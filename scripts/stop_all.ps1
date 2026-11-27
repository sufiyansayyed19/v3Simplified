# Stop all 4 microservices and close their PowerShell terminal windows
# Run from project root: .\scripts\stop_all.ps1

$Ports = @(8001, 8002, 8003, 8004)
$StoppedCount = 0

# 1. Close the 4 spawned PowerShell windows (and their child uvicorn/python trees)
$ServiceShells = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" | Where-Object {
    $_.ProcessId -ne $PID -and
    $_.CommandLine -match "uvicorn\s+app\.main:app\s+--port\s+800[1-4]"
}

foreach ($Shell in $ServiceShells) {
    $ProcId = [int]$Shell.ProcessId
    # taskkill /T kills the entire process tree (PowerShell window + watchfiles reloader + uvicorn worker)
    & taskkill.exe /PID $ProcId /T /F 2>$null | Out-Null
    Write-Host "Closed service terminal PID $ProcId" -ForegroundColor Yellow
    $StoppedCount++
}

# 2. Safety sweep: kill any remaining listener on ports 8001-8004 (and any reloader parent python.exe)
foreach ($Port in $Ports) {
    $Listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($Conn in $Listeners) {
        $OwnerId = [int]$Conn.OwningProcess
        if ($OwnerId -gt 0 -and $OwnerId -ne $PID) {
            & taskkill.exe /PID $OwnerId /T /F 2>$null | Out-Null
            Write-Host "Stopped remaining listener on port $Port (PID $OwnerId)" -ForegroundColor Yellow
            $StoppedCount++
        }
    }
}

# 3. Clean up any stray uvicorn python reloader parent processes for ports 8001-8004
$StrayUvicorn = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -match "uvicorn\s+app\.main:app\s+--port\s+800[1-4]"
}
foreach ($Proc in $StrayUvicorn) {
    $ProcId = [int]$Proc.ProcessId
    & taskkill.exe /PID $ProcId /T /F 2>$null | Out-Null
    Write-Host "Stopped stray uvicorn process PID $ProcId" -ForegroundColor Yellow
    $StoppedCount++
}

if ($StoppedCount -eq 0) {
    Write-Host "No running ParkingSimplified service terminals found." -ForegroundColor Cyan
} else {
    Write-Host "All 4 microservice terminals stopped cleanly!" -ForegroundColor Green
}
