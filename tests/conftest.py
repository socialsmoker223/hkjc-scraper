"""Pytest fixtures for HKJC scraper tests."""

from pathlib import Path

import pytest


def get_fixture_path(name: str) -> Path:
    """Get the full path to a fixture file.

    Args:
        name: Fixture name (with or without .html extension)

    Returns:
        Path to the fixture file
    """
    if not name.endswith(".html"):
        name = f"{name}.html"
    return Path(__file__).parent / "fixtures" / name


def load_fixture(name: str) -> str:
    """Load a fixture file as text.

    Args:
        name: Fixture name (with or without .html extension)

    Returns:
        File contents as a string
    """
    path = get_fixture_path(name)
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_race_html():
    """Load the sample race HTML fixture."""
    return load_fixture("sample_race")


@pytest.fixture
def sample_race_response(sample_race_html):
    from bs4 import BeautifulSoup
    from scrapling.spiders import Request
    from urllib.parse import urljoin

    class MockResponse:
        def __init__(self, html):
            self.html = html
            self.url = "https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2026/03/01&Racecourse=ST&RaceNo=1"
            self.meta = {}

        @property
        def text(self):
            return self.html

        def css(self, selector):
            soup = BeautifulSoup(self.html, "html.parser")
            results = soup.select(selector)
            return [self._element_to_mock(e) for e in results]

        def _element_to_mock(self, elem):
            class MockElem:
                def __init__(self, el):
                    self._el = el
                    self.text = el.get_text(strip=True)
                    self.attrib = {"href": el.get("href", "")}

                def css(self, selector):
                    return [MockElem(e) for e in self._el.select(selector)]

            return MockElem(elem)

        def urljoin(self, url):
            """Join relative URL with base URL."""
            return urljoin(self.url, url)

        def follow(self, url, callback=None, meta=None):
            """Mock follow method that returns a Request object."""
            req = Request(url)
            req.callback = callback
            req.meta = meta or {}
            return req

    return MockResponse(sample_race_html)
