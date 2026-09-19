//! 接收公开的合成测试数据，对照 Python 距离统计；不读取个人资源。
use serde::Deserialize;
use std::io::{self, Read};
use stereorange_native::analysis::{self, Detection, Settings};

#[derive(Deserialize)]
struct Input {
    width: usize,
    height: usize,
    depth: Vec<Option<f32>>,
    detections: Vec<Detection>,
}
fn main() -> anyhow::Result<()> {
    let mut text = String::new();
    io::stdin().read_to_string(&mut text)?;
    let mut input: Input = serde_json::from_str(&text)?;
    let depth: Vec<f32> = input.depth.iter().map(|v| v.unwrap_or(f32::NAN)).collect();
    anyhow::ensure!(
        depth.len() == input.width * input.height,
        "测试图尺寸不一致"
    );
    let mut settings = Settings::default();
    analysis::detection_distances(
        &mut input.detections,
        &depth,
        input.width,
        input.height,
        &settings,
    );
    let scene = analysis::points(
        &depth,
        input.width,
        input.height,
        &input.detections,
        &settings,
    );
    settings.objects_only = true;
    let objects = analysis::points(
        &depth,
        input.width,
        input.height,
        &input.detections,
        &settings,
    );
    println!(
        "{}",
        serde_json::json!({"detections":input.detections,"scene":scene,"objects":objects})
    );
    Ok(())
}
