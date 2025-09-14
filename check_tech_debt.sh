#!/usr/bin/env bash
set -euo pipefail

echo "== Tech Debt Snapshot =="
echo "Timestamp: $(date -Iseconds)"

pushd backend >/dev/null

echo -n "MyPy错误数: "
mypy app 2>&1 | grep -E "error:" | wc -l || echo 0

echo -n "Dict[str, Any] 次数: "
grep -R "Dict\[str, Any\]" app | wc -l || echo 0

popd >/dev/null

