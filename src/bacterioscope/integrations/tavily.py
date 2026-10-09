"""Tavily search for public INS/OPS antimicrobial-resistance alerts.

Queries are fixed and contain no isolate, patient, or laboratory result data.
Returned pages are untrusted references and are never treated as AST evidence.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_DOMAIN_BY_SOURCE = {
    "ins": ("ins.gov.co",),
    "ops": ("paho.org",),
}
_QUERY_BY_SOURCE = {
    "ins": "alerta resistencia antimicrobiana Colombia",
    "ops": "alerta resistencia antimicrobiana Americas",
}


class AlertSource(str, Enum):
    INS = "ins"
    OPS = "ops"


class TavilyConfigurationError(RuntimeError):
    """Raised when Tavily has not been configured with a server-side key."""


class TavilySearchError(RuntimeError):
    """Raised when Tavily returns an unusable response."""


@dataclass(frozen=True)
class PublicAlert:
    source: str
    title: str
    url: str
    snippet: str
    published_date: str | None = None


class TavilyAlertSearch:
    """Small stdlib client for the allowlisted public-health search workflow."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 10.0,
        max_results: int = 5,
    ) -> None:
        self._api_key = (api_key if api_key is not None else os.getenv("TAVILY_API_KEY", ""))
        self._timeout_seconds = timeout_seconds
        self._max_results = max(1, min(max_results, 10))

    @property
    def configured(self) -> bool:
        return bool(self._api_key.strip())

    def search_amr_alerts(self, source: AlertSource | str) -> list[PublicAlert]:
        """Search one official source; source must be INS or OPS."""

        try:
            selected = AlertSource(source)
        except ValueError as exc:
            raise ValueError("source must be 'ins' or 'ops'") from exc
        if not self.configured:
            raise TavilyConfigurationError("TAVILY_API_KEY is not configured")

        domains = _DOMAIN_BY_SOURCE[selected.value]
        payload = {
            "query": _QUERY_BY_SOURCE[selected.value],
            "topic": "news",
            "search_depth": "basic",
            "max_results": self._max_results,
            "include_domains": list(domains),
            "include_domains_mode": "restrict",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_favicon": False,
            "include_published_date": True,
            "include_usage": False,
        }
        request = Request(
            TAVILY_SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            # The URL is a fixed HTTPS endpoint; no caller-controlled URL reaches this call.
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310
                if response.status < 200 or response.status >= 300:
                    raise TavilySearchError(f"Tavily returned HTTP {response.status}")
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise TavilySearchError(f"Tavily returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TavilySearchError("Tavily request failed") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TavilySearchError("Tavily returned invalid JSON") from exc

        raw_results: Any = body.get("results") if isinstance(body, dict) else None
        if not isinstance(raw_results, list):
            raise TavilySearchError("Tavily response is missing a results list")

        alerts: list[PublicAlert] = []
        allowed_domain = domains[0]
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            if not isinstance(url, str) or not _url_is_in_domain(url, allowed_domain):
                continue
            if not isinstance(title, str) or not title.strip():
                continue
            snippet = item.get("content", "")
            published = item.get("published_date")
            alerts.append(
                PublicAlert(
                    source=selected.value,
                    title=_clean_text(title, 300),
                    url=url,
                    snippet=_clean_text(snippet, 1200) if isinstance(snippet, str) else "",
                    published_date=(
                        _clean_text(published, 80) if isinstance(published, str) else None
                    ),
                )
            )
            if len(alerts) >= self._max_results:
                break
        return alerts


def _url_is_in_domain(url: str, domain: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    return parsed.scheme == "https" and (hostname == domain or hostname.endswith("." + domain))


def _clean_text(value: str, max_length: int) -> str:
    text = re.sub(r"<[^>]*>", " ", unescape(value))
    return " ".join(text.split())[:max_length]
