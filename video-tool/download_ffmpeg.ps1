$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ffmpegDir = Join-Path $PSScriptRoot "ffmpeg"
$binDir = Join-Path $ffmpegDir "bin"
$zipFile = Join-Path $ffmpegDir "ffmpeg.zip"
$extractDir = Join-Path $ffmpegDir "extract"

if (Test-Path (Join-Path $binDir "ffmpeg.exe")) {
    Write-Host "FFmpeg al aanwezig in $binDir"
    exit 0
}

New-Item -ItemType Directory -Path $binDir -Force | Out-Null

Write-Host "Downloaden van FFmpeg..."
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zipFile

Write-Host "Uitpakken..."
Expand-Archive -Path $zipFile -DestinationPath $extractDir -Force

$subDir = Get-ChildItem $extractDir -Directory | Select-Object -First 1
Copy-Item -Path (Join-Path $subDir.FullName "bin\*") -Destination $binDir -Force -Recurse

Remove-Item $extractDir -Recurse -Force
Remove-Item $zipFile -Force

Write-Host "FFmpeg geinstalleerd in $binDir"
