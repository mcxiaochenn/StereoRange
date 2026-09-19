param([Parameter(Mandatory)][string]$Apk,[string]$AndroidSdk='D:\Android\Sdk')
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $Apk).Path
$buildTools = if ($env:ANDROID_BUILD_TOOLS) { $env:ANDROID_BUILD_TOOLS } else { '36.0.0' }
$ndkVersion = if ($env:ANDROID_NDK_VERSION) { $env:ANDROID_NDK_VERSION } else { '28.2.13676358' }
& "$AndroidSdk\build-tools\$buildTools\zipalign.exe" -c -P 16 -v 4 $resolved
if($LASTEXITCODE -ne 0){throw 'APK ZIP 16 KB 对齐检查失败'}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('stereorange-elf-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $temporary | Out-Null
$archive=[IO.Compression.ZipFile]::OpenRead($resolved)
$readelf="$AndroidSdk\ndk\$ndkVersion\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-readelf.exe"
if (!(Test-Path $readelf)) { throw "找不到 llvm-readelf：$readelf" }
try {
    $libraries=@($archive.Entries | Where-Object {$_.FullName -match '^lib/[^/]+/[^/]+\.so$'})
    if(!$libraries.Count){throw 'APK 中没有原生库'}
    foreach($entry in $libraries){
        $path=Join-Path $temporary $entry.Name
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$true)
        $segments=& $readelf -lW $path
        if($LASTEXITCODE -ne 0){throw "ELF 解析失败：$($entry.FullName)"}
        foreach($line in $segments){
            if($line -match '^\s*LOAD\s+.*\s+(0x[0-9a-fA-F]+)\s*$'){
                if([Convert]::ToInt64($Matches[1].Substring(2),16) -lt 16384){throw "ELF LOAD 段不满足 16 KB 对齐：$($entry.FullName)"}
            }
        }
        Write-Host "16 KB ELF 通过：$($entry.FullName)"
    }
} finally {$archive.Dispose()}
# 保留本次独立临时目录便于复查，不删除其他文件。
Write-Host "APK SHA-256：$((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash)"
