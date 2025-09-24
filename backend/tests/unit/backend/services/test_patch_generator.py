from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.services.admin.patch_generator import build_patch, dump_yaml


def test_build_patch_and_dump_yaml() -> None:
    decisions = [
        {"community": "r/startups", "action": "approve", "labels": ["状态:核心"]},
        {"community": "r/technology", "action": "blacklist", "labels": ["状态:黑名单"]},
        {"community": "r/ArtificialIntelligence", "action": "experiment", "labels": ["主题:AI"]},
        {"community": "r/startups", "action": "approve", "labels": ["状态:核心"]},  # 重复
    ]

    patch = build_patch(decisions)
    assert "core" in patch and "experimental" in patch and "blacklist" in patch and "labels" in patch
    assert "r/startups" in patch["core"]
    assert "r/technology" in patch["blacklist"]
    assert "r/ArtificialIntelligence" in patch["experimental"]

    ytext = dump_yaml(patch)
    assert "core:" in ytext and "labels:" in ytext

