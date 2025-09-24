from typing import Any, Protocol, TypeVar


class Page(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class BrowserContext(Protocol):
    async def new_page(self, *args: Any, **kwargs: Any) -> Page: ...
    def set_default_timeout(self, timeout: int) -> None: ...
    async def close(self) -> None: ...


class Browser(Protocol):
    async def new_context(self, *args: Any, **kwargs: Any) -> BrowserContext: ...
    async def close(self) -> None: ...
    async def launch(self, *args: Any, **kwargs: Any) -> "Browser": ...


class Playwright(Protocol):
    chromium: Browser


class PlaywrightContextManager(Protocol):
    async def __aenter__(self) -> Playwright: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None: ...


def async_playwright() -> PlaywrightContextManager: ...
