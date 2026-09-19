package io.github.mcxiaochenn.stereorange

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.content.pm.PackageManager
import android.graphics.*
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.hardware.usb.UsbConstants
import android.os.Handler
import android.os.HandlerThread
import android.view.WindowManager
import com.herohan.uvcapp.CameraHelper
import com.herohan.uvcapp.CameraException
import com.herohan.uvcapp.ICameraHelper
import com.serenegiant.usb.Size
import com.serenegiant.usb.UVCCamera
import com.serenegiant.utils.UVCUtils
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import io.flutter.view.TextureRegistry
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer

class MainActivity : FlutterActivity() {
    private var helper: CameraHelper? = null
    private var events: EventChannel.EventSink? = null
    private var producer: TextureRegistry.SurfaceProducer? = null
    private val renderThread = HandlerThread("StereoRange-preview")
    private lateinit var render: Handler
    private val main = Handler(android.os.Looper.getMainLooper())
    private var permissionReply: MethodChannel.Result? = null
    private var documentReply: MethodChannel.Result? = null
    private var exportImage: Bitmap? = null
    @Volatile private var active = false
    @Volatile private var view = 0
    @Volatile private var showBoxes = true
    @Volatile private var showPoints = true
    @Volatile private var foreground = true
    @Volatile private var wantedCamera = false
    private var fallback = false
    private var cameraLabel = "未连接 USB 相机"

    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        UVCUtils.init(applicationContext)
        renderThread.start()
        render = Handler(renderThread.looper)
        EventChannel(engine.dartExecutor.binaryMessenger, "stereorange/device").setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, sink: EventChannel.EventSink) { events = sink; emit("idle", cameraLabel) }
            override fun onCancel(arguments: Any?) { events = null }
        })
        MethodChannel(engine.dartExecutor.binaryMessenger, "stereorange/android").setMethodCallHandler { call, reply ->
            try {
                when (call.method) {
                    "openRepository" -> {
                        val repository = Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/mcxiaochenn/StereoRange"))
                            .addCategory(Intent.CATEGORY_BROWSABLE)
                        // 先解析通用网页的默认浏览器，避免仓库链接被 GitHub 客户端接管。
                        val browser = Intent(Intent.ACTION_VIEW, Uri.parse("https://example.com"))
                            .addCategory(Intent.CATEGORY_BROWSABLE)
                            .resolveActivity(packageManager)
                        if (browser != null && browser.packageName != "android") repository.setPackage(browser.packageName)
                        try { startActivity(repository); reply.success(null) }
                        catch (_: android.content.ActivityNotFoundException) { reply.error("browser", "未找到浏览器，请先安装或设置默认浏览器", null) }
                    }
                    "prepare" -> {
                        if (producer == null) {
                            producer = engine.renderer.createSurfaceProducer().also { it.setSize(320, 240) }
                        }
                        // 资源文件只存于应用私有目录，不需要存储权限。
                        val model = File(filesDir, "yolox_nano.onnx")
                        try { assets.open("private/yolox_nano.onnx").use { src -> model.outputStream().use { src.copyTo(it) } } } catch (_: java.io.FileNotFoundException) { }
                        val saved = File(filesDir, "calibration.json")
                        val calibration = if (saved.isFile) saved.readText() else try { assets.open("private/calibration.json").bufferedReader().use { it.readText() } } catch (_: java.io.FileNotFoundException) { null }
                        val hasCamera=(getSystemService(USB_SERVICE) as UsbManager).deviceList.values.any { device -> (0 until device.interfaceCount).any { device.getInterface(it).interfaceClass==UsbConstants.USB_CLASS_VIDEO } }
                        reply.success(mapOf("textureId" to producer!!.id(), "modelPath" to model.absolutePath, "runtimePath" to "libonnxruntime.so", "calibration" to calibration, "hasCamera" to hasCamera))
                    }
                    "connect" -> {
                        if (permissionReply != null) { reply.error("busy", "正在等待相机权限", null) }
                        else if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                            permissionReply = reply
                            requestPermissions(arrayOf(Manifest.permission.CAMERA), 101)
                        } else { connect(); reply.success(null) }
                    }
                    "disconnect" -> { disconnect(); reply.success(null) }
                    "render" -> {
                        active = call.argument<Boolean>("active") == true
                        if (active) { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON); render.removeCallbacks(pump); render.post(pump) }
                        else { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON); render.removeCallbacks(pump) }
                        reply.success(null)
                    }
                    "view" -> { view = (call.argument<Int>("index") ?: 0).coerceIn(0,3); showBoxes=call.argument<Boolean>("boxes") ?: true; showPoints=call.argument<Boolean>("points") ?: true; reply.success(null) }
                    "importCalibration" -> {
                        if (documentReply != null) { reply.error("busy", "请先完成当前文件操作", null) }
                        else { documentReply=reply; startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { type="*/*"; addCategory(Intent.CATEGORY_OPENABLE) },201) }
                    }
                    "saveCalibration" -> { File(filesDir,"calibration.json").writeText(call.argument<String>("json") ?: error("缺少标定内容")); reply.success(null) }
                    "screenshot" -> {
                        if (documentReply != null) { reply.error("busy","请先完成当前文件操作",null) }
                        else {
                            documentReply=reply
                            render.post {
                                try {
                                    val frame=readPreview() ?: error("暂无可截图的实时画面")
                                    val image=makeScreenshot(frame.first,frame.second)
                                    main.post { exportImage=image; startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {type="image/png";addCategory(Intent.CATEGORY_OPENABLE);putExtra(Intent.EXTRA_TITLE,"StereoRange-${System.currentTimeMillis()}.png")},202) }
                                } catch (e:Exception) { main.post { documentReply?.error("screenshot",e.message,null);documentReply=null } }
                            }
                        }
                    }
                    else -> reply.notImplemented()
                }
            } catch (e:Throwable) { reply.error("native", e.message ?: "Android 操作失败", null) }
        }
    }
    private fun emit(state:String,message:String) { main.post { events?.success(mapOf("state" to state,"message" to message)) } }
    private fun connect() {
        disconnect(); wantedCamera=true; fallback=false
        helper=CameraHelper().also { camera ->
            camera.setStateCallback(object : ICameraHelper.StateCallback {
                override fun onAttach(device:UsbDevice) {
                    if(helper !== camera) return
                    val video=(0 until device.interfaceCount).any { device.getInterface(it).interfaceClass==UsbConstants.USB_CLASS_VIDEO }
                    if(wantedCamera && foreground && video && !camera.isCameraOpened) camera.selectDevice(device)
                }
                override fun onDeviceOpen(device:UsbDevice,isFirstOpen:Boolean) { if(helper === camera && wantedCamera) openRequested(camera) }
                override fun onCameraOpen(device:UsbDevice) {
                    if(helper !== camera) return
                    if(!wantedCamera || !foreground) { camera.closeCamera(); return }
                    val size=camera.previewSize
                    if(size==null || size.width!=640 || size.height!=240) { emit("error","相机未提供 640×240 双目画面，请检查设备与模式"); disconnect(); return }
                    camera.setFrameCallback({ buffer ->
                        try { if(helper === camera && wantedCamera && foreground) NativeBridge.submit(buffer,640,240) }
                        catch(e:Throwable) { emit("error","读取相机帧失败：${e.message}");main.post { disconnect() } }
                    },UVCCamera.PIXEL_FORMAT_RGBX)
                    camera.startPreview()
                    cameraLabel="${device.productName ?: "USB 双目相机"} · 640×240 @ ${size.fps}"
                    emit("connected",cameraLabel)
                }
                override fun onCameraClose(device:UsbDevice) { if(helper === camera && wantedCamera) emit("disconnected","相机已停止，请重连") }
                override fun onDeviceClose(device:UsbDevice) { if(helper === camera && wantedCamera) emit("disconnected","USB 设备已关闭") }
                override fun onDetach(device:UsbDevice) { if(helper === camera && wantedCamera) { emit("disconnected","相机已拔出，请连接后重试");disconnect() } }
                override fun onCancel(device:UsbDevice) { if(helper !== camera) return;wantedCamera=false;emit("error","USB 访问未获授权，请点击重试并允许访问") }
                override fun onError(device:UsbDevice,e:CameraException) {
                    if(helper !== camera) return
                    if(!fallback && wantedCamera) { fallback=true;openRequested(camera) }
                    else { emit("error","无法打开双目相机：${e.message}，请检查 OTG 供电或重插");disconnect() }
                }
            })
        }
        emit("connecting","正在查找 USB 双目相机并申请授权")
        main.postDelayed({ if(wantedCamera && helper?.isCameraOpened!=true && helper?.deviceList.isNullOrEmpty()) emit("error","未发现 USB 相机，请连接支持数据传输的 OTG 转接器") },2000)
    }
    private fun openRequested(camera:CameraHelper) {
        val type=if(fallback) UVCCamera.UVC_VS_FRAME_UNCOMPRESSED else UVCCamera.UVC_VS_FRAME_MJPEG
        camera.openCamera(Size(type,640,240,30,arrayListOf(30)))
    }
    private fun disconnect() { wantedCamera=false;helper?.release();helper=null;cameraLabel="未连接 USB 相机" }
    override fun onRequestPermissionsResult(code:Int, permissions:Array<out String>, results:IntArray) {
        super.onRequestPermissionsResult(code,permissions,results)
        if(code==101) {
            val reply=permissionReply;permissionReply=null
            if(results.firstOrNull()==PackageManager.PERMISSION_GRANTED) { connect();reply?.success(null) }
            else reply?.error("permission","需要相机权限才能读取 USB 双目相机，可在系统设置中允许",null)
        }
    }
    private val pixels=ByteBuffer.allocateDirect(320*240*4)
    private val preview=Bitmap.createBitmap(320,240,Bitmap.Config.ARGB_8888)
    private fun readPreview():Pair<Bitmap,JSONObject>? {
        val json=NativeBridge.copyPreview(pixels,view)
        if(json.isEmpty()) return null
        pixels.rewind();preview.copyPixelsFromBuffer(pixels)
        return preview to JSONObject(json)
    }
    private val pump=object:Runnable {
        override fun run() {
            if(!active || !foreground) return
            try {
                val frame=readPreview()
                val surface=producer?.surface
                if(frame!=null && surface?.isValid==true) {
                    val canvas=surface.lockCanvas(null)
                    try { canvas.drawBitmap(frame.first,null,Rect(0,0,canvas.width,canvas.height),null) } finally { surface.unlockCanvasAndPost(canvas) }
                }
            } catch(e:Throwable) { active=false;emit("error","画面显示失败：${e.message}") }
            if(active) render.postDelayed(this,33)
        }
    }
    private fun makeScreenshot(bitmap:Bitmap,frame:JSONObject):Bitmap {
        val image=Bitmap.createBitmap(1280,1040,Bitmap.Config.ARGB_8888); val c=Canvas(image)
        c.drawColor(Color.rgb(15,23,28));c.drawBitmap(bitmap,null,Rect(0,0,1280,960),Paint(Paint.FILTER_BITMAP_FLAG))
        val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize=26f; strokeWidth=4f }
        if(view!=1 && showBoxes) {
            val boxes=frame.getJSONArray("detections")
            for(i in 0 until boxes.length()) {
                val d=boxes.getJSONObject(i);val b=d.getJSONArray("bbox");paint.color=Color.rgb(115,220,177);paint.style=Paint.Style.STROKE
                c.drawRect(b.getInt(0)*4f,b.getInt(1)*4f,b.getInt(2)*4f,b.getInt(3)*4f,paint);paint.style=Paint.Style.FILL
                val distance=if(d.isNull("distance_m")) "距离不可用" else "%.2f m".format(d.getDouble("distance_m"))
                c.drawText("${d.getString("label")} | ${"%.0f%%".format(d.getDouble("confidence")*100)} | $distance",b.getInt(0)*4f,(b.getInt(1)*4f+30).coerceAtMost(950f),paint)
            }
        }
        if(view!=1 && showPoints) {
            val points=frame.getJSONArray("points")
            for(i in 0 until points.length()) {
                val p=points.getJSONObject(i);val kind=p.getString("kind");paint.color=when(kind){"nearest"->Color.rgb(255,120,80);"center"->Color.CYAN;else->Color.rgb(156,145,255)}
                val x=p.getDouble("x").toFloat()*4;val y=p.getDouble("y").toFloat()*4;c.drawCircle(x,y,10f,paint)
                c.drawText("%.2f m".format(p.getDouble("distance_m")),x.coerceAtMost(1140f),(y+35).coerceAtMost(950f),paint)
            }
        }
        paint.color=Color.WHITE;c.drawText("StereoRange · ${if(frame.getBoolean("demo")) "模拟演示" else "双目测距"} · 平湖技师学院 / 陆逸尘 / ChenDusk",20f,1010f,paint)
        return image
    }
    @Deprecated("Android 文件选择回调")
    override fun onActivityResult(code:Int,result:Int,data:Intent?) {
        super.onActivityResult(code,result,data)
        if(code!=201 && code!=202) return
        val reply=documentReply;documentReply=null
        try {
            val uri=data?.data
            if(result!=RESULT_OK || uri==null) {reply?.success(null);return}
            if(code==201) {
                val bytes=contentResolver.openInputStream(uri)?.use {it.readNBytes(262145)} ?: error("无法读取文件")
                require(bytes.size<=262144){"标定文件过大，请选择导出的 JSON"};reply?.success(bytes.toString(Charsets.UTF_8))
            } else {
                contentResolver.openOutputStream(uri)?.use {requireNotNull(exportImage).compress(Bitmap.CompressFormat.PNG,100,it)} ?: error("无法保存截图")
                reply?.success("截图已保存")
            }
        } catch(e:Exception) {reply?.error("file",e.message,null)} finally {exportImage?.recycle();exportImage=null}
    }
    override fun onStart() {super.onStart();foreground=true}
    override fun onStop() {foreground=false;active=false;disconnect();if(::render.isInitialized) render.removeCallbacks(pump);super.onStop()}
    override fun onDestroy() {
        active=false;disconnect();permissionReply?.error("closed","页面已关闭",null);documentReply?.error("closed","页面已关闭",null)
        if(::render.isInitialized) render.removeCallbacksAndMessages(null)
        renderThread.quitSafely();producer?.release();super.onDestroy()
    }
}
