from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed


def test_health_concurrency_basic(client: "object") -> None:
    def call_health() -> int:
        r = client.get("/health")
        return r.status_code

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(call_health) for _ in range(16)]
        codes = [f.result() for f in as_completed(futures)]

    assert all(c == 200 for c in codes)
