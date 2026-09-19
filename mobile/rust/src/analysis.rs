//! 平湖技师学院 · 陆逸尘（辰渊尘 ChenDusk · @mcxiaochenn）· 周璟雯 · 胡乐毅 · 指导教师 张梁
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Settings {
    pub minimum_m: f32,
    pub maximum_m: f32,
    pub confidence: f32,
    pub objects_only: bool,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            minimum_m: 0.2,
            maximum_m: 3.,
            confidence: 0.4,
            objects_only: false,
        }
    }
}
impl Settings {
    pub fn validate(&self) -> anyhow::Result<()> {
        anyhow::ensure!(
            self.minimum_m.is_finite()
                && self.maximum_m.is_finite()
                && self.minimum_m > 0.
                && self.maximum_m > self.minimum_m,
            "距离范围必须为有限正数，且最大值大于最小值"
        );
        anyhow::ensure!(
            self.confidence.is_finite() && self.confidence > 0. && self.confidence <= 1.,
            "置信度必须在 0～1 之间"
        );
        Ok(())
    }
    pub fn valid(&self, v: f32) -> bool {
        v.is_finite() && v >= self.minimum_m && v <= self.maximum_m
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Detection {
    pub class_id: usize,
    pub label: String,
    pub confidence: f32,
    pub bbox: [usize; 4],
    pub valid_depth_ratio: f32,
    pub distance_m: Option<f32>,
    pub depth_point: Option<[usize; 2]>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Point {
    pub kind: String,
    pub x: f32,
    pub y: f32,
    pub distance_m: f32,
    pub source: String,
}
pub fn median(values: &mut [f32]) -> Option<f32> {
    if values.is_empty() {
        return None;
    }
    values.sort_unstable_by(f32::total_cmp);
    let n = values.len();
    Some(if n % 2 == 0 {
        (values[n / 2 - 1] + values[n / 2]) / 2.
    } else {
        values[n / 2]
    })
}
pub fn depth_from_disparity(d: &[f32], f: f32, b: f32) -> Vec<f32> {
    d.iter()
        .map(|v| {
            if v.is_finite() && *v > 0. {
                f * b / v
            } else {
                f32::NAN
            }
        })
        .collect()
}
pub fn sample(
    depth: &[f32],
    w: usize,
    h: usize,
    x: usize,
    y: usize,
    window: usize,
    s: &Settings,
) -> Option<f32> {
    if x >= w || y >= h || depth.len() != w * h {
        return None;
    }
    let r = window / 2;
    let mut values = Vec::new();
    for yy in y.saturating_sub(r)..(y + r + 1).min(h) {
        for xx in x.saturating_sub(r)..(x + r + 1).min(w) {
            let d = depth[yy * w + xx];
            if s.valid(d) {
                values.push(d);
            }
        }
    }
    median(&mut values)
}
pub fn detection_distances(
    detections: &mut [Detection],
    depth: &[f32],
    w: usize,
    h: usize,
    s: &Settings,
) {
    for d in detections {
        d.distance_m = None;
        d.depth_point = None;
        d.valid_depth_ratio = 0.;
        let [x1, y1, x2, y2] = d.bbox;
        let (x1, y1, x2, y2) = (x1.min(w), y1.min(h), x2.min(w), y2.min(h));
        if x2 <= x1 || y2 <= y1 {
            continue;
        }
        let mx = ((x2 - x1) as f32 * 0.2) as usize;
        let my = ((y2 - y1) as f32 * 0.2) as usize;
        let area = (x2 - x1 - 2 * mx) * (y2 - y1 - 2 * my);
        let (mut values, mut xs, mut ys) = (Vec::new(), Vec::new(), Vec::new());
        for y in y1 + my..y2 - my {
            for x in x1 + mx..x2 - mx {
                let v = depth[y * w + x];
                if s.valid(v) {
                    values.push(v);
                    xs.push(x as f32);
                    ys.push(y as f32);
                }
            }
        }
        d.valid_depth_ratio = values.len() as f32 / area as f32;
        if values.len() >= 10.max(area / 10) {
            d.distance_m = median(&mut values);
            d.depth_point = Some([
                median(&mut xs).unwrap() as usize,
                median(&mut ys).unwrap() as usize,
            ]);
        }
    }
}
pub fn points(
    depth: &[f32],
    w: usize,
    h: usize,
    detections: &[Detection],
    s: &Settings,
) -> Vec<Point> {
    let mut candidates = Vec::new();
    if s.objects_only {
        for d in detections {
            if let (Some(z), Some([x, y])) = (d.distance_m, d.depth_point) {
                candidates.push(Point {
                    kind: String::new(),
                    x: x as f32,
                    y: y as f32,
                    distance_m: z,
                    source: d.label.clone(),
                });
            }
        }
    } else {
        for y in (0..h).step_by(8) {
            for x in (0..w).step_by(8) {
                let (bw, bh) = (8.min(w - x), 8.min(h - y));
                let mut values = Vec::new();
                for yy in y..y + bh {
                    for xx in x..x + bw {
                        let v = depth[yy * w + xx];
                        if s.valid(v) {
                            values.push(v);
                        }
                    }
                }
                if values.len() * 2 >= bw * bh {
                    if let Some(z) = median(&mut values) {
                        candidates.push(Point {
                            kind: String::new(),
                            x: (x + bw / 2) as f32,
                            y: (y + bh / 2) as f32,
                            distance_m: z,
                            source: "全场景".into(),
                        });
                    }
                }
            }
        }
    }
    let mut result = Vec::new();
    if let Some(p) = candidates
        .iter()
        .min_by(|a, b| a.distance_m.total_cmp(&b.distance_m))
    {
        let mut p = p.clone();
        p.kind = "nearest".into();
        result.push(p);
    }
    if let Some(z) = sample(depth, w, h, w / 2, h / 2, 15, s) {
        result.push(Point {
            kind: "center".into(),
            x: (w / 2) as f32,
            y: (h / 2) as f32,
            distance_m: z,
            source: "画面中心".into(),
        });
    }
    if let Some(p) = candidates
        .iter()
        .rev()
        .max_by(|a, b| a.distance_m.total_cmp(&b.distance_m))
    {
        let mut p = p.clone();
        p.kind = "farthest".into();
        result.push(p);
    }
    result
}
#[derive(Default)]
pub struct Tracker {
    stored: Vec<(Point, f64)>,
}
impl Tracker {
    pub fn reset(&mut self) {
        self.stored.clear();
    }
    pub fn update(&mut self, candidates: Vec<Point>, now: f64) -> Vec<Point> {
        // 超时后再出现的目标从新值起步，不向过期目标平滑。
        self.stored.retain(|(_, seen)| now - seen <= 0.5);
        for mut c in candidates {
            if let Some((old, t)) = self.stored.iter_mut().find(|(p, _)| p.kind == c.kind) {
                c.x = old.x * 0.75 + c.x * 0.25;
                c.y = old.y * 0.75 + c.y * 0.25;
                c.distance_m = old.distance_m * 0.75 + c.distance_m * 0.25;
                *old = c;
                *t = now;
            } else {
                self.stored.push((c, now));
            }
        }
        self.stored.iter().map(|(p, _)| p.clone()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn depth_and_invalid() {
        let z = depth_from_disparity(&[10., 0., -1., f32::NAN], 200., 0.1);
        assert_eq!(z[0], 2.);
        assert!(z[1..].iter().all(|x| x.is_nan()));
    }
    #[test]
    fn sample_range_and_edges() {
        let s = Settings::default();
        let mut z = vec![1.; 49];
        z[24] = 99.;
        assert_eq!(sample(&z, 7, 7, 3, 3, 7, &s), Some(1.));
        assert_eq!(sample(&z, 7, 7, 9, 0, 7, &s), None);
        assert_eq!(sample(&vec![f32::NAN; 49], 7, 7, 0, 0, 7, &s), None);
    }
    #[test]
    fn grid_rejects_single_extreme() {
        let mut z = vec![1.; 256];
        z[0] = 0.2;
        z[15] = 3.;
        let p = points(&z, 16, 16, &[], &Settings::default());
        assert!(p.iter().all(|p| p.distance_m == 1.));
    }
    #[test]
    fn box_filters_and_objects() {
        let mut d = vec![Detection {
            class_id: 0,
            label: "人".into(),
            confidence: 0.9,
            bbox: [0, 0, 20, 20],
            valid_depth_ratio: 0.,
            distance_m: Some(9.),
            depth_point: None,
        }];
        let mut s = Settings::default();
        detection_distances(&mut d, &vec![2.; 400], 20, 20, &s);
        assert_eq!(d[0].distance_m, Some(2.));
        s.objects_only = true;
        assert_eq!(points(&vec![1.; 400], 20, 20, &d, &s)[0].distance_m, 2.);
        detection_distances(&mut d, &vec![f32::NAN; 400], 20, 20, &s);
        assert_eq!(d[0].distance_m, None);
    }
    #[test]
    fn ema_and_expiry() {
        let p = Point {
            kind: "center".into(),
            x: 0.,
            y: 0.,
            distance_m: 1.,
            source: "中心".into(),
        };
        let mut t = Tracker::default();
        t.update(vec![p.clone()], 0.);
        let mut q = p;
        q.distance_m = 3.;
        assert_eq!(t.update(vec![q], 0.1)[0].distance_m, 1.5);
        assert_eq!(t.update(vec![], 0.5).len(), 1);
        assert!(t.update(vec![], 0.61).is_empty());
    }
    #[test]
    fn settings_reject_nan() {
        let mut s = Settings::default();
        s.minimum_m = f32::NAN;
        assert!(s.validate().is_err());
    }
}
