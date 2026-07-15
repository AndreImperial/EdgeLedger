$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot 'backend'
$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $backendPython)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3.11 -m venv (Join-Path $backendRoot '.venv')
    } elseif ($systemPython) {
        & $systemPython.Source -m venv (Join-Path $backendRoot '.venv')
    } else {
        throw 'Python 3.11 is required to initialize the integrated EdgeLedger engine.'
    }
    & $backendPython -m pip install -r (Join-Path $backendRoot 'requirements.txt')
}

$pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
if (-not $pnpm) {
    throw 'pnpm is required. Install it with: corepack enable && corepack prepare pnpm@latest --activate'
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'node_modules'))) {
    & $pnpm.Source install --dir $projectRoot
}

if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $backendPython `
        -ArgumentList '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden
}

if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $pnpm.Source `
        -ArgumentList 'dev', '--', '--host', '127.0.0.1' `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden
}

Start-Sleep -Seconds 2
Start-Process 'http://127.0.0.1:5173/scanner'
