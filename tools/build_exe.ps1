# build_exe.ps1
# Packages the game into ONE file, GloryBowlGM.exe, and zips it, so you
# can send it to someone who doesn't have Python. Everything is inside the .exe,
# so it works even if they double-click it without unzipping first.
# Run it from the project folder with:
#     powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1
# Add -ErrorWindow for a test copy that opens a text window showing any error
# message (for when the game won't start on someone's PC):
#     powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1 -ErrorWindow
# Needs PyInstaller once:  python -m pip install pyinstaller
#
# The packaged game keeps its saves in Documents\Glory Bowl GM\saves (or an
# existing Documents\Front Office Football\saves from older copies;
# engine/saves.py). If its window doesn't appear within 30 seconds, it opens in
# the web browser instead (app.py). Your own saves are NOT included.
# The big temporary build files go in C:\Users\<you>\FOF-build (outside
# OneDrive, so OneDrive doesn't sync scratch files). The finished zip goes in
# the project's "dist" folder.

param([switch]$ErrorWindow)

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $env:USERPROFILE "FOF-build"
$name = "GloryBowlGM"
$zipName = $name
if ($ErrorWindow) { $zipName = "$name-ErrorWindow" }

Set-Location $project
$nicegui = python -c "import nicegui, os; print(os.path.dirname(nicegui.__file__))"

$windowArg = @("--windowed")
if ($ErrorWindow) { $windowArg = @("--console") }

$distDir = Join-Path $buildRoot "dist"
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force -Confirm:$false }

python -m PyInstaller app.py --name $name --onefile @windowArg --noconfirm --clean `
    --add-data "$nicegui;nicegui" `
    --workpath (Join-Path $buildRoot "work") `
    --distpath $distDir `
    --specpath $buildRoot
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (see the messages above)." }

# What goes in the zip: the .exe plus two small helper files.
$appDir = Join-Path $buildRoot "package\$name"
if (Test-Path $appDir) { Remove-Item $appDir -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory -Force $appDir | Out-Null
Copy-Item (Join-Path $distDir "$name.exe") $appDir

# Backup way to play if the game window won't open on someone's PC: the game
# opens in their web browser instead (Quit game on the main menu stops it).
Set-Content -Path (Join-Path $appDir "Play in browser (if the window won't open).bat") `
    -Value "@echo off`r`nstart `"`" `"%~dp0$name.exe`" --browser`r`n" -Encoding ascii -NoNewline

if ($ErrorWindow) {
    # Double-clicking this runs the game and keeps the text window open
    # afterwards, so any error message stays on screen for a screenshot.
    $bat = "@echo off`r`necho Starting Glory Bowl GM...`r`n`"%~dp0$name.exe`"`r`necho.`r`necho The game has stopped. If there's an error above, take a screenshot of this window.`r`npause`r`n"
    Set-Content -Path (Join-Path $appDir "START HERE - shows errors.bat") -Value $bat -Encoding ascii -NoNewline
}

$stamp = Get-Date -Format "yyyy-MM-dd"
$outDir = Join-Path $project "dist"
New-Item -ItemType Directory -Force $outDir | Out-Null
$zip = Join-Path $outDir "$zipName-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Confirm:$false }
Compress-Archive -Path $appDir -DestinationPath $zip
Write-Host "Done: $zip"
