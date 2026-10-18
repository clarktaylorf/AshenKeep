# Installs Python (user-scope) + edge-tts for generating the game's narrator voice files.
$ErrorActionPreference = 'Stop'
$envDir = Join-Path $env:LOCALAPPDATA 'Temp\opencode\pyenv'
$log    = Join-Path $env:LOCALAPPDATA 'Temp\opencode\voice-setup.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log), $envDir | Out-Null
function Log($m) { $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Add-Content -Path $log -Value $line; Write-Output $line }
Set-Content -Path $log -Value 'voice setup start'

function Find-Py {
  $cands = @()
  $cands += (Get-ChildItem "$envDir\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName)
  $cands += @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
              "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
              "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")
  foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
  $g = Get-Command python -ErrorAction SilentlyContinue
  if ($g -and $g.Source -notlike '*WindowsApps*') { return $g.Source }
  return $null
}

$py = Find-Py
if (-not $py) {
  Log 'trying winget (user scope)...'
  try {
    winget install --id Python.Python.3.12 --scope user --silent --disable-interactivity --accept-package-agreements --accept-source-agreements 2>&1 | ForEach-Object { Log "  $_" }
  } catch { Log "winget error: $($_.Exception.Message)" }
  $py = Find-Py
}

if (-not $py) {
  Log 'winget did not yield python - using embeddable zip fallback'
  $zip = Join-Path $env:LOCALAPPDATA 'Temp\opencode\python-embed.zip'
  Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip' -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath $envDir -Force
  # allow site-packages / pip inside the embeddable distribution
  Get-ChildItem "$envDir\python*._pth" | ForEach-Object {
    $c = Get-Content $_.FullName -Raw
    if ($c -notmatch 'import site') { Add-Content -Path $_.FullName -Value "`nimport site" }
  }
  $gp = Join-Path $env:LOCALAPPDATA 'Temp\opencode\get-pip.py'
  Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile $gp
  & (Join-Path $envDir 'python.exe') $gp --quiet 2>&1 | ForEach-Object { Log "  $_" }
  $py = Find-Py
}

if (-not $py) { Log 'FAILED: no python available'; exit 1 }
Log "python: $py"
& $py --version 2>&1 | ForEach-Object { Log "  $_" }

Log 'installing edge-tts...'
& $py -m pip install --quiet --disable-pip-version-check --no-warn-script-location edge-tts 2>&1 | ForEach-Object { Log "  $_" }
& $py -c "import edge_tts, sys; print('edge-tts', edge_tts.__version__)" 2>&1 | ForEach-Object { Log "  $_" }
if ($LASTEXITCODE -ne 0) { Log 'FAILED: edge-tts import failed'; exit 1 }
Set-Content -Path (Join-Path (Split-Path $log) 'voice-setup.py') -Value $py
Log 'SETUP OK'
