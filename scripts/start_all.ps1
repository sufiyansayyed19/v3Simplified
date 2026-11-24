# Start all 4 microservices in separate PowerShell windows
# Run from project root: .\scripts\start_all.ps1

$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Virtual environment python not found at $Python. Create .venv and install requirements.txt first."
    exit 1
}

$Apps = @(
    @{ Name = "User/Auth Service (8001)"; Dir = Join-Path $Root "services\user-auth-service"; Port = 8001 },
    @{ Name = "Vehicle Service (8002)";   Dir = Join-Path $Root "services\vehicle-service";   Port = 8002 },
    @{ Name = "Parking Service (8003)";   Dir = Join-Path $Root "services\parking-service";   Port = 8003 },
    @{ Name = "Payment Service (8004)";   Dir = Join-Path $Root "services\payment-service";   Port = 8004 }
)

foreach ($App in $Apps) {
    $Cmd = "`$Host.UI.RawUI.WindowTitle = '$($App.Name)'; Set-Location '$($App.Dir)'; & '$Python' -m uvicorn app.main:app --port $($App.Port) --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $Cmd
}

Write-Host "Started all 4 microservices!" -ForegroundColor Green
Write-Host "  User/Auth Swagger: http://127.0.0.1:8001/docs"
Write-Host "  Vehicle Swagger:   http://127.0.0.1:8002/docs"
Write-Host "  Parking Swagger:   http://127.0.0.1:8003/docs"
Write-Host "  Payment Swagger:   http://127.0.0.1:8004/docs"
