//! OpenCV 与 ONNX Runtime 的 Android 适配；计算规则与 Python 版对齐。
use crate::{analysis::Detection, calibration::Calibration};
use anyhow::{ensure, Result};
use opencv::{
    calib3d,
    core::{self, Mat, MatTraitConst, MatTraitConstManual, Ptr, Scalar, Size, Vec3b},
    imgproc,
    prelude::*,
};

pub const LABELS: [&str; 80] = [
    "人",
    "自行车",
    "汽车",
    "摩托车",
    "飞机",
    "公交车",
    "火车",
    "卡车",
    "船",
    "交通灯",
    "消防栓",
    "停车标志",
    "停车计时器",
    "长椅",
    "鸟",
    "猫",
    "狗",
    "马",
    "羊",
    "牛",
    "大象",
    "熊",
    "斑马",
    "长颈鹿",
    "背包",
    "雨伞",
    "手提包",
    "领带",
    "行李箱",
    "飞盘",
    "滑雪板",
    "单板滑雪",
    "运动球",
    "风筝",
    "棒球棒",
    "棒球手套",
    "滑板",
    "冲浪板",
    "网球拍",
    "瓶子",
    "酒杯",
    "杯子",
    "叉子",
    "刀",
    "勺子",
    "碗",
    "香蕉",
    "苹果",
    "三明治",
    "橙子",
    "西兰花",
    "胡萝卜",
    "热狗",
    "披萨",
    "甜甜圈",
    "蛋糕",
    "椅子",
    "沙发",
    "盆栽",
    "床",
    "餐桌",
    "马桶",
    "电视",
    "笔记本电脑",
    "鼠标",
    "遥控器",
    "键盘",
    "手机",
    "微波炉",
    "烤箱",
    "烤面包机",
    "水槽",
    "冰箱",
    "书",
    "时钟",
    "花瓶",
    "剪刀",
    "泰迪熊",
    "吹风机",
    "牙刷",
];

pub struct Processor {
    matcher: Ptr<calib3d::StereoSGBM>,
    maps: Option<[Mat; 4]>,
    pub focal: f32,
    pub baseline: f32,
    pub metric: bool,
}
fn matrix(v: &[Vec<f64>]) -> Result<Mat> {
    Ok(Mat::from_slice_2d(v)?)
}
impl Processor {
    pub fn new(calibration: Option<&Calibration>, demo: bool) -> Result<Self> {
        let matcher = calib3d::StereoSGBM::create(
            0,
            80,
            5,
            200,
            800,
            1,
            31,
            10,
            100,
            2,
            calib3d::StereoSGBM_MODE_SGBM_3WAY,
        )?;
        let mut p = Self {
            matcher,
            maps: None,
            focal: 240.,
            baseline: 0.064,
            metric: demo,
        };
        if !demo {
            if let Some(c) = calibration {
                let mut maps = [
                    Mat::default(),
                    Mat::default(),
                    Mat::default(),
                    Mat::default(),
                ];
                for (i, k, d, r, proj) in [
                    (
                        0,
                        &c.left_camera_matrix,
                        &c.left_distortion,
                        &c.rectification_left,
                        &c.projection_left,
                    ),
                    (
                        2,
                        &c.right_camera_matrix,
                        &c.right_distortion,
                        &c.rectification_right,
                        &c.projection_right,
                    ),
                ] {
                    let (mut a, mut b) = (Mat::default(), Mat::default());
                    calib3d::init_undistort_rectify_map(
                        &matrix(k)?,
                        &matrix(d)?,
                        &matrix(r)?,
                        &matrix(proj)?,
                        Size::new(320, 240),
                        core::CV_32FC1,
                        &mut a,
                        &mut b,
                    )?;
                    maps[i] = a;
                    maps[i + 1] = b;
                }
                p.maps = Some(maps);
                p.focal = c.focal() as f32;
                p.baseline = c.baseline() as f32;
                p.metric = true;
            }
        }
        Ok(p)
    }
    pub fn process(&mut self, rgba: &[u8]) -> Result<(Mat, Vec<f32>, Vec<Vec<u8>>)> {
        ensure!(rgba.len() == 640 * 240 * 4, "相机帧尺寸必须为 640×240 RGBA");
        let raw = Mat::from_slice(rgba)?;
        let raw = raw.reshape(4, 240)?;
        let mut bgr = Mat::default();
        imgproc::cvt_color_def(&raw, &mut bgr, imgproc::COLOR_RGBA2BGR)?;
        let mut left = Mat::roi(&bgr, core::Rect::new(0, 0, 320, 240))?.try_clone()?;
        let mut right = Mat::roi(&bgr, core::Rect::new(320, 0, 320, 240))?.try_clone()?;
        if let Some(m) = &self.maps {
            let (mut a, mut b) = (Mat::default(), Mat::default());
            imgproc::remap(
                &left,
                &mut a,
                &m[0],
                &m[1],
                imgproc::INTER_LINEAR,
                core::BORDER_CONSTANT,
                Scalar::all(0.),
            )?;
            imgproc::remap(
                &right,
                &mut b,
                &m[2],
                &m[3],
                imgproc::INTER_LINEAR,
                core::BORDER_CONSTANT,
                Scalar::all(0.),
            )?;
            left = a;
            right = b;
        }
        let (mut gray_l, mut gray_r, mut disparity) =
            (Mat::default(), Mat::default(), Mat::default());
        imgproc::cvt_color_def(&left, &mut gray_l, imgproc::COLOR_BGR2GRAY)?;
        imgproc::cvt_color_def(&right, &mut gray_r, imgproc::COLOR_BGR2GRAY)?;
        self.matcher.compute(&gray_l, &gray_r, &mut disparity)?;
        let d: Vec<f32> = disparity
            .data_typed::<i16>()?
            .iter()
            .map(|v| *v as f32 / 16.)
            .collect();
        let depth = if self.metric {
            crate::analysis::depth_from_disparity(&d, self.focal, self.baseline)
        } else {
            vec![f32::NAN; 320 * 240]
        };
        let previews = vec![
            to_rgba(&left)?,
            to_rgba(&right)?,
            colorize(&d, imgproc::COLORMAP_TURBO)?,
            colorize(&depth, imgproc::COLORMAP_MAGMA)?,
        ];
        Ok((left, depth, previews))
    }
}
pub fn to_rgba(bgr: &Mat) -> Result<Vec<u8>> {
    let mut out = Mat::default();
    imgproc::cvt_color_def(bgr, &mut out, imgproc::COLOR_BGR2RGBA)?;
    Ok(out.data_bytes()?.to_vec())
}
fn colorize(values: &[f32], palette: i32) -> Result<Vec<u8>> {
    let (mut lo, mut hi) = (f32::INFINITY, f32::NEG_INFINITY);
    for &v in values {
        if v.is_finite() && v > 0. {
            lo = lo.min(v);
            hi = hi.max(v);
        }
    }
    let normalized: Vec<u8> = values
        .iter()
        .map(|v| {
            if v.is_finite() && *v > 0. {
                (((v - lo) / (hi - lo).max(0.001)) * 255.).clamp(0., 255.) as u8
            } else {
                0
            }
        })
        .collect();
    let m = Mat::from_slice(&normalized)?;
    let m = m.reshape(1, 240)?;
    let mut colored = Mat::default();
    imgproc::apply_color_map(&m, &mut colored, palette)?;
    let mut out = to_rgba(&colored)?;
    for (i, v) in values.iter().enumerate() {
        if !v.is_finite() || *v <= 0. {
            out[4 * i..4 * i + 3].fill(0);
        }
    }
    Ok(out)
}
pub fn demo_frame() -> Vec<u8> {
    // 确定性纹理平面，已校正；不伪造识别框或实测距离。
    let mut out = vec![0u8; 640 * 240 * 4];
    let texture = |x: usize, y: usize| {
        let n = (x as u32).wrapping_mul(374761393) ^ (y as u32).wrapping_mul(668265263);
        ((n ^ (n >> 13)).wrapping_mul(1274126177) >> 24) as u8
    };
    for y in 0..240 {
        for x in 0..320 {
            let d = if y < 80 {
                8
            } else if y < 160 {
                16
            } else {
                24
            };
            for (xx, src) in [(x, x), (x + 320, (x + d).min(319))] {
                let i = (y * 640 + xx) * 4;
                let v = texture(src, y);
                out[i..i + 4].copy_from_slice(&[v, v, v, 255]);
            }
        }
    }
    out
}
pub struct Detector {
    session: ort::session::Session,
}
impl Detector {
    pub fn new(model: &str, runtime: &str) -> Result<Self> {
        ort::init_from(runtime).with_name("StereoRange").commit()?;
        let session = ort::session::Session::builder()?
            .with_intra_threads(2)?
            .commit_from_file(model)?;
        Ok(Self { session })
    }
    pub fn detect(&mut self, bgr: &Mat, confidence: f32) -> Result<Vec<Detection>> {
        let ratio = (416. / bgr.cols() as f32).min(416. / bgr.rows() as f32);
        let (w, h) = (
            (bgr.cols() as f32 * ratio) as i32,
            (bgr.rows() as f32 * ratio) as i32,
        );
        let mut resized = Mat::default();
        imgproc::resize(
            bgr,
            &mut resized,
            Size::new(w, h),
            0.,
            0.,
            imgproc::INTER_LINEAR,
        )?;
        let mut input = vec![114f32; 3 * 416 * 416];
        let pix = resized.data_typed::<Vec3b>()?;
        for y in 0..h as usize {
            for x in 0..w as usize {
                for c in 0..3 {
                    input[c * 416 * 416 + y * 416 + x] = pix[y * w as usize + x][2 - c] as f32;
                }
            }
        }
        let tensor = ort::value::Tensor::from_array(([1usize, 3, 416, 416], input))?;
        let result = self.session.run(ort::inputs![tensor])?;
        let (shape, values) = result[0].try_extract_tensor::<f32>()?;
        ensure!(
            &**shape == [1, 3549, 85],
            "YOLOX 输出尺寸不匹配，应为 [1,3549,85]"
        );
        let mut boxes = Vec::new();
        let mut row = 0;
        for stride in [8, 16, 32] {
            for y in 0..416 / stride {
                for x in 0..416 / stride {
                    let v = &values[row * 85..(row + 1) * 85];
                    row += 1;
                    let (id, score) = v[5..]
                        .iter()
                        .enumerate()
                        .max_by(|a, b| a.1.total_cmp(b.1))
                        .unwrap();
                    let score = score * v[4];
                    if !score.is_finite() || score < confidence {
                        continue;
                    }
                    let cx = (v[0] + x as f32) * stride as f32 / ratio;
                    let cy = (v[1] + y as f32) * stride as f32 / ratio;
                    let bw = v[2].exp() * stride as f32 / ratio;
                    let bh = v[3].exp() * stride as f32 / ratio;
                    if ![cx, cy, bw, bh].iter().all(|x| x.is_finite()) {
                        continue;
                    }
                    boxes.push((
                        id,
                        score,
                        [cx - bw / 2., cy - bh / 2., cx + bw / 2., cy + bh / 2.],
                    ));
                }
            }
        }
        boxes.sort_by(|a, b| b.1.total_cmp(&a.1));
        let mut kept: Vec<(usize, f32, [f32; 4])> = Vec::new();
        for b in boxes {
            if kept.iter().all(|k| iou(k.2, b.2) <= 0.45) {
                kept.push(b);
            }
        }
        Ok(kept
            .into_iter()
            .filter_map(|(class_id, confidence, b)| {
                let bbox = [
                    b[0].clamp(0., 320.) as usize,
                    b[1].clamp(0., 240.) as usize,
                    b[2].clamp(0., 320.) as usize,
                    b[3].clamp(0., 240.) as usize,
                ];
                (bbox[2] > bbox[0] && bbox[3] > bbox[1]).then(|| Detection {
                    class_id,
                    label: LABELS[class_id].into(),
                    confidence,
                    bbox,
                    valid_depth_ratio: 0.,
                    distance_m: None,
                    depth_point: None,
                })
            })
            .collect())
    }
}
fn iou(a: [f32; 4], b: [f32; 4]) -> f32 {
    let intersection =
        (a[2].min(b[2]) - a[0].max(b[0])).max(0.) * (a[3].min(b[3]) - a[1].max(b[1])).max(0.);
    intersection
        / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection).max(1e-6)
}
