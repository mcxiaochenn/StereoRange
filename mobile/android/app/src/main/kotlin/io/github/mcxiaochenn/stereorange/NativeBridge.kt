package io.github.mcxiaochenn.stereorange

import java.nio.ByteBuffer

/** 仅传递直接缓冲区；Rust 在回调返回前复制相机所有的内存。 */
object NativeBridge {
    init {
        System.loadLibrary("c++_shared")
        System.loadLibrary("opencv_java4")
        System.loadLibrary("onnxruntime")
        System.loadLibrary("stereorange_native")
    }
    @JvmStatic external fun submit(buffer: ByteBuffer, width: Int, height: Int)
    @JvmStatic external fun copyPreview(buffer: ByteBuffer, view: Int): String
}
