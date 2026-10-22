# build_exe.ps1
# Packages the game into a folder with FrontOfficeFootball.exe inside, then
# zips it, so you can send it to someone who doesn't have Python.
# Run it from the project folder with:
#     powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1
# Add -ErrorWindow for a test copy that opens a text window showing any error
# message (for when the game won't start on someone's PC):
#     powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1 -ErrorWindow
# Needs PyInstaller once:  python -m pip install pyinstaller
#
# The big temporary build files go in C:\Users\<you>\FOF-build (outside
# OneDrive, so OneDrive doesn't sync hundreds of MB of scratch files). The
# finished zip goes in the project's "dist" folder. Your own saves are NOT
# included: the packaged game starts with an empty "saves" folder next to the .exe.

param([switch]$ErrorWindow)

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $env:USERPROFILE "FOF-build"
$name = "FrontOfficeFootball"
$zipName = $name
if ($ErrorWindow) { $zipName = "$name-ErrorWindow" }

Set-Location $project
$nicegui = python -c "import nicegui, os; print(os.path.dirname(nicegui.__file__))"

$windowArg = @("--windowed")
if ($ErrorWindow) { $windowArg = @("--console") }

python -m PyInstaller app.py --name $name @windowArg --noconfirm --clean `
    --add-data "$nicegui;nicegui" `
    --workpath (Join-Path $buildRoot "work") `
    --distpath (Join-Path $buildRoot "dist") `
    --specpath $buildRoot
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (see the messages above)." }

$appDir = Join-Path $buildRoot "dist\$name"
New-Item -ItemType Directory -Force (Join-Path $appDir "saves") | Out-Null

# Backup way to play if the game window won't open on someone's PC: the game
# opens in their web browser instead (Quit game on the main menu stops it).
Set-Content -Path (Join-Path $appDir "Play in browser (if the window won't open).bat") `
    -Value "@echo off`r`nstart `"`" `"%~dp0$name.exe`" --browser`r`n" -Encoding ascii -NoNewline

if ($ErrorWindow) {
    # Double-clicking this runs the game and keeps the text window open
    # afterwards, so any error message stays on screen for a screenshot.
    $bat = "@echo off`r`necho Starting Front Office Football...`r`n`"%~dp0$name.exe`"`r`necho.`r`necho The game has stopped. If there's an error above, take a screenshot of this window.`r`npause`r`n"
    Set-Content -Path (Join-Path $appDir "START HERE - shows errors.bat") -Value $bat -Encoding ascii -NoNewline
}

$stamp = Get-Date -Format "yyyy-MM-dd"
$outDir = Join-Path $project "dist"
New-Item -ItemType Directory -Force $outDir | Out-Null
$zip = Join-Path $outDir "$zipName-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Confirm:$false }
Compress-Archive -Path $appDir -DestinationPath $zip
Write-Host "Done: $zip"
