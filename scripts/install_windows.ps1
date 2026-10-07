# RXTERM installer for Windows.
#   Open PowerShell and run:
#   irm https://raw.githubusercontent.com/itslupichuk/pharma_agent/HEAD/scripts/install_windows.ps1 | iex
# Installs to %USERPROFILE%\RXTERM, puts an RXTERM shortcut (with icon) on the Desktop and in the
# Start menu, and adds an `rxterm` command. Re-run any time to update — watchlist and settings are kept.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

$Repo = "itslupichuk/pharma_agent"
$OnWindows = ($PSVersionTable.PSEdition -eq "Desktop") -or $IsWindows
$UserHome = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$AppDir = Join-Path $UserHome "RXTERM"
function Step($m) { Write-Host "> $m" -ForegroundColor DarkYellow }

Write-Host ""
Write-Host "  RXTERM  " -ForegroundColor Black -BackgroundColor DarkYellow -NoNewline
Write-Host "  pharma & biotech trading terminal - installer"
Write-Host ""

# 1. Code ---------------------------------------------------------------
Step "Downloading RXTERM..."
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("rxterm_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
Invoke-WebRequest "https://codeload.github.com/$Repo/zip/HEAD" -OutFile (Join-Path $Tmp "rxterm.zip") -UseBasicParsing
Expand-Archive (Join-Path $Tmp "rxterm.zip") -DestinationPath $Tmp -Force
$Src = Get-ChildItem $Tmp -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Get-ChildItem $AppDir -Force | Where-Object { $_.Name -notin @(".venv", ".env", "out") } | Remove-Item -Recurse -Force
Copy-Item -Path (Join-Path $Src.FullName "*") -Destination $AppDir -Recurse -Force
Get-ChildItem $Src.FullName -Force -Filter ".*" | Copy-Item -Destination $AppDir -Recurse -Force

# 2. Python via uv (brings its own Python 3.12; nothing system-wide) ---------
$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv) {
  Step "Installing uv (Python manager)..."
  $env:UV_NO_MODIFY_PATH = "1"
  if ($OnWindows) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
    $Uv = Join-Path $UserHome ".local\bin\uv.exe"
  } else {
    sh -c "curl -LsSf https://astral.sh/uv/install.sh | sh" | Out-Null
    $Uv = Join-Path $UserHome ".local/bin/uv"
  }
}
if (-not (Test-Path $Uv)) { throw "uv was not installed correctly ($Uv not found)." }

Step "Setting up Python 3.12 and dependencies (first run takes ~1 minute)..."
$VenvPy = if ($OnWindows) { Join-Path $AppDir ".venv\Scripts\python.exe" } else { Join-Path $AppDir ".venv/bin/python" }
Push-Location $AppDir
try {
  if (-not (Test-Path $VenvPy)) { & $Uv venv --quiet --python 3.12 .venv; if ($LASTEXITCODE) { throw "uv venv failed" } }
  & $Uv pip install --quiet --python $VenvPy -e .
  if ($LASTEXITCODE) { throw "dependency install failed" }
  if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
} finally { Pop-Location }

# 3. Launcher + shortcuts ----------------------------------------------------
if ($OnWindows) {
  Step "Creating Desktop and Start-menu shortcuts..."
  $Launcher = Join-Path $AppDir "rxterm.cmd"
  $cmd = "@echo off`r`n" +
         "title RXTERM`r`n" +
         "chcp 65001 >nul`r`n" +
         "set PYTHONUTF8=1`r`n" +
         "cd /d `"%USERPROFILE%\RXTERM`"`r`n" +
         "`".venv\Scripts\rxterm.exe`" %*`r`n"
  [IO.File]::WriteAllText($Launcher, $cmd, [Text.Encoding]::ASCII)

  # `rxterm` command in new terminals
  $BinDir = Join-Path $UserHome ".local\bin"
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
  Copy-Item $Launcher (Join-Path $BinDir "rxterm.cmd") -Force
  $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (-not ($UserPath -split ";" | Where-Object { $_ -eq $BinDir })) {
    [Environment]::SetEnvironmentVariable("Path", ($BinDir + ";" + $UserPath).TrimEnd(";"), "User")
  }

  # Prefer Windows Terminal (true colour + Unicode charts); fall back to the classic console.
  $Wt = (Get-Command wt.exe -ErrorAction SilentlyContinue).Source
  $Shell = New-Object -ComObject WScript.Shell
  $Targets = @([Environment]::GetFolderPath("Desktop"),
               (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))
  foreach ($dir in $Targets) {
    $lnk = $Shell.CreateShortcut((Join-Path $dir "RXTERM.lnk"))
    if ($Wt) {
      $lnk.TargetPath = $Wt
      $lnk.Arguments = "--size 200,56 new-tab --title RXTERM --suppressApplicationTitle cmd /c `"`"$Launcher`"`""
    } else {
      $lnk.TargetPath = Join-Path $env:WINDIR "System32\cmd.exe"
      $lnk.Arguments = "/c mode con: cols=200 lines=56 & `"$Launcher`""
    }
    $lnk.WorkingDirectory = $AppDir
    $lnk.IconLocation = (Join-Path $AppDir "assets\rxterm.ico") + ",0"
    $lnk.Description = "RXTERM pharma & biotech trading terminal"
    $lnk.Save()
  }
  if (-not $Wt) {
    Write-Host "  Tip: install Windows Terminal from the Microsoft Store for the best-looking RXTERM, then re-run this installer." -ForegroundColor DarkGray
  }
} else {
  Step "Not on Windows - skipping shortcuts."
}

# 4. Smoke test ----------------------------------------------------------------
Step "Checking install..."
& $VenvPy -m rxterm --version | Out-Null
if ($LASTEXITCODE) { throw "RXTERM did not start - see the messages above." }
Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "RXTERM installed." -ForegroundColor Green
Write-Host "  Double-click RXTERM on your Desktop (also in the Start menu)."
Write-Host "  Or type 'rxterm' in a new terminal window."
Write-Host "  Run this installer again any time to update."
Write-Host ""
