import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(True is False, reason="placeholder")
def _placeholder() -> None:
    # keeps file importable on older pytest versions that mis-handle empties
    pass


def test_autoretry_on_engine_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch AnalysisEngine.analyze to fail twice, then succeed.

    Asserts Celery autoretry kicks in (>=2 attempts) and the final task completes.
    """
    from typing import Any, Dict
    from backend.app.tasks.analysis_tasks import analyze_product_task
    from backend.app.services import analysis_engine as ae_mod

    attempts = {"n": 0}

    class FakeReport:
        def __init__(self) -> None:
            self.report_id = "fake-report"
            self.confidence_score = 0.7
            self.total_posts_analyzed = 10
            self.communities_scanned = 3

        def get_executive_summary(self) -> str:
            return "summary"

    async def fake_analyze(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("transient network")
        return FakeReport()

    monkeypatch.setattr(ae_mod.AnalysisEngine, "analyze", fake_analyze, raising=True)

    res = analyze_product_task.delay(payload={"product_description": "valid long description"})
    out: Dict[str, Any] = res.get(timeout=180)

    assert attempts["n"] >= 3  # 2 failures + 1 success
    assert res.successful() is True
    assert out.get("status") == "completed"

