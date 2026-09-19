param([string]$AndroidSdk = 'D:\Android\Sdk', [ValidateSet('arm64-v8a','x86_64')][string]$Abi='arm64-v8a', [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path $PSScriptRoot -Parent
$cache = Join-Path $mobileRoot '.native'
$triple = if ($Abi -eq 'arm64-v8a') { 'aarch64-linux-android' } else { 'x86_64-linux-android' }
$ndk = Join-Path $AndroidSdk 'ndk\28.2.13676358'
$bin = Join-Path $ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin'
if (!(Test-Path "$bin\clang.exe")) { throw '缺少 Android NDK 28.2.13676358，请通过 Android Studio SDK Manager 安装。' }
New-Item -ItemType Directory -Force $cache | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Fetch-Aar([string]$Name, [string]$Url) {
    $archive = Join-Path $cache "$Name.aar"
    if (!(Test-Path $archive)) { Invoke-WebRequest $Url -OutFile $archive }
    $expected = (Invoke-RestMethod "$Url.sha256").ToString().Trim().Split(' ')[0]
    if ((Get-FileHash $archive -Algorithm SHA256).Hash -ne $expected) { throw "$Name 下载校验失败，请检查缓存文件。" }
    $destination = Join-Path $cache $Name
    if (!(Test-Path $destination)) { [IO.Compression.ZipFile]::ExtractToDirectory($archive, $destination) }
    return $destination
}
$opencv = Fetch-Aar 'opencv' 'https://repo.maven.apache.org/maven2/org/opencv/opencv/4.12.0/opencv-4.12.0.aar'
$ort = Fetch-Aar 'onnxruntime' 'https://repo.maven.apache.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/1.22.0/onnxruntime-android-1.22.0.aar'
$clangDir = Join-Path $cache 'clang'
if (!(Test-Path $clangDir)) {
    $package = Invoke-RestMethod 'https://pypi.org/pypi/libclang/18.1.1/json'
    $wheel = $package.urls | Where-Object { $_.filename -eq 'libclang-18.1.1-py2.py3-none-win_amd64.whl' } | Select-Object -First 1
    $archive = Join-Path $cache $wheel.filename
    if (!(Test-Path $archive)) { Invoke-WebRequest $wheel.url -OutFile $archive }
    if ((Get-FileHash $archive -Algorithm SHA256).Hash -ne $wheel.digests.sha256) { throw 'libclang 下载校验失败。' }
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $clangDir)
}
$nativeOut = Join-Path $mobileRoot "android\app\src\main\jniLibs\$Abi"
New-Item -ItemType Directory -Force $nativeOut | Out-Null
Copy-Item -LiteralPath "$opencv\jni\$Abi\libopencv_java4.so" -Destination $nativeOut
Copy-Item -LiteralPath "$ort\jni\$Abi\libonnxruntime.so" -Destination $nativeOut
Copy-Item -LiteralPath "$ndk\toolchains\llvm\prebuilt\windows-x86_64\sysroot\usr\lib\$triple\libc++_shared.so" -Destination $nativeOut
if ($PrepareOnly) { return }
$env:LIBCLANG_PATH = "$clangDir\libclang-18.1.1.data\platlib\clang\native"
$env:PATH = "$bin;$env:PATH"
$env:CLANG_PATH = "$bin\${triple}33-clang.cmd"
$env:OPENCV_INCLUDE_PATHS = "$opencv\prefab\modules\opencv_java4\include"
$env:OPENCV_LINK_PATHS = "$opencv\jni\$Abi"
$env:OPENCV_LINK_LIBS = 'opencv_java4'
$env:OPENCV_DISABLE_PROBES = 'pkg_config,cmake,vcpkg_cmake,vcpkg'
$sysroot = "$ndk/toolchains/llvm/prebuilt/windows-x86_64/sysroot".Replace('\','/')
$env:OPENCV_CLANG_ARGS = "--target=${triple}33 --sysroot=$sysroot -I$sysroot/usr/include/c++/v1 -isystem $sysroot/usr/include/$triple"
$suffix = $triple.Replace('-','_')
Set-Item "Env:CC_$suffix" "$bin\${triple}33-clang.cmd"
Set-Item "Env:CXX_$suffix" "$bin\${triple}33-clang++.cmd"
Set-Item "Env:AR_$suffix" "$bin\llvm-ar.exe"
Set-Item "Env:CARGO_TARGET_$($suffix.ToUpper())_LINKER" "$bin\${triple}33-clang.cmd"
Set-Item "Env:CARGO_TARGET_$($suffix.ToUpper())_RUSTFLAGS" '-C link-arg=-Wl,-z,max-page-size=16384 -C link-arg=-Wl,-z,common-page-size=16384'
& cargo +1.98.0 build --manifest-path "$mobileRoot\rust\Cargo.toml" --locked --target $triple --release
if ($LASTEXITCODE -ne 0) { throw 'Rust Android 构建失败。' }
Copy-Item -LiteralPath "$mobileRoot\rust\target\$triple\release\libstereorange_native.so" -Destination $nativeOut
Write-Host 'Rust / OpenCV / ONNX 原生库已准备完成。'
