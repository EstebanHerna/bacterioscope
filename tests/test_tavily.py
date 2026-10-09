"""Tests for fixed-query Tavily integration using mocked HTTP responses."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from bacterioscope.integrations.tavily import (
    AlertSource,
    TavilyAlertSearch,
    TavilyConfigurationError,
    TavilySearchError,
)


class _Response:
    status = 200

    def __init__(self, payload: dict) -> None:
        self._body = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body.read()


def test_missing_api_key_fails_without_network_call() -> None:
    client = TavilyAlertSearch(api_key="")
    with patch("bacterioscope.integrations.tavily.urlopen") as open_mock:
        with pytest.raises(TavilyConfigurationError, match="TAVILY_API_KEY"):
            client.search_amr_alerts(AlertSource.INS)
    open_mock.assert_not_called()


def test_ins_search_uses_fixed_query_domain_filter_and_returns_allowlisted_results() -> None:
    response = _Response(
        {
            "results": [
                {
                    "title": "  Alerta   oficial ",
                    "url": "https://www.ins.gov.co/alerta/1",
                    "content": "  Texto   del aviso ",
                    "published_date": "2026-10-01",
                },
                {
                    "title": "External result",
                    "url": "https://example.org/alerta",
                    "content": "Must be rejected",
                },
                {
                    "title": "Insecure result",
                    "url": "http://ins.gov.co/alerta",
                    "content": "Must be rejected",
                },
            ]
        }
    )
    with patch("bacterioscope.integrations.tavily.urlopen", return_value=response) as open_mock:
        result = TavilyAlertSearch(api_key="server-secret", max_results=5).search_amr_alerts("ins")

    request = open_mock.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["include_domains"] == ["ins.gov.co"]
    assert payload["include_domains_mode"] == "restrict"
    assert payload["query"] == "alerta resistencia antimicrobiana Colombia"
    assert payload["include_answer"] is False
    assert "server-secret" not in payload["query"]
    assert len(result) == 1
    assert result[0].title == "Alerta oficial"
    assert result[0].snippet == "Texto del aviso"
    assert result[0].source == "ins"


def test_ops_uses_paho_domain_and_limits_result_count() -> None:
    response = _Response(
        {"results": [{"title": f"Alert {i}", "url": f"https://paho.org/{i}"} for i in range(4)]}
    )
    with patch("bacterioscope.integrations.tavily.urlopen", return_value=response) as open_mock:
        results = TavilyAlertSearch(api_key="key", max_results=2).search_amr_alerts("ops")

    payload = json.loads(open_mock.call_args.args[0].data)
    assert payload["include_domains"] == ["paho.org"]
    assert len(results) == 2


def test_invalid_source_is_rejected_before_network_call() -> None:
    with patch("bacterioscope.integrations.tavily.urlopen") as open_mock:
        with pytest.raises(ValueError, match="source must"):
            TavilyAlertSearch(api_key="key").search_amr_alerts("anywhere")
    open_mock.assert_not_called()


def test_http_errors_do_not_expose_credentials() -> None:
    error = HTTPError("https://api.tavily.com/search", 401, "Unauthorized", {}, None)
    with patch("bacterioscope.integrations.tavily.urlopen", side_effect=error):
        with pytest.raises(TavilySearchError) as raised:
            TavilyAlertSearch(api_key="do-not-print-me").search_amr_alerts("ops")
    assert "do-not-print-me" not in str(raised.value)
    assert "401" in str(raised.value)
