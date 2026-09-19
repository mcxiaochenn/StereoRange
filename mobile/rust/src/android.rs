use crate::{
    analysis::{self, Detection, Tracker},
    api::{publish, state, FrameResult},
    vision::{Detector, Processor},
};
use jni::{
    objects::{JByteBuffer, JClass},
    sys::{jint, jstring},
    JNIEnv,
};
use opencv::core::Mat;
use std::{
    sync::{Condvar, Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

struct Input {
    bytes: Vec<u8>,
    time: f64,
    generation: u64,
}
struct DetectionInput {
    image: Mat,
    time: f64,
    generation: u64,
    confidence: f32,
}
#[derive(Default)]
struct DetectionOutput {
    boxes: Vec<Detection>,
    time: f64,
    generation: u64,
    fps: f32,
}
struct Engine {
    input: Mutex<Option<Input>>,
    signal: Condvar,
    pool: Mutex<Vec<Vec<u8>>>,
    detection_input: Mutex<Option<DetectionInput>>,
    detection_signal: Condvar,
    detection_output: Mutex<DetectionOutput>,
    detector: Mutex<Option<Detector>>,
    model_error: Mutex<Option<String>>,
    capture_interval: Mutex<(f64, f32)>,
}
fn engine() -> &'static Engine {
    static E: OnceLock<Engine> = OnceLock::new();
    E.get_or_init(|| Engine {
        input: Mutex::new(None),
        signal: Condvar::new(),
        pool: Mutex::new(Vec::new()),
        detection_input: Mutex::new(None),
        detection_signal: Condvar::new(),
        detection_output: Mutex::new(DetectionOutput::default()),
        detector: Mutex::new(None),
        model_error: Mutex::new(None),
        capture_interval: Mutex::new((0., 0.)),
    })
}
fn now() -> f64 {
    static ORIGIN: OnceLock<Instant> = OnceLock::new();
    ORIGIN.get_or_init(Instant::now).elapsed().as_secs_f64()
}
pub fn wake() {
    engine().signal.notify_one();
}
pub fn initialize(model: String, runtime: String) -> anyhow::Result<()> {
    let e = engine();
    if e.detector.lock().unwrap().is_none() {
        match Detector::new(&model, &runtime) {
            Ok(d) => {
                *e.detector.lock().unwrap() = Some(d);
                *e.model_error.lock().unwrap() = None;
            }
            Err(error) => {
                *e.model_error.lock().unwrap() = Some(format!("识别模型不可用：{error}"));
            }
        }
    }
    {
        let mut s = state().lock().unwrap();
        s.result.model_ready = e.model_error.lock().unwrap().is_none();
        s.result.warnings = e.model_error.lock().unwrap().iter().cloned().collect();
        publish(&s);
    }
    static STARTED: OnceLock<()> = OnceLock::new();
    STARTED.get_or_init(|| {
        thread::spawn(process_loop);
        thread::spawn(detection_loop);
    });
    Ok(())
}
fn process_loop() {
    let e = engine();
    let mut generation = u64::MAX;
    let mut processor: Option<Processor> = None;
    let mut tracker = Tracker::default();
    let mut number = 0;
    let mut previous = now();
    loop {
        let input = e.input.lock().unwrap();
        let (mut input, _) = e
            .signal
            .wait_timeout_while(input, Duration::from_millis(33), |i| i.is_none())
            .unwrap();
        let frame = input.take();
        drop(input);
        let (running, demo, gen, settings, calibration) = {
            let s = state().lock().unwrap();
            (
                s.running,
                s.demo,
                s.generation,
                s.settings.clone(),
                s.calibration.clone(),
            )
        };
        if !running {
            continue;
        }
        if generation != gen {
            generation = gen;
            tracker.reset();
            match Processor::new(calibration.as_ref(), demo) {
                Ok(p) => processor = Some(p),
                Err(err) => {
                    fail(gen, format!("校正初始化失败：{err}"));
                    continue;
                }
            }
        }
        let frame = if demo {
            Some(Input {
                bytes: crate::vision::demo_frame(),
                time: now(),
                generation: gen,
            })
        } else {
            frame
        };
        let Some(frame) = frame else {
            let mut s = state().lock().unwrap();
            if s.running
                && now() * 1000. - s.result.timestamp_ms as f64 > 500.
                && s.result.depth_fps != 0.
            {
                s.depth.clear();
                s.result.points.clear();
                s.result.detections.clear();
                s.result.capture_fps = 0.;
                s.result.depth_fps = 0.;
                s.result.detection_fps = 0.;
                s.result.warnings = vec!["相机暂未提供新画面，请检查连接".into()];
                publish(&s);
            }
            continue;
        };
        if frame.generation != gen {
            continue;
        }
        let Some(p) = processor.as_mut() else {
            continue;
        };
        match p.process(&frame.bytes) {
            Ok((left, depth, previews)) => {
                let time = now();
                {
                    *e.detection_input.lock().unwrap() = Some(DetectionInput {
                        image: left,
                        time: frame.time,
                        generation: gen,
                        confidence: settings.confidence,
                    });
                    e.detection_signal.notify_one();
                }
                let cached = e.detection_output.lock().unwrap();
                let fresh = cached.generation == gen && time - cached.time <= 0.5;
                let mut detections = if fresh {
                    cached.boxes.clone()
                } else {
                    Vec::new()
                };
                let detection_fps = if fresh { cached.fps } else { 0. };
                drop(cached);
                analysis::detection_distances(&mut detections, &depth, 320, 240, &settings);
                let points = tracker.update(
                    analysis::points(&depth, 320, 240, &detections, &settings),
                    time,
                );
                let mut warnings = Vec::new();
                if demo {
                    warnings.push("模拟双目图与虚拟参数，仅用于演示".into());
                }
                if !p.metric {
                    warnings.push("未导入匹配标定，距离不可用".into());
                }
                let rms = if demo {
                    None
                } else {
                    calibration.as_ref().map(|c| c.rms_stereo)
                };
                if rms.is_some_and(|v| v > 2.) {
                    warnings.push("标定 RMS 较高，距离仅供参考".into());
                }
                if let Some(error) = e.model_error.lock().unwrap().as_ref() {
                    warnings.push(error.clone());
                }
                number += 1;
                let fps = (1. / (time - previous).max(0.001)) as f32;
                previous = time;
                let mut s = state().lock().unwrap();
                if s.running && s.generation == gen {
                    s.result = FrameResult {
                        frame_id: number,
                        timestamp_ms: (frame.time * 1000.) as u64,
                        width: 320,
                        height: 240,
                        running: true,
                        demo,
                        capture_fps: if demo {
                            fps
                        } else {
                            e.capture_interval.lock().unwrap().1
                        },
                        depth_fps: fps,
                        detection_fps,
                        latency_ms: ((time - frame.time) * 1000.) as f32,
                        detections,
                        points,
                        warnings,
                        rms,
                        model_ready: e.model_error.lock().unwrap().is_none(),
                    };
                    s.depth = depth;
                    s.previews = previews;
                    publish(&s);
                }
            }
            Err(error) => fail(gen, format!("图像处理失败：{error}")),
        }
        let mut pool = e.pool.lock().unwrap();
        if pool.len() < 3 {
            pool.push(frame.bytes);
        }
    }
}
fn fail(generation: u64, message: String) {
    let mut s = state().lock().unwrap();
    if s.generation == generation {
        s.running = false;
        s.result.running = false;
        s.result.points.clear();
        s.result.detections.clear();
        s.depth.clear();
        s.result.warnings = vec![message];
        publish(&s);
    }
}
fn detection_loop() {
    let e = engine();
    let mut last = 0.;
    let mut last_started = 0.;
    loop {
        let input = e.detection_input.lock().unwrap();
        let mut input = e
            .detection_signal
            .wait_while(input, |i| i.is_none())
            .unwrap();
        let mut task = input.take().unwrap();
        drop(input);
        let remaining = 0.1 - (now() - last_started);
        if remaining > 0. {
            thread::sleep(Duration::from_secs_f64(remaining));
        }
        // 限制推理启动频率，等待结束后取最新帧，不累积旧图像。
        if let Some(newest) = e.detection_input.lock().unwrap().take() {
            task = newest;
        }
        {
            let s = state().lock().unwrap();
            if !s.running || s.generation != task.generation {
                continue;
            }
        }
        let mut detector = e.detector.lock().unwrap();
        let Some(detector) = detector.as_mut() else {
            continue;
        };
        last_started = now();
        match detector.detect(&task.image, task.confidence) {
            Ok(boxes) => {
                *e.model_error.lock().unwrap() = None;
                let time = now();
                let fps = (1. / (time - last).max(0.001)) as f32;
                last = time;
                *e.detection_output.lock().unwrap() = DetectionOutput {
                    boxes,
                    time: task.time,
                    generation: task.generation,
                    fps,
                };
            }
            Err(error) => {
                *e.model_error.lock().unwrap() = Some(format!("识别失败：{error}"));
                last = now();
            }
        }
    }
}

// JNI 仅在回调期间借用 UVC 内存；队列内始终为 Rust 拥有的缓冲区。
#[no_mangle]
pub extern "system" fn Java_io_github_mcxiaochenn_stereorange_NativeBridge_submit(
    mut env: JNIEnv,
    _class: JClass,
    buffer: JByteBuffer,
    width: jint,
    height: jint,
) {
    let result = (|| -> anyhow::Result<()> {
        anyhow::ensure!(width == 640 && height == 240, "相机实际尺寸不是 640×240");
        let (running, demo, generation) = {
            let s = state().lock().unwrap();
            (s.running, s.demo, s.generation)
        };
        if !running || demo {
            return Ok(());
        }
        let len = 640 * 240 * 4;
        anyhow::ensure!(
            env.get_direct_buffer_capacity(&buffer)? == len,
            "RGBA 缓冲区长度不匹配"
        );
        let ptr = env.get_direct_buffer_address(&buffer)?;
        let e = engine();
        let mut bytes = e.pool.lock().unwrap().pop().unwrap_or_default();
        bytes.resize(len, 0);
        unsafe {
            bytes.copy_from_slice(std::slice::from_raw_parts(ptr, len));
        }
        let time = now();
        let mut rate = e.capture_interval.lock().unwrap();
        if rate.0 > 0. {
            rate.1 = (1. / (time - rate.0).max(0.001)) as f32;
        }
        rate.0 = time;
        drop(rate);
        let previous = e.input.lock().unwrap().replace(Input {
            bytes,
            time,
            generation,
        });
        if let Some(p) = previous {
            e.pool.lock().unwrap().push(p.bytes);
        }
        e.signal.notify_one();
        Ok(())
    })();
    if let Err(error) = result {
        let _ = env.throw_new("java/lang/IllegalArgumentException", error.to_string());
    }
}
#[no_mangle]
pub extern "system" fn Java_io_github_mcxiaochenn_stereorange_NativeBridge_copyPreview(
    mut env: JNIEnv,
    _class: JClass,
    buffer: JByteBuffer,
    view: jint,
) -> jstring {
    let result = (|| -> anyhow::Result<String> {
        let s = state().lock().unwrap();
        if !s.running || s.previews.is_empty() {
            return Ok(String::new());
        }
        let pixels = s
            .previews
            .get(view as usize)
            .ok_or_else(|| anyhow::anyhow!("未知画面"))?;
        anyhow::ensure!(
            env.get_direct_buffer_capacity(&buffer)? == pixels.len(),
            "预览缓冲区尺寸无效"
        );
        let ptr = env.get_direct_buffer_address(&buffer)?;
        unsafe {
            std::ptr::copy_nonoverlapping(pixels.as_ptr(), ptr, pixels.len());
        }
        Ok(serde_json::to_string(&s.result)?)
    })();
    match result {
        Ok(json) => env
            .new_string(json)
            .map(|s| s.into_raw())
            .unwrap_or(std::ptr::null_mut()),
        Err(error) => {
            let _ = env.throw_new("java/lang/IllegalStateException", error.to_string());
            std::ptr::null_mut()
        }
    }
}
