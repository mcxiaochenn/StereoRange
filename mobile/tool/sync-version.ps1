param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$OverrideTag,
    [switch]$WriteOnly
)
$ErrorActionPreference = 'Stop'
$versionPath = Join-Path $RepoRoot 'VERSION'
$pubspecPath = Join-Path $RepoRoot 'mobile/pubspec.yaml'
if (!(Test-Path -LiteralPath $versionPath)) { throw "缺少版本源文件：$versionPath" }
if (!(Test-Path -LiteralPath $pubspecPath)) { throw "缺少 pubspec：$pubspecPath" }

# 约定：人工只维护/打 tag vX.Y.Z；+提交次数一律由脚本自动附加。
$base = ((Get-Content -LiteralPath $versionPath -Raw) -split "`r?`n" | Where-Object { $_ -and $_ -notmatch '^\s*#' } | Select-Object -First 1).Trim()
if ($base -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION 中的语义版本非法（应为 X.Y.Z）：$base"
}
$replaced = $null
if ($OverrideTag) {
    if ($OverrideTag -match '\+') {
        throw "tag 请只使用 vX.Y.Z，不要带提交次数：$OverrideTag（+N 由构建脚本自动附加）"
    }
    if ($OverrideTag -notmatch '^v(\d+\.\d+\.\d+)$') {
        throw "版本 tag 非法，应形如 v1.0.2：$OverrideTag"
    }
    $tagBase = $Matches[1]
    if ($tagBase -ne $base) {
        $replaced = "$base -> $tagBase"
        $base = $tagBase
        Set-Content -LiteralPath $versionPath -Value $base -Encoding ascii -NoNewline
        Write-Host "源码版本与 tag 不一致，已替换 VERSION：$replaced"
    } else {
        Write-Host "源码版本与 tag 一致：$base"
    }
}

Push-Location $RepoRoot
try {
    $count = [int](git rev-list --count HEAD)
} finally { Pop-Location }

$full = "$base+$count"
$releaseTag = "v$base"
$pubspecRaw = Get-Content -LiteralPath $pubspecPath -Raw
if ($pubspecRaw -notmatch '(?m)^version:\s*.+$') {
    throw "pubspec.yaml 中找不到 version 字段"
}
$newPubspec = [regex]::Replace($pubspecRaw, '(?m)^version:\s*.+$', "version: $full")
if ($newPubspec -ne $pubspecRaw) {
    Set-Content -LiteralPath $pubspecPath -Value $newPubspec -Encoding utf8 -NoNewline
    Write-Host "已同步 pubspec version: $full"
} else {
    Write-Host "pubspec version 已是 $full"
}
Write-Host "产品版本：$full（release tag $releaseTag，versionCode $count=git提交数）"
if ($env:GITHUB_OUTPUT) {
    "base=$base" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    "code=$count" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    "full=$full" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    "release_tag=$releaseTag" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    "build_label=v$full" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    if ($replaced) { "replaced=$replaced" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8 }
}
if ($WriteOnly) { return }
Write-Host "Base=$base Code=$count Full=$full ReleaseTag=$releaseTag"
exit 0
