param(
    [ValidateSet('debug','release')][string]$Mode='debug',
    [string]$AndroidSdk='D:\Android\Sdk',
    [switch]$WithPrivateData,
    [switch]$PublicRelease,
    [string]$SigningDirectory='D:\Android\Signing\StereoRange'
)
$ErrorActionPreference='Stop'
$mobileRoot=Split-Path $PSScriptRoot -Parent
if($PublicRelease -and ($WithPrivateData -or $Mode -ne 'release')){throw '公开发布只允许 Release 模式，不能包含个人资源。'}
$savedSigning=@{}
foreach($name in @('STEREORANGE_KEYSTORE','STEREORANGE_STORE_PASSWORD','STEREORANGE_KEY_ALIAS','STEREORANGE_KEY_PASSWORD','STEREORANGE_PUBLIC_RELEASE')){
    $savedSigning[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
Push-Location $mobileRoot
try {
    $env:STEREORANGE_PUBLIC_RELEASE=if($PublicRelease){'true'}else{'false'}
    if($Mode -eq 'release'){
        if(!$env:STEREORANGE_KEYSTORE){
            $credentialPath=Join-Path $SigningDirectory 'credentials.clixml'
            if(!(Test-Path -LiteralPath $credentialPath)){throw '缺少正式签名配置。先执行 tool/initialize-signing.ps1 或提供 STEREORANGE 签名环境变量。'}
            $credential=Import-Clixml -LiteralPath $credentialPath
            $env:STEREORANGE_KEYSTORE=Join-Path $SigningDirectory 'release.p12'
            $env:STEREORANGE_KEY_ALIAS=$credential.UserName
            $env:STEREORANGE_STORE_PASSWORD=$credential.GetNetworkCredential().Password
            $env:STEREORANGE_KEY_PASSWORD=$env:STEREORANGE_STORE_PASSWORD
        }
        if(!(Test-Path -LiteralPath $env:STEREORANGE_KEYSTORE) -or !$env:STEREORANGE_KEY_ALIAS -or !$env:STEREORANGE_STORE_PASSWORD -or !$env:STEREORANGE_KEY_PASSWORD){throw '正式签名文件或密码配置不完整。'}
    }
    $flutterVersion=(& flutter --version --machine | ConvertFrom-Json).frameworkVersion
    if($flutterVersion -ne '3.47.1'){throw "需要 Flutter 3.47.1，当前为 $flutterVersion；请切换 SDK 后重试。"}
    # 仅影响本次进程，规避 Windows 长临时路径导致的 Java Unix Socket 错误。
    $javaTemp=Join-Path $mobileRoot '.native\java-tmp'
    New-Item -ItemType Directory -Force $javaTemp | Out-Null
    $env:JAVA_TOOL_OPTIONS="-Djdk.net.unixdomain.tmpdir=$javaTemp"
    & flutter pub get --enforce-lockfile
    if($LASTEXITCODE -ne 0){throw 'Flutter 依赖安装失败'}
    & "$PSScriptRoot\build-native.ps1" -AndroidSdk $AndroidSdk
    if($PublicRelease){ & "$PSScriptRoot\prepare-public.ps1" }
    elseif($WithPrivateData){ & "$PSScriptRoot\prepare-private.ps1" }
    elseif(Test-Path 'android\app\src\main\assets\private'){
        throw '检测到上次准备的私有资源。请明确使用 -WithPrivateData，或在全新工作区构建公共版本。'
    }
    & flutter analyze
    if($LASTEXITCODE -ne 0){throw 'Flutter 静态检查失败'}
    & flutter test test
    if($LASTEXITCODE -ne 0){throw 'Flutter 测试失败'}
    & cargo +1.98.0 test --manifest-path rust/Cargo.toml --locked
    if($LASTEXITCODE -ne 0){throw 'Rust 测试失败'}
    & flutter build apk "--$Mode" --target-platform android-arm64
    if($LASTEXITCODE -ne 0){throw 'APK 构建失败'}
    & "$PSScriptRoot\verify-apk.ps1" -Apk "build/app/outputs/flutter-apk/app-$Mode.apk" -AndroidSdk $AndroidSdk
    if($Mode -eq 'release'){
        & "$AndroidSdk\build-tools\36.0.0\apksigner.bat" verify --print-certs 'build/app/outputs/flutter-apk/app-release.apk'
        if($LASTEXITCODE -ne 0){throw '正式 APK 签名校验失败。'}
    }
    if($PublicRelease){
        $archive=[IO.Compression.ZipFile]::OpenRead((Resolve-Path 'build/app/outputs/flutter-apk/app-release.apk').Path)
        try {
            $privateEntries=@($archive.Entries | Where-Object {$_.FullName.StartsWith('assets/private/') -and $_.Length -gt 0})
            if($privateEntries.Count -ne 1 -or $privateEntries[0].FullName -ne 'assets/private/yolox_nano.onnx'){throw '公开 APK 模型资源检查失败。'}
            if(@($archive.Entries | Where-Object {$_.FullName -match '(?i)(calibration\.json|\.(npz|p12|jks|keystore))$'}).Count){throw '公开 APK 包含不允许发布的个人或签名文件。'}
        } finally {$archive.Dispose()}
        Write-Host '公开发布检查通过：只有官方识别模型，无个人标定和签名文件。'
    }
} finally {
    foreach($name in $savedSigning.Keys){[Environment]::SetEnvironmentVariable($name,$savedSigning[$name],'Process')}
    Pop-Location
}
