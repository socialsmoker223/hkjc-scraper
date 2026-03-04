"""Tests for HKJCRacingSpider."""
import pytest
from scrapling.spiders import Spider
from hkjc_scraper.spider_v2 import HKJCRacingSpider


class TestSpiderClass:
    """Test Spider class configuration."""

    def test_spider_is_spider_subclass(self):
        assert issubclass(HKJCRacingSpider, Spider)

    def test_spider_has_name(self):
        assert HKJCRacingSpider.name == "hkjc_racing"

    def test_spider_has_base_url(self):
        spider = HKJCRacingSpider()
        assert spider.BASE_URL == "https://racing.hkjc.com/zh-hk/local/information/localresults"

    def test_spider_has_concurrent_requests(self):
        spider = HKJCRacingSpider()
        assert spider.concurrent_requests == 5
