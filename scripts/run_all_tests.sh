#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTEST="$ROOT_DIR/.venv/bin/pytest"
if [[ ! -x "$PYTEST" ]]; then
  PYTEST="$ROOT_DIR/.venv/Scripts/pytest.exe"
fi

SUITES=(
  "services/user-auth-service/tests/test_auth.py"
  "services/vehicle-service/tests/test_vehicles.py"
  "services/parking-service/tests/test_parking.py"
  "services/parking-service/tests/test_internal.py"
  "services/payment-service/tests/test_payments.py"
  "tests/test_pg_concurrency.py"
  "tests/test_e2e_journey.py"
)

for suite in "${SUITES[@]}"; do
  echo ""
  echo "=== Running $suite ==="
  "$PYTEST" "$ROOT_DIR/$suite" -v
done

echo ""
echo "ALL TEST SUITES PASSED!"
