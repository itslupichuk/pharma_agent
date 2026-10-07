# RXTERM installer for Windows (PowerShell).
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/itslupichuk/pharma_agent/HEAD/scripts/install_windows.ps1 | iex"
# Installs to %USERPROFILE%\RXTERM and puts an RXTERM shortcut on the Desktop and in the Start menu.
# Re-run any time to update.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Repo = "itslupichuk/pharma_agent"
$AppDir = Join-Path $env:USERPROFILE "RXTERM"
function Step($m) { Write-Host "> $m" -ForegroundColor DarkYellow }

Write-Host "`n  RXTERM  pharma & biotech trading terminal - installer`n" -ForegroundColor DarkYellow

Step "Downloading RXTERM..."
$Tmp = Join-Path $env:TEMP ("rxterm_" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Tmp | Out-Null
Invoke-WebRequest "https://codeload.github.com/$Repo/zip/HEAD" -OutFile "$Tmp\rxterm.zip"
Expand-Archive "$Tmp\rxterm.zip" -DestinationPath $Tmp
$Src = Get-ChildItem $Tmp -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Get-ChildItem $AppDir -Force | Where-Object { $_.Name -notin @(".venv", ".env", "out") } | Remove-Item -Recurse -Force
Copy-Item -Path (Join-Path $Src.FullName "*") -Destination $AppDir -Recurse -Force

$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv) {
  Step "Installing uv (Python manager)..."
  $env:UV_NO_MODIFY_PATH = "1"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
  $Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
}

Step "Setting up Python 3.12 and dependencies (first run takes ~1 minute)..."
Push-Location $AppDir
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $Uv venv --quiet --python 3.12 .venv }
& $Uv pip install --quiet --python .venv\Scripts\python.exe -e .
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
Pop-Location

Step "Creating shortcuts..."
$Launcher = Join-Path $AppDir "rxterm.cmd"
Set-Content -Path $Launcher -Encoding ASCII -Value "@echo off`r`ntitle RXTERM`r`ncd /d `"%USERPROFILE%\RXTERM`"`r`n.venv\Scripts\rxterm.exe %*`r`n"
$Wt = (Get-Command wt.exe -ErrorAction SilentlyContinue).Source
$Shell = New-Object -ComObject WScript.Shell
$Targets = @([Environment]::GetFolderPath("Desktop"), (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))
foreach ($dir in $Targets) {
  $lnk = $Shell.CreateShortcut((Join-Path $dir "RXTERM.lnk"))
  if ($Wt) {
    $lnk.TargetPath = $Wt
    $lnk.Arguments = "--title RXTERM --size 200,56 `"$Launcher`""
  } else {
    $lnk.TargetPath = "$env:WINDIR\System32\cmd.exe"
    $lnk.Arguments = "/c mode con: cols=200 lines=56 & `"$Launcher`""
  }
  $lnk.WorkingDirectory = $AppDir
  $lnk.IconLocation = (Join-Path $AppDir "assets\rxterm.ico")
  $lnk.Description = "RXTERM pharma & biotech trading terminal"
  $lnk.Save()
}
Remove-Item $Tmp -Recurse -Force

Write-Host "`nRXTERM installed." -ForegroundColor Green
Write-Host "  Double-click RXTERM on your Desktop (or find it in the Start menu)."
Write-Host "  Best in Windows Terminal with a dark theme. Re-run this installer to update.`n"
