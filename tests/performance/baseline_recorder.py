"""
轻量性能基线记录器（测试侧专用）

目标：
- 在关键用例中记录耗时与轻量计数（如重连/失败至成功次数），形成可对比的JSON基线
- 最小侵入：纯测试侧实现，不改动生产代码
- 容错：写盘失败不影响测试通过
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from contextlib import contextmanager, asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Generator, List, Optional
from typing import AsyncGenerator

_LOCK = Lock()
_RECORDS: List[Dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _default_out_path() -> Path:
    # 默认输出到仓库内 tests/reports/perf/chaos_baseline.json
    # 若目录不可写，flush() 内部会降级为临时目录
    tests_dir = Path(__file__).resolve().parents[1]
    out_dir = tests_dir / "reports" / "perf"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "chaos_baseline.json"


@dataclass
class EnvInfo:
    python: str
    platform: str
    node: str


def _env_info() -> EnvInfo:
    return EnvInfo(
        python=sys.version.split(" ")[0],
        platform=platform.platform(),
        node=platform.node(),
    )


def record(case_id: str, **metrics: Any) -> None:
    """记录一条性能数据。

    常用字段：
        - duration_ms: float
        - retries / reconnect_attempts / failures_until_success: int
    """
    item: Dict[str, Any] = {
        "case_id": case_id,
        "timestamp": _now_iso(),
        "env": asdict(_env_info()),
    }
    item.update(metrics)

    with _LOCK:
        _RECORDS.append(item)


@contextmanager
def time_block(
    case_id: str, label: Optional[str] = None
) -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        record(case_id, duration_ms=round(elapsed_ms, 3), label=label or "")


@asynccontextmanager
async def async_time_block(
    case_id: str, label: Optional[str] = None
) -> AsyncGenerator[None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        record(case_id, duration_ms=round(elapsed_ms, 3), label=label or "")


def flush() -> Optional[Path]:
    """将采集记录写出为 JSON。返回最终写入的文件路径或 None（无记录）。"""
    with _LOCK:
        if not _RECORDS:
            return None

        # 环境变量可覆盖输出路径
        out_env = os.getenv("PERF_BASELINE_OUT")
        if out_env:
            out_path = Path(out_env)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = _default_out_path()

        payload = {
            "generated_at": _now_iso(),
            "count": len(_RECORDS),
            "records": list(_RECORDS),
        }

        try:
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            # 可选：与上一版基线进行对比并打印摘要
            prev = os.getenv("PERF_BASELINE_PREV")
            if prev:
                try:
                    summary = _compare_with(Path(prev))
                    if os.getenv("PERF_COMPARE_PRINT", "1") == "1":
                        print("\n[perf] Baseline comparison summary:")
                        print(json.dumps(summary, ensure_ascii=False, indent=2))
                except Exception:
                    # 对比失败不影响测试
                    pass
            return out_path
        except Exception:
            # 降级到临时目录
            try:
                tmp_dir = Path(os.getenv("TMPDIR", "/tmp"))
                tmp_dir.mkdir(parents=True, exist_ok=True)
                fallback = tmp_dir / "chaos_baseline.json"
                fallback.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
                return fallback
            except Exception:
                # 最终放弃写盘，避免影响测试
                return None


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        return None
    return None


def _compare_with(prev_path: Path) -> Dict[str, Any]:
    """内部：与上一版基线对比（仅比对相同 case_id 的 duration_ms）。"""
    prev_payload = _load_json(prev_path) or {}
    prev_list: List[Dict[str, Any]] = prev_payload.get("records", [])  # type: ignore[assignment]
    prev = {rec.get("case_id"): rec for rec in prev_list}

    with _LOCK:
        current = {rec.get("case_id"): rec for rec in _RECORDS}

    tol = float(os.getenv("PERF_TOLERANCE_PCT", "10"))
    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []

    for case_id, curr in current.items():
        if case_id not in prev:
            continue
        c_ms = float(curr.get("duration_ms", -1))
        p_ms = float(prev[case_id].get("duration_ms", -1))
        if c_ms < 0 or p_ms <= 0:
            continue
        change_pct = ((c_ms - p_ms) / p_ms) * 100.0
        item = {
            "case_id": case_id,
            "prev_ms": round(p_ms, 3),
            "curr_ms": round(c_ms, 3),
            "change_pct": round(change_pct, 2),
        }
        if change_pct > tol:
            regressions.append(item)
        elif change_pct < -tol:
            improvements.append(item)

    return {"regressions": regressions, "improvements": improvements}
