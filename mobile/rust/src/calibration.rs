use anyhow::{ensure, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Calibration {
    pub schema_version: u32,
    pub length_unit: String,
    pub image_size: [usize; 2],
    pub left_camera_matrix: Vec<Vec<f64>>,
    pub right_camera_matrix: Vec<Vec<f64>>,
    pub left_distortion: Vec<Vec<f64>>,
    pub right_distortion: Vec<Vec<f64>>,
    pub rectification_left: Vec<Vec<f64>>,
    pub rectification_right: Vec<Vec<f64>>,
    pub projection_left: Vec<Vec<f64>>,
    pub projection_right: Vec<Vec<f64>>,
    pub rotation: Vec<Vec<f64>>,
    pub translation: Vec<Vec<f64>>,
    pub disparity_to_depth: Vec<Vec<f64>>,
    pub rms_stereo: f64,
}

impl Calibration {
    pub fn parse(text: &str) -> Result<Self> {
        let c: Self = serde_json::from_str(text)?;
        ensure!(
            c.schema_version == 1 && c.length_unit == "m",
            "不支持的标定版本或单位"
        );
        ensure!(
            c.image_size == [320, 240],
            "标定必须为单目 320×240，请重新导出匹配分辨率的标定"
        );
        for (m, rows, cols) in [
            (&c.left_camera_matrix, 3, 3),
            (&c.right_camera_matrix, 3, 3),
            (&c.rectification_left, 3, 3),
            (&c.rectification_right, 3, 3),
            (&c.projection_left, 3, 4),
            (&c.projection_right, 3, 4),
            (&c.rotation, 3, 3),
            (&c.translation, 3, 1),
            (&c.disparity_to_depth, 4, 4),
        ] {
            ensure!(
                m.len() == rows
                    && m.iter()
                        .all(|r| r.len() == cols && r.iter().all(|v| v.is_finite())),
                "标定矩阵尺寸或数值无效"
            );
        }
        for d in [&c.left_distortion, &c.right_distortion] {
            let n: usize = d.iter().map(Vec::len).sum();
            ensure!(
                matches!(n, 4 | 5 | 8 | 12 | 14)
                    && (d.len() == 1 || d.iter().all(|r| r.len() == 1))
                    && d.iter().flatten().all(|v| v.is_finite()),
                "畸变参数无效"
            );
        }
        ensure!(c.rms_stereo.is_finite() && c.rms_stereo >= 0., "RMS 无效");
        ensure!(
            c.projection_left[0][0] > 0.
                && c.projection_right[0][0] > 0.
                && c.focal().is_finite()
                && c.baseline().is_finite()
                && c.baseline() > 0.,
            "焦距或基线无效"
        );
        Ok(c)
    }
    pub fn focal(&self) -> f64 {
        (self.projection_left[0][0] + self.projection_right[0][0]) / 2.
    }
    pub fn baseline(&self) -> f64 {
        self.translation
            .iter()
            .flatten()
            .map(|v| v * v)
            .sum::<f64>()
            .sqrt()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> serde_json::Value {
        let identity = vec![vec![1., 0., 0.], vec![0., 1., 0.], vec![0., 0., 1.]];
        let projection = vec![
            vec![240., 0., 160., 0.],
            vec![0., 240., 120., 0.],
            vec![0., 0., 1., 0.],
        ];
        serde_json::json!({
            "schema_version":1,"length_unit":"m","image_size":[320,240],
            "left_camera_matrix":identity,"right_camera_matrix":identity,
            "left_distortion":[[0.,0.,0.,0.,0.]],"right_distortion":[[0.,0.,0.,0.,0.]],
            "rectification_left":identity,"rectification_right":identity,
            "projection_left":projection,"projection_right":projection,
            "rotation":identity,"translation":[[-0.064],[0.],[0.]],
            "disparity_to_depth":[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]],
            "rms_stereo":0.5
        })
    }
    #[test]
    fn valid_calibration() {
        let c = Calibration::parse(&fixture().to_string()).unwrap();
        assert_eq!(c.focal(), 240.);
        assert_eq!(c.baseline(), 0.064);
    }
    #[test]
    fn rejects_wrong_units_size_shape_and_baseline() {
        for (key, value) in [
            ("length_unit", serde_json::json!("mm")),
            ("schema_version", serde_json::json!(2)),
            ("image_size", serde_json::json!([640, 480])),
            ("left_camera_matrix", serde_json::json!([[1.]])),
            ("translation", serde_json::json!([[0.], [0.], [0.]])),
            ("rms_stereo", serde_json::json!(-1.)),
        ] {
            let mut value_fixture = fixture();
            value_fixture[key] = value;
            assert!(
                Calibration::parse(&value_fixture.to_string()).is_err(),
                "{key}"
            );
        }
    }
}
