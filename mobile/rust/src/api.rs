use crate::{
    analysis::{Detection, Point, Settings},
    calibration::Calibration,
};
use anyhow::Result;
use serde::Serialize;
use std::sync::{Mutex, OnceLock};

#[derive(Clone, Default, Serialize)]
pub struct FrameResult {
    pub frame_id: u64,
    pub timestamp_ms: u64,
    pub width: usize,
    pub height: usize,
    pub running: bool,
    pub demo: bool,
    pub capture_fps: f32,
    pub depth_fps: f32,
    pub detection_fps: f32,
    pub latency_ms: f32,
    pub detections: Vec<Detection>,
    pub points: Vec<Point>,
    pub warnings: Vec<String>,
    pub rms: Option<f64>,
    pub model_ready: bool,
}
pub(crate) struct State {
    pub settings: Settings,
    pub calibration: Option<Calibration>,
    pub running: bool,
    pub demo: bool,
    pub generation: u64,
    pub result: FrameResult,
    pub depth: Vec<f32>,
    pub previews: Vec<Vec<u8>>,
    pub sink: Option<crate::frb_generated::StreamSink<String>>,
}
impl Default for State {
    fn default() -> Self {
        Self {
            settings: Settings::default(),
            calibration: None,
            running: false,
            demo: false,
            generation: 0,
            result: FrameResult {
                width: 320,
                height: 240,
                ..Default::default()
            },
            depth: Vec::new(),
            previews: Vec::new(),
            sink: None,
        }
    }
}
pub(crate) fn state() -> &'static Mutex<State> {
    static STATE: OnceLock<Mutex<State>> = OnceLock::new();
    STATE.get_or_init(|| Mutex::new(State::default()))
}
pub(crate) fn publish(s: &State) {
    if let Some(sink) = &s.sink {
        if let Ok(json) = serde_json::to_string(&s.result) {
            let _ = sink.add(json);
        }
    }
}
pub fn initialize(model_path: String, runtime_path: String) -> Result<()> {
    #[cfg(target_os = "android")]
    crate::android::initialize(model_path, runtime_path)?;
    #[cfg(not(target_os = "android"))]
    let _ = (model_path, runtime_path);
    Ok(())
}
pub fn subscribe_results(sink: crate::frb_generated::StreamSink<String>) -> Result<()> {
    let mut s = state().lock().unwrap();
    s.sink = Some(sink);
    publish(&s);
    Ok(())
}
pub fn unsubscribe_results() -> Result<()> {
    // 主动释放 Rust 端发送器，让 Dart 的异步流取消能够完成。
    state().lock().unwrap().sink = None;
    Ok(())
}
pub fn start_session(demo: bool) -> Result<()> {
    let mut s = state().lock().unwrap();
    s.running = true;
    s.demo = demo;
    s.generation += 1;
    s.depth.clear();
    s.previews.clear();
    s.result.points.clear();
    s.result.detections.clear();
    s.result.running = true;
    s.result.demo = demo;
    publish(&s);
    drop(s);
    #[cfg(target_os = "android")]
    crate::android::wake();
    Ok(())
}
pub fn stop_session() -> Result<()> {
    let mut s = state().lock().unwrap();
    s.running = false;
    s.generation += 1;
    s.depth.clear();
    s.previews.clear();
    s.result.points.clear();
    s.result.detections.clear();
    s.result.running = false;
    s.result.capture_fps = 0.;
    s.result.depth_fps = 0.;
    s.result.detection_fps = 0.;
    publish(&s);
    Ok(())
}
pub fn update_settings(json: String) -> Result<()> {
    let next: Settings = serde_json::from_str(&json)?;
    next.validate()?;
    let mut s = state().lock().unwrap();
    if s.settings == next {
        return Ok(());
    }
    s.settings = next;
    s.generation += 1;
    s.depth.clear();
    s.result.points.clear();
    s.result.detections.clear();
    publish(&s);
    Ok(())
}
pub fn load_calibration(json: String) -> Result<f64> {
    let c = Calibration::parse(&json)?;
    let rms = c.rms_stereo;
    let mut s = state().lock().unwrap();
    s.calibration = Some(c);
    s.generation += 1;
    s.depth.clear();
    s.result.points.clear();
    s.result.rms = Some(rms);
    publish(&s);
    Ok(rms)
}
pub fn sample_distance(x: u32, y: u32) -> Result<Option<f32>> {
    let s = state().lock().unwrap();
    Ok(if s.running {
        crate::analysis::sample(&s.depth, 320, 240, x as usize, y as usize, 7, &s.settings)
    } else {
        None
    })
}
#[flutter_rust_bridge::frb(init)]
pub fn init_app() {
    flutter_rust_bridge::setup_default_user_utils();
}
