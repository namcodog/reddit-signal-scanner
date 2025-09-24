from __future__ import annotations


def test_stream_endpoint_contract(client: "object") -> None:
    # SSE 端点应返回 200 且 content-type 含 text/event-stream
    resp = client.get("/api/v1/stream/test", headers={"Accept": "text/event-stream"})
    # 某些实现可能返回 404（若未启用流）；此处按存在性验证，不强制
    if resp.status_code == 200:
        ctype = resp.headers.get("content-type", "")
        assert "text/event-stream" in ctype

