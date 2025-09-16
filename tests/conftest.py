import os
import sys
from typing import Any

# Ensure project root and backend package are importable during pytest collection
_here = os.path.dirname(__file__)
_project_root = os.path.abspath(os.path.join(_here, ".."))
_backend_root = os.path.join(_project_root, "backend")

for p in (_project_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, p)

# 性能基线记录器：在测试会话结束时统一落盘
try:
    from tests.performance import baseline_recorder as _perf_recorder  # type: ignore

    def pytest_sessionfinish(session: Any, exitstatus: int) -> None:  # noqa: D401
        """在pytest会话结束时写出性能基线JSON（如果已采集）。"""
        try:
            _perf_recorder.flush()
        except Exception:
            # 不影响测试结果
            pass
except Exception:
    # 性能记录器不存在或导入失败时静默跳过
    pass
