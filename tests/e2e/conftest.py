import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from app.database.models import Source
from app.utils.browser_manager import PlaywrightBrowserManager
from app.utils.rate_limiter import rate_limiter
from app.utils.proxy_manager import tor_proxy_manager


@pytest.fixture(scope="function", autouse=True)
def inline_rq_worker(monkeypatch: MonkeyPatch):
    """Execute scraping jobs inline for E2E tests without external RQ worker."""

    from app.workers import queue as queue_module
    from app.workers import scraping_worker
    from app.api import scraping as scraping_module

    job_status: dict[str, str] = {}

    def enqueue_inline(job_id: int, config: dict, priority: str = "normal") -> str:
        rq_job_id = f"inline-{job_id}"
        job_status[rq_job_id] = "queued"

        loop = asyncio.get_running_loop()

        async def run_job():
            job_status[rq_job_id] = "started"
            try:
                await scraping_worker.process_scraping_job_async(job_id, config)
            except Exception:  # pragma: no cover - surface in test helpers
                job_status[rq_job_id] = "failed"
                # Don't re-raise - let the job finish with failed status
            else:
                job_status[rq_job_id] = "finished"

        loop.create_task(run_job())
        return rq_job_id

    def get_inline_status(rq_job_id: str) -> dict:
        status = job_status.get(rq_job_id, "not_found")
        return {"status": status, "result": None, "exc_info": None, "meta": {}}

    def cancel_inline_job(rq_job_id: str) -> bool:
        if job_status.get(rq_job_id) == "queued":
            job_status[rq_job_id] = "cancelled"
            return True
        return False

    monkeypatch.setattr(queue_module, "enqueue_scraping_job", enqueue_inline)
    monkeypatch.setattr(queue_module, "get_rq_job_status", get_inline_status)
    monkeypatch.setattr(queue_module, "cancel_rq_job", cancel_inline_job)

    # Patch API module references that imported the helpers directly
    monkeypatch.setattr(scraping_module, "enqueue_scraping_job", enqueue_inline)
    monkeypatch.setattr(scraping_module, "get_rq_job_status", get_inline_status)
    monkeypatch.setattr(scraping_module, "cancel_rq_job", cancel_inline_job)

    yield

    job_status.clear()


@pytest.fixture(scope="function")
def html_fixture_loader():
    """Factory fixture to load HTML fixture files from tests/fixtures/html."""

    cache: dict[str, str] = {}

    def _load(filename: str) -> str:
        if filename not in cache:
            fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "html"
            file_path = fixtures_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Fixture '{filename}' not found in {fixtures_dir}")
            cache[filename] = file_path.read_text(encoding="utf-8")
        return cache[filename]

    return _load


@pytest.fixture(scope="function")
def mock_playwright_with_html(monkeypatch: MonkeyPatch):
    """Factory fixture to mock Playwright page content with provided HTML."""

    async def _create_page_stub(*_, html_content: str):
        page = AsyncMock()
        page.content = AsyncMock(return_value=html_content)
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        context.close = AsyncMock()

        browser = AsyncMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()

        playwright = AsyncMock()
        playwright.stop = AsyncMock()

        return page, context, browser, playwright

    def _factory(html_content: str):
        async def create_page(*args, **kwargs):
            return await _create_page_stub(*args, html_content=html_content, **kwargs)

        async def close_stub(self, browser, playwright):
            await browser.close()
            await playwright.stop()

        monkeypatch.setattr(PlaywrightBrowserManager, "create_page", create_page)
        monkeypatch.setattr(PlaywrightBrowserManager, "close", close_stub)

    return _factory


@pytest.fixture(scope="function")
def mock_rate_limiter(monkeypatch: MonkeyPatch):
    """Mock rate limiter instance to avoid Redis access."""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(rate_limiter, "wait_if_needed", noop)
    monkeypatch.setattr(rate_limiter, "connect", noop)
    monkeypatch.setattr(rate_limiter, "close", noop)


@pytest.fixture(scope="function")
def mock_tor_proxy(monkeypatch: MonkeyPatch):
    """Mock Tor proxy manager to avoid Tor interactions."""

    async def noop(*args, **kwargs):
        return None

    def proxy_config_stub(*args, **kwargs):
        return None

    monkeypatch.setattr(tor_proxy_manager, "rotate_ip", noop)
    monkeypatch.setattr(tor_proxy_manager, "get_proxy_config", proxy_config_stub)


@pytest.fixture(scope="function")
def create_html_fixture_file(tmp_path):
    """Utility to create HTML fixture files dynamically for tests."""

    def _create(filename: str, content: str, directory: Optional[Path] = None) -> Path:
        target_dir = directory or (Path(__file__).resolve().parent.parent / "fixtures" / "html")
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    return _create


@pytest.fixture(scope="function")
def create_source(db_session):
    """Create or fetch a scraping source for tests."""

    def _create(**overrides):
        name = overrides.get("name", "11880")
        source = db_session.query(Source).filter_by(name=name).first()
        if not source:
            source = Source(
                name=name,
                display_name=overrides.get("display_name", name.replace("_", " ").title()),
                url=overrides.get("url", f"https://{name}.example.com"),
            )
            db_session.add(source)
            db_session.commit()
            db_session.refresh(source)
        return source

    return _create
