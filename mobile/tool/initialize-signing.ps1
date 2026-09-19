param([string]$Directory='D:\Android\Signing\StereoRange',[string]$Keytool='D:\rj\Android\Android Studio\jbr\bin\keytool.exe')
$ErrorActionPreference='Stop'
$keyPath=Join-Path $Directory 'release.p12'
$credentialPath=Join-Path $Directory 'credentials.clixml'
if((Test-Path -LiteralPath $keyPath) -or (Test-Path -LiteralPath $credentialPath)){throw '签名文件已存在，不覆盖。'}
if(!(Test-Path -LiteralPath $Keytool)){throw '未找到 JDK keytool。'}
New-Item -ItemType Directory -Force $Directory | Out-Null
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $Directory /inheritance:r /grant:r "*${sid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){throw '签名目录权限设置失败'}
$bytes=[byte[]]::new(32)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$secure=ConvertTo-SecureString ([Convert]::ToBase64String($bytes)) -AsPlainText -Force
$credential=[pscredential]::new('stereorange-release',$secure)
# DPAPI 仅允许本机当前 Windows 用户解密；密码不写入日志或 Git。
$credential | Export-Clixml -LiteralPath $credentialPath -NoClobber
$env:STEREORANGE_KEY_PASSWORD=$credential.GetNetworkCredential().Password
try {
    & $Keytool -genkeypair -noprompt -storetype PKCS12 -keystore $keyPath -alias 'stereorange-release' -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=ChenDusk, OU=StereoRange, O=Pinghu Technician College, C=CN' -storepass:env STEREORANGE_KEY_PASSWORD -keypass:env STEREORANGE_KEY_PASSWORD
    if($LASTEXITCODE -ne 0){throw '密钥生成失败，请检查已生成文件后人工处理；不会自动覆盖。'}
} finally {Remove-Item Env:STEREORANGE_KEY_PASSWORD -ErrorAction SilentlyContinue}
Write-Host "签名已创建：$keyPath；请备份密钥，并在换机前安全导出密码。"
