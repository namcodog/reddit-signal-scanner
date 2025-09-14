"""
Integration test base utilities

Keep simple; reuse fixtures from test_fixtures.
"""

from dataclasses import dataclass


@dataclass
class IntegrationTestBase:
    def url(self, build_url, path: str) -> str:
        return build_url(path)

