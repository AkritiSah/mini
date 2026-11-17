param([switch]$SmokeTest, [switch]$Restart)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtime = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$backendProcess = $null
$frontendProcess = $null
$mongoProcess = $null

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Required command missing: $Name" }
}
function Check-Exit([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit $LASTEXITCODE)." }
}
function Quoted([string]$Value) { return '"' + $Value + '"' }
function Get-DevServerListeners {
    & netstat.exe -ano -p tcp | ForEach-Object {
        if ($_ -match '^\s*TCP\s+\S+:(8000|5173)\s+\S+\s+LISTENING\s+(\d+)\s*$') {
            [pscustomobject]@{ Port = [int]$Matches[1]; ProcessId = [int]$Matches[2] }
        }
    }
}
function Test-ProjectServer($Listener) {
    $taskProcessId = $Listener.ProcessId
    $projectPython = [regex]::Escape((Join-Path $projectRoot '.venv\Scripts\python.exe'))
    $projectVite = [regex]::Escape((Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'))
    # Windows venv Python launches a system-Python child that owns the socket.
    # Check its parent too, but only while both processes are Uvicorn servers.
    for ($level = 0; $level -lt 3 -and $taskProcessId; $level++) {
        $taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$taskProcessId"
        if (-not $taskProcess) { return $false }
        $command = $taskProcess.CommandLine
        if ($Listener.Port -eq 5173) {
            return $taskProcess.Name -eq 'node.exe' -and $command -match $projectVite
        }
        if ($taskProcess.Name -ne 'python.exe' -or $command -notmatch '-m\s+uvicorn\s+main:app\b' -or
                $command -notmatch '--port\s+8000\b') { return $false }
        if ($command -match $projectPython) { return $true }
        $taskProcessId = $taskProcess.ParentProcessId
    }
    return $false
}
function Resolve-DevServerPorts {
    $listeners = @(Get-DevServerListeners)
    if (-not $listeners.Count) { return }
    $description = ($listeners | ForEach-Object { "port $($_.Port) (PID $($_.ProcessId))" }) -join ', '
    if (-not $Restart) {
        throw "Servers are already using $description. To reload this project's servers and .env, run .\run.ps1 -Restart."
    }
    # Validate every listener before stopping any process. Never stop another app.
    foreach ($listener in $listeners) {
        if (-not (Test-ProjectServer $listener)) {
            throw "Port $($listener.Port) is used by PID $($listener.ProcessId), which cannot be verified as this project's server. Stop that app or free the port manually."
        }
    }
    foreach ($listener in ($listeners | Sort-Object ProcessId -Unique)) {
        # Recheck ownership immediately before stopping in case a process exited.
        if (Test-ProjectServer $listener) {
            Write-Host "Stopping project server on port $($listener.Port) (PID $($listener.ProcessId))."
            Stop-Process -Id $listener.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not @(Get-DevServerListeners).Count) { return }
        Start-Sleep -Milliseconds 500
    }
    throw 'Ports 8000/5173 are still occupied after restart. Check the owning processes and try again.'
}
function Test-Database {
    try {
        & $python -c "import sys; sys.path.insert(0, 'backend'); from src.settings import Settings; from pymongo import MongoClient; s=Settings(); c=MongoClient(s.mongodb_uri,serverSelectionTimeoutMS=1000); c.admin.command('ping'); c.close()" 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

Push-Location $projectRoot
try {
    Require-Command 'python'; Require-Command 'node'; Require-Command 'npm'
    & python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ is required'"
    Check-Exit 'Python version check'
    & node -e "if (Number(process.versions.node.split('.')[0]) < 20) process.exit(1)"
    Check-Exit 'Node 20+ version check'
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & python -m venv .venv; Check-Exit 'Virtual environment creation'
    }
    $requirements = Join-Path $projectRoot 'backend\requirements.txt'
    $requirementsHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $requirementsMarker = Join-Path $runtime 'requirements.sha256'
    if (-not (Test-Path -LiteralPath $requirementsMarker) -or (Get-Content -LiteralPath $requirementsMarker -Raw).Trim() -ne $requirementsHash) {
        & $python -m pip install -r $requirements; Check-Exit 'Backend dependency installation'
        Set-Content -LiteralPath $requirementsMarker -Value $requirementsHash
    }
    $envFile = Join-Path $projectRoot 'backend\.env'
    if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath 'backend\.env.example' -Destination $envFile }
    & $python -c "import sys; sys.path.insert(0, 'backend'); from src.settings import Settings; s=Settings(); print('Gemini configured; connection initialized once at backend startup.' if s.llm_ready else 'Gemini requires GEMINI_API_KEY and GEMINI_MODEL in backend/.env.')"
    Resolve-DevServerPorts
    if (-not (Test-Database)) {
        $mongod = Get-ChildItem -LiteralPath (Join-Path $runtime 'mongodb') -Filter mongod.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $mongod) {
            & (Join-Path $projectRoot 'scripts\setup_mongo.ps1')
            $mongod = Get-ChildItem -LiteralPath (Join-Path $runtime 'mongodb') -Filter mongod.exe -Recurse | Select-Object -First 1
        }
        $databasePath = Join-Path $runtime 'mongo-data'
        New-Item -ItemType Directory -Path $databasePath -Force | Out-Null
        $mongoLog = Join-Path $runtime 'mongo.log'
        $mongoProcess = Start-Process -FilePath $mongod.FullName -ArgumentList @('--dbpath', (Quoted $databasePath), '--bind_ip', '127.0.0.1', '--port', '27017', '--logpath', (Quoted $mongoLog)) -WindowStyle Hidden -PassThru
        $databaseReady = $false
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            if (Test-Database) { $databaseReady = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $databaseReady) { throw 'MongoDB did not become ready. Check the MongoDB service/logs and MONGODB_URI.' }
    }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        $packageHash = (Get-FileHash -LiteralPath 'package.json' -Algorithm SHA256).Hash
        $packageMarker = Join-Path $runtime 'frontend.sha256'
        if (-not (Test-Path -LiteralPath 'node_modules') -or -not (Test-Path -LiteralPath $packageMarker) -or (Get-Content -LiteralPath $packageMarker -Raw).Trim() -ne $packageHash) {
            if (Test-Path -LiteralPath 'package-lock.json') { & npm ci --no-audit --no-fund } else { & npm install --no-audit --no-fund }
            Check-Exit 'Frontend dependency installation'
            Set-Content -LiteralPath $packageMarker -Value $packageHash
        }
    } finally { Pop-Location }
    $backendProcess = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1') -WorkingDirectory (Join-Path $projectRoot 'backend') -RedirectStandardOutput (Join-Path $runtime 'backend.out.log') -RedirectStandardError (Join-Path $runtime 'backend.err.log') -WindowStyle Hidden -PassThru
    $vite = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
    $frontendProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList @((Quoted $vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -RedirectStandardOutput (Join-Path $runtime 'frontend.out.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log') -WindowStyle Hidden -PassThru
    Write-Host "`nKrishi Mitra is starting."
    Write-Host 'Frontend: http://localhost:5173'
    Write-Host 'Backend:  http://127.0.0.1:8000'
    Write-Host 'API docs: http://127.0.0.1:8000/docs'
    Write-Host 'First document ingestion downloads MPNet; the reranker downloads only when reranking is enabled.'
    Write-Host 'Logs: .runtime and backend/logs. Press Ctrl+C here to stop.'
    if ($SmokeTest) {
        $webReady = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            try {
                $apiReady = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 3
                $uiReady = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 3
                if ($apiReady.StatusCode -eq 200 -and $uiReady.StatusCode -eq 200) { $webReady = $true; break }
            } catch { Start-Sleep -Seconds 1 }
        }
        if (-not $webReady) { throw 'Application readiness smoke test failed. See .runtime logs.' }
        Write-Host 'Smoke test passed: real MongoDB, backend health, and React server are ready.'
        return
    }
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) { Start-Sleep -Seconds 1 }
    throw 'An application process stopped. Check .runtime/backend.err.log and .runtime/frontend.err.log.'
} finally {
    foreach ($ownedProcess in @($backendProcess, $frontendProcess, $mongoProcess)) {
        if ($ownedProcess -and -not $ownedProcess.HasExited) {
            & taskkill.exe /PID $ownedProcess.Id /T /F 2>$null | Out-Null
        }
    }
    Pop-Location
}
