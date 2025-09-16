"""
Integration test base utilities

Keep simple; reuse fixtures from test_fixtures.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class IntegrationTestBase:
    def url(self, build_url: Callable[[str], str], path: str) -> str:
        return build_url(path)

