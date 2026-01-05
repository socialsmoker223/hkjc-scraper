"""
Tests for HTTP utilities (retry logic, rate limiting, session management)
"""

import time
from unittest.mock import Mock, patch

import pytest
import requests

from hkjc_scraper.http_utils import HTTPSession, rate_limited, retry_on_network_error


class TestHTTPSession:
    """Test HTTPSession context manager"""

    def test_session_creation(self):
        """Test HTTPSession creates and closes session properly"""
        with HTTPSession() as session:
            assert session is not None
            assert hasattr(session, "get")
            assert hasattr(session, "session")
            assert session.session is not None

    def test_session_has_headers(self):
        """Test HTTPSession sets default headers"""
        with HTTPSession() as session:
            headers = session.session.headers
            assert "User-Agent" in headers
            assert "Accept-Language" in headers

    def test_session_get_method(self):
        """Test HTTPSession.get() method exists and accepts parameters"""
        with HTTPSession() as session:
            # Mock the actual get call to avoid real HTTP request
            with patch.object(session.session, "get") as mock_get:
                mock_get.return_value = Mock(status_code=200, text="OK")
                response = session.get("http://example.com")
                assert response.status_code == 200
                mock_get.assert_called_once()


class TestRetryDecorator:
    """Test retry_on_network_error decorator"""

    def test_retry_on_connection_error(self):
        """Test retry logic on ConnectionError"""
        mock_func = Mock(
            side_effect=[
                requests.ConnectionError("Connection failed"),
                requests.ConnectionError("Connection failed"),
                "success",
            ]
        )

        @retry_on_network_error
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_gives_up_after_max_attempts(self):
        """Test retry logic eventually gives up"""
        mock_func = Mock(side_effect=requests.ConnectionError("Permanent failure"))

        @retry_on_network_error
        def test_func():
            return mock_func()

        with pytest.raises(requests.ConnectionError):
            test_func()

        # Should try 3 times (default RETRY_MAX_ATTEMPTS)
        assert mock_func.call_count == 3

    def test_retry_on_timeout(self):
        """Test retry logic on Timeout"""
        mock_func = Mock(side_effect=[requests.Timeout("Timeout"), "success"])

        @retry_on_network_error
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 2

    def test_no_retry_on_http_error(self):
        """Test that HTTP errors are not retried"""
        mock_func = Mock(side_effect=requests.HTTPError("404 Not Found"))

        @retry_on_network_error
        def test_func():
            return mock_func()

        with pytest.raises(requests.HTTPError):
            test_func()

        # Should only try once (no retry for HTTP errors)
        assert mock_func.call_count == 1


class TestRateLimiter:
    """Test rate_limited decorator"""

    def test_rate_limiting_adds_delay(self):
        """Test rate limiter adds delays between calls"""
        call_times = []

        @rate_limited(0.1)  # 100ms delay
        def test_func():
            call_times.append(time.time())
            return "done"

        # Make two calls
        test_func()
        test_func()

        # Check that there was a delay between calls
        if len(call_times) >= 2:
            time_diff = call_times[1] - call_times[0]
            assert time_diff >= 0.1, f"Expected delay >= 0.1s, got {time_diff}s"

    def test_rate_limiting_per_function(self):
        """Test rate limiter is independent per function"""

        @rate_limited(0.1)
        def func1():
            return "func1"

        @rate_limited(0.1)
        def func2():
            return "func2"

        start = time.time()
        func1()
        func2()  # Should not be delayed by func1's rate limit
        duration = time.time() - start

        # Both calls should complete quickly (no cumulative delay)
        assert duration < 0.2, f"Expected < 0.2s, got {duration}s"


class TestIntegration:
    """Integration tests for HTTP utilities"""

    def test_session_with_retry_decorator(self):
        """Test HTTPSession works with retry decorator"""

        @retry_on_network_error
        def fetch_with_session(session):
            with patch.object(session.session, "get") as mock_get:
                mock_get.return_value = Mock(status_code=200, text="OK")
                return session.get("http://example.com")

        with HTTPSession() as session:
            response = fetch_with_session(session)
            assert response.status_code == 200

    def test_combined_decorators(self):
        """Test combining retry and rate limit decorators"""
        mock_func = Mock(return_value="success")

        @retry_on_network_error
        @rate_limited(0.05)
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
