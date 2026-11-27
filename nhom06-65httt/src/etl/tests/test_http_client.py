import io
import math
import ssl
import unittest
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from etl.config import Settings
from etl.http_client import (
    HttpClient,
    PaginationError,
    PaginationLimitError,
)


class FakeResponse:
    def __init__(self, body=b"ok", status=200, headers=None, url="https://api.test/"):
        self.body = body
        self.status = status
        self.headers = headers or {}
        self.url = url

    def read(self):
        return self.body

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def make_http_error(status, headers=None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return HTTPError(
        "https://api.test/resource?token=hidden",
        status,
        "request failed",
        message,
        io.BytesIO(b"private response body"),
    )


class HttpClientTests(unittest.TestCase):
    def test_get_uses_configured_timeout_and_encodes_params(self):
        client = HttpClient(timeout=4.5, max_retries=0)
        response = FakeResponse(
            body=b'{"ok":true}',
            headers={"Content-Type": "application/json"},
            url="https://api.test/items?limit=2",
        )

        with patch("etl.http_client.urlopen", return_value=response) as urlopen:
            result = client.get(
                "https://api.test/items",
                params={"search": "blue cup"},
                headers={"Authorization": "Bearer secret-token"},
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.test/items?search=blue+cup",
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 4.5)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, b'{"ok":true}')
        self.assertEqual(result.headers["Content-Type"], "application/json")

    def test_network_error_retries_only_up_to_configured_limit(self):
        client = HttpClient(
            timeout=1,
            max_retries=2,
            backoff_seconds=0.1,
        )
        response = FakeResponse()

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=[URLError("temporary"), URLError("temporary"), response],
            ) as urlopen,
            patch("etl.http_client.time.sleep") as sleep,
        ):
            result = client.get("https://api.test/resource")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.1, 0.2])

    def test_retries_stop_after_max_retries(self):
        client = HttpClient(max_retries=1, backoff_seconds=0)

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=URLError("offline"),
            ) as urlopen,
            patch("etl.http_client.time.sleep"),
        ):
            with self.assertRaises(URLError):
                client.get("https://api.test/resource")

        self.assertEqual(urlopen.call_count, 2)

    def test_http_429_honors_retry_after(self):
        client = HttpClient(max_retries=1)
        response = FakeResponse()

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=[make_http_error(429, {"Retry-After": "3"}), response],
            ),
            patch("etl.http_client.time.sleep") as sleep,
        ):
            result = client.get("https://api.test/resource")

        self.assertEqual(result.status_code, 200)
        sleep.assert_called_once_with(3.0)

    def test_retry_after_above_limit_does_not_retry_early(self):
        client = HttpClient(max_retries=2, max_retry_delay_seconds=5)

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=make_http_error(429, {"Retry-After": "60"}),
            ) as urlopen,
            patch("etl.http_client.time.sleep") as sleep,
        ):
            with self.assertRaises(HTTPError):
                client.get("https://api.test/resource")

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_non_retryable_http_error_is_not_retried(self):
        client = HttpClient(max_retries=3)

        with patch(
            "etl.http_client.urlopen",
            side_effect=make_http_error(404),
        ) as urlopen:
            with self.assertRaises(HTTPError):
                client.get("https://api.test/resource")

        self.assertEqual(urlopen.call_count, 1)

    def test_logs_status_and_host_without_query_or_sensitive_headers(self):
        client = HttpClient(max_retries=0)
        response = FakeResponse()

        with (
            self.assertLogs("etl.http_client", level="INFO") as logs,
            patch("etl.http_client.urlopen", return_value=response),
        ):
            client.get(
                "https://api.test/resource?access_token=secret-query",
                headers={"Authorization": "Bearer secret-header"},
            )

        output = "\n".join(logs.output)
        self.assertIn("method=GET", output)
        self.assertIn("host=api.test", output)
        self.assertIn("status=200", output)
        self.assertIn("response_time_ms=", output)
        self.assertNotIn("secret-query", output)
        self.assertNotIn("secret-header", output)
        self.assertNotIn("/resource", output)

    def test_pagination_uses_callback_and_stops_when_no_next_page(self):
        client = HttpClient(max_retries=0)
        responses = [
            FakeResponse(headers={"X-Next": "https://api.test/page/2"}),
            FakeResponse(headers={"X-Next": "https://api.test/page/3"}),
            FakeResponse(headers={}),
        ]
        with patch("etl.http_client.urlopen", side_effect=responses) as urlopen:
            pages = list(
                client.iter_pages(
                    "https://api.test/page/1",
                    lambda response: response.headers.get("X-Next"),
                )
            )

        self.assertEqual(len(pages), 3)
        self.assertEqual(urlopen.call_count, 3)

    def test_pagination_resolves_relative_next_links(self):
        client = HttpClient(max_retries=0)
        responses = [
            FakeResponse(headers={"X-Next": "/page/2"}),
            FakeResponse(headers={}),
        ]

        with patch("etl.http_client.urlopen", side_effect=responses) as urlopen:
            pages = list(
                client.iter_pages(
                    "https://api.test/page/1",
                    lambda response: response.headers.get("X-Next"),
                )
            )

        self.assertEqual(len(pages), 2)
        self.assertEqual(
            urlopen.call_args_list[1].args[0].full_url,
            "https://api.test/page/2",
        )

    def test_pagination_rejects_cross_origin_and_repeated_links(self):
        client = HttpClient(max_retries=0)
        response = FakeResponse()

        with patch("etl.http_client.urlopen", return_value=response):
            with self.assertRaisesRegex(PaginationError, "origin"):
                list(
                    client.iter_pages(
                        "https://api.test/page/1",
                        lambda _: "https://other.test/page/2",
                    )
                )
            with self.assertRaisesRegex(PaginationError, "repeated"):
                list(
                    client.iter_pages(
                        "https://api.test/page/1",
                        lambda _: "https://api.test/page/1",
                    )
                )

    def test_pagination_limit_is_enforced(self):
        client = HttpClient(max_retries=0)
        response = FakeResponse()

        with patch("etl.http_client.urlopen", return_value=response):
            with self.assertRaises(PaginationLimitError):
                list(
                    client.iter_pages(
                        "https://api.test/page/1",
                        lambda _: "https://api.test/page/2",
                        max_pages=1,
                    )
                )

    def test_client_can_be_built_from_environment_settings(self):
        settings = Settings.from_env(
            {
                "ETL_HTTP_TIMEOUT_SECONDS": "7.5",
                "ETL_HTTP_MAX_RETRIES": "4",
                "ETL_HTTP_BACKOFF_SECONDS": "0.25",
                "ETL_HTTP_MAX_RETRY_DELAY_SECONDS": "12",
            }
        )
        client = HttpClient.from_settings(settings)

        self.assertEqual(client.timeout, 7.5)
        self.assertEqual(client.max_retries, 4)
        self.assertEqual(client.backoff_seconds, 0.25)
        self.assertEqual(client.max_retry_delay_seconds, 12)

    def test_url_credentials_and_invalid_client_settings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            HttpClient().get("https://user:password@api.test/")
        with self.assertRaisesRegex(ValueError, "timeout"):
            HttpClient(timeout=0)
        with self.assertRaisesRegex(ValueError, "timeout"):
            HttpClient(timeout=-1.0)
        with self.assertRaisesRegex(ValueError, "timeout"):
            HttpClient(timeout=float("nan"))
        with self.assertRaisesRegex(ValueError, "timeout"):
            HttpClient(timeout=float("inf"))

        with self.assertRaisesRegex(ValueError, "max_retries"):
            HttpClient(max_retries=11)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            HttpClient(max_retries=-1)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            HttpClient(max_retries="3")  # type: ignore
        with self.assertRaisesRegex(ValueError, "max_retries"):
            HttpClient(max_retries=3.5)  # type: ignore

        with self.assertRaisesRegex(ValueError, "backoff_seconds"):
            HttpClient(backoff_seconds=-0.5)
        with self.assertRaisesRegex(ValueError, "backoff_seconds"):
            HttpClient(backoff_seconds=float("inf"))

        with self.assertRaisesRegex(ValueError, "max_retry_delay_seconds"):
            HttpClient(max_retry_delay_seconds=0)
        with self.assertRaisesRegex(ValueError, "max_retry_delay_seconds"):
            HttpClient(max_retry_delay_seconds=-10.0)
        with self.assertRaisesRegex(ValueError, "max_retry_delay_seconds"):
            HttpClient(max_retry_delay_seconds=float("nan"))

    def test_per_request_timeout_validation(self):
        client = HttpClient(timeout=10.0)
        with self.assertRaisesRegex(ValueError, "timeout must be finite and greater than zero"):
            client.get("https://api.test/resource", timeout=0)
        with self.assertRaisesRegex(ValueError, "timeout must be finite and greater than zero"):
            client.get("https://api.test/resource", timeout=-2.0)
        with self.assertRaisesRegex(ValueError, "timeout must be finite and greater than zero"):
            client.get("https://api.test/resource", timeout=float("nan"))

    def test_ssl_error_fails_immediately_without_retrying(self):
        client = HttpClient(max_retries=3)
        ssl_error = URLError(ssl.SSLError("certificate verify failed"))

        with (
            patch("etl.http_client.urlopen", side_effect=ssl_error) as urlopen,
            patch("etl.http_client.time.sleep") as sleep,
        ):
            with self.assertRaises(URLError):
                client.get("https://api.test/secure-resource")

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_retry_after_http_date_and_503_status(self):
        client = HttpClient(max_retries=1)
        response = FakeResponse()
        target_time = datetime.now(timezone.utc) + timedelta(seconds=4)
        date_str = format_datetime(target_time)

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=[make_http_error(503, {"Retry-After": date_str}), response],
            ),
            patch("etl.http_client.time.sleep") as sleep,
        ):
            result = client.get("https://api.test/resource")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(sleep.call_count, 1)
        self.assertAlmostEqual(sleep.call_args[0][0], 4.0, delta=1.5)

    def test_retry_after_unparseable_falls_back_to_backoff(self):
        client = HttpClient(max_retries=1, backoff_seconds=0.3)
        response = FakeResponse()

        with (
            patch(
                "etl.http_client.urlopen",
                side_effect=[make_http_error(429, {"Retry-After": "invalid-date-string"}), response],
            ),
            patch("etl.http_client.time.sleep") as sleep,
        ):
            result = client.get("https://api.test/resource")

        self.assertEqual(result.status_code, 200)
        sleep.assert_called_once_with(0.3)

    def test_pagination_validates_arguments_and_callback_types(self):
        client = HttpClient(max_retries=0)

        # max_pages boundary
        with self.assertRaisesRegex(ValueError, "max_pages must be a positive integer"):
            list(client.iter_pages("https://api.test/p/1", lambda _: None, max_pages=0))
        with self.assertRaisesRegex(ValueError, "max_pages must be a positive integer"):
            list(client.iter_pages("https://api.test/p/1", lambda _: None, max_pages=-5))
        with self.assertRaisesRegex(ValueError, "max_pages must be a positive integer"):
            list(client.iter_pages("https://api.test/p/1", lambda _: None, max_pages="10"))  # type: ignore

        # Callback returns empty string
        with patch("etl.http_client.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(PaginationError, "next page URL must be a non-empty string"):
                list(client.iter_pages("https://api.test/p/1", lambda _: ""))

        # Callback returns non-string
        with patch("etl.http_client.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(PaginationError, "next page URL must be a non-empty string"):
                list(client.iter_pages("https://api.test/p/1", lambda _: 123))  # type: ignore

    def test_append_query_parameters_combines_with_existing_query(self):
        client = HttpClient(max_retries=0)
        response = FakeResponse()

        with patch("etl.http_client.urlopen", return_value=response) as urlopen:
            client.get(
                "https://api.test/items?filter=active",
                params={"sort": "desc", "page": 2},
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.test/items?filter=active&sort=desc&page=2",
        )


if __name__ == "__main__":
    unittest.main()
