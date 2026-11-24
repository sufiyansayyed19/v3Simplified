# Run all service, PostgreSQL concurrency, and E2E tests in isolated processes
# Run from project root: .\scripts\run_all_tests.ps1

$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

$Suites = @(
    "services/user-auth-service/tests/test_auth.py",
    "services/vehicle-service/tests/test_vehicles.py",
    "services/parking-service/tests/test_parking.py",
    "services/parking-service/tests/test_internal.py",
    "services/payment-service/tests/test_payments.py",
    "tests/test_pg_concurrency.py",
    "tests/test_e2e_journey.py"
)

$Failed = @()
foreach ($Suite in $Suites) {
    Write-Host "`n=== Running $Suite ===" -ForegroundColor Cyan
    & $Python -m pytest $Suite -v
    if ($LASTEXITCODE -ne 0) {
        $Failed += $Suite
    }
}

if ($Failed.Count -gt 0) {
    Write-Host "`nFAILED SUITES:" -ForegroundColor Red
    $Failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "`nALL TEST SUITES PASSED!" -ForegroundColor Green
