"""HTML -> PNG rendering for receipt cards.

Playwright is imported lazily here only -- the core test suite (and
data.py/template.py, which are pure) run without a headless browser
installed, same convention as workflows/material/graph.py's lazy langgraph
import. One headless Chromium instance is reused across renders (started on
first use, never per-message) since launching a browser per WhatsApp message
would be far too slow for a reply path.
"""

from __future__ import annotations

import asyncio
from typing import Any

_CARD_SELECTOR = ".card"


class ReceiptRenderer:
    """Owns one long-lived headless Chromium instance for the process."""

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> Any:
        if self._browser is not None:
            return self._browser
        async with self._lock:
            if self._browser is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def render_png(self, html: str) -> bytes:
        """Render the given HTML and screenshot just the `.card` element."""
        browser = await self._ensure_browser()
        page = await browser.new_page(viewport={"width": 680, "height": 800})
        try:
            await page.set_content(html, wait_until="load")
            card = page.locator(_CARD_SELECTOR)
            return await card.screenshot(type="png")
        finally:
            await page.close()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
