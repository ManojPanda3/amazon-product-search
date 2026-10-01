"""HTTP transport: TLS/HTTP2 browser impersonation plus anti-bot retry.

Amazon gates ``/s`` behind bot management that inspects the TLS and HTTP/2
fingerprints of the client, not just headers. A plain ``requests``/``httpx``
call from a datacenter IP gets a ``503`` "Sorry! Something went wrong!" page.
``curl_cffi`` impersonates a real browser's TLS ClientHello and HTTP/2 SETTINGS
frame, which is what Amazon actually keys on, so this is the load-bearing part.

Two layers of defence:

1. **Impersonation** -- each request is sent with one of several browser
   profiles (see :data:`IMPERSONATE_PROFILES`).
2. **Detect-and-retry** -- a response is treated as a block when the status is
   non-200 *or* the body carries a known challenge marker
   (see :data:`BLOCK_MARKERS`). On a block the transport sleeps with backoff
   and retries under a *different* profile, since the block tends to follow the
   fingerprint rather than the URL.

The module is transport-only: it knows how to fetch a URL, not what a product
is. Everything above it works on an HTML string.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import time
from typing import Any, Awaitable, Callable, Optional, Sequence

from curl_cffi import requests as curl_requests
from curl_cffi.requests import AsyncSession, Session
from curl_cffi.requests.errors import RequestsError

__all__ = [
    "Transport",
    "TransportError",
    "IMPERSONATE_PROFILES",
    "BLOCK_MARKERS",
    "is_blocked",
]

# Browser fingerprints rotated across requests. All of these exist in every
# curl_cffi release that ships them (>=0.13), so no runtime feature probing is
# needed. Deliberately a mix of Chrome and Safari generations: a single stuck
# profile is survivable because the next attempt rotates away from it.
IMPERSONATE_PROFILES: tuple[str, ...] = (
    "chrome124",
    "chrome120",
    "safari184",
    "chrome119",
    "chrome116",
    "chrome101",
)

# Substrings that identify an Amazon bot challenge. A 200 is *not* success here:
# the interstitial challenge page (bm-verify), the 503 error page and the
# "contact api-services-support" notice all return HTML that parses to zero
# products, so they must be caught before parsing.
BLOCK_MARKERS: tuple[str, ...] = (
    "Something went wrong",
    "bm-verify",
    "api-services-support@amazon.com",
    "Enter the characters you see",
    "To discuss automated access",
)

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Raised when every attempt for a URL was blocked or errored."""


def is_blocked(body: str) -> bool:
    """True if ``body`` looks like an Amazon bot challenge rather than results."""
    return any(marker in body for marker in BLOCK_MARKERS)


class Transport:
    """Fetches URLs from Amazon, impersonating browsers and retrying blocks.

    Args:
        timeout (int): Per-request timeout in seconds. Default 20 rather than a
            tighter value because a search page is ~1 MB and a too-low budget
            aborts mid-body ("timed out with N bytes received") on slow links.
        max_attempts (int): Total attempts per URL before raising. Capped at
            ``len(IMPERSONATE_PROFILES)`` since each attempt needs a fresh
            fingerprint to be worth anything.
        profiles (Sequence[str]): Fingerprints to rotate through.
        backoff (float): Base seconds for exponential backoff between attempts.
        accept_language (str): ``Accept-Language`` header. ``User-Agent`` is
            deliberately *not* sent: with impersonation active, a hand-written UA
            that disagrees with the TLS fingerprint is itself a detection signal.
        debug (bool): Log every attempt outcome.
        session (Any): Pre-built sync session. Injectable so tests can exercise
            the retry logic against a scripted double instead of the network.
        async_session_factory (Callable[[], Any]): Builds the async session for
            a loop, injectable for the same reason as ``session``.
    """

    def __init__(
        self,
        timeout: int = 20,
        max_attempts: int = 4,
        profiles: Optional[Sequence[str]] = None,
        backoff: float = 0.4,
        accept_language: str = "en-US,en;q=0.9",
        debug: bool = False,
        session: Optional[Any] = None,
        async_session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.timeout = timeout
        self.backoff = backoff
        self.accept_language = accept_language
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if debug else logging.ERROR)

        self._profiles: tuple[str, ...] = tuple(
            profiles if profiles is not None else IMPERSONATE_PROFILES
        )
        if not self._profiles:
            raise ValueError("at least one impersonate profile is required")

        self.max_attempts = max(1, min(max_attempts, len(self._profiles)))

        # Round-robin over profiles so consecutive requests do not all present
        # the same fingerprint. itertools.cycle is thread-safe enough here: the
        # counter update is a single bytecode-level step under the GIL.
        self._cycle = itertools.cycle(self._profiles)

        self._headers = {"Accept-Language": accept_language}
        self._session: Optional[Any] = None
        self._injected_session = session
        self._async_session_factory = async_session_factory
        self._async_sessions: dict[asyncio.AbstractEventLoop, Any] = {}

    # ------------------------------------------------------------------ sync

    def _get_session(self) -> Any:
        if self._session is None:
            self._session = self._injected_session or Session(headers=self._headers)
        return self._session

    def get(self, url: str) -> str:
        """Fetch ``url`` and return its HTML, rotating profiles past blocks.

        Raises:
            TransportError: If every attempt was blocked or failed.
        """
        session = self._get_session()
        return self._run_sync(url, lambda profile: self._attempt(url, session, profile))

    def _attempt(self, url: str, session: Any, profile: str) -> Optional[str]:
        """One request. Returns HTML when clean, ``None`` when blocked/failed."""
        try:
            response = session.get(url, impersonate=profile, timeout=self.timeout)
        except RequestsError as error:
            self.logger.debug("request failed profile=%s url=%s error=%s", profile, url, error)
            return None

        body = response.text
        if response.status_code == 200 and not is_blocked(body):
            return body

        reason = "blocked" if is_blocked(body) else f"status {response.status_code}"
        self.logger.debug(
            "attempt rejected (%s) profile=%s url=%s bytes=%s", reason, profile, url, len(body)
        )
        return None

    def _run_sync(self, url: str, attempt: Callable[[str], Optional[str]]) -> str:
        last_reason = "no attempt made"
        for index in range(self.max_attempts):
            profile = next(self._cycle)
            body = attempt(profile)
            if body is not None:
                return body
            last_reason = f"profile={profile}"
            if index < self.max_attempts - 1:
                time.sleep(self.backoff * (2**index))
        raise TransportError(
            f"amazon blocked {url} after {self.max_attempts} attempts ({last_reason})"
        )

    # ----------------------------------------------------------------- async

    def _get_async_session(self) -> AsyncSession:
        """Return an AsyncSession bound to the running loop.

        curl_cffi's AsyncSession holds sockets registered with the loop that
        created it, so one cannot be reused from a second ``asyncio.run()``.
        Keying the cache on the loop keeps repeated calls correct -- the test
        suite and any ``asyncio.run(amazon.async_search(...))`` one-liner both
        create a fresh loop per call.
        """
        loop = asyncio.get_running_loop()
        session = self._async_sessions.get(loop)
        if session is None:
            if self._async_session_factory is not None:
                session = self._async_session_factory()
            else:
                session = AsyncSession(headers=self._headers, max_clients=10)
            self._async_sessions[loop] = session
        return session

    async def aget(self, url: str) -> str:
        """Async twin of :meth:`get`."""
        session = self._get_async_session()
        return await self._run_async(
            url, lambda profile: self._attempt_async(url, session, profile)
        )

    async def _attempt_async(self, url: str, session: Any, profile: str) -> Optional[str]:
        try:
            response = await session.get(url, impersonate=profile, timeout=self.timeout)
        except RequestsError as error:
            self.logger.debug("request failed profile=%s url=%s error=%s", profile, url, error)
            return None

        body = response.text
        if response.status_code == 200 and not is_blocked(body):
            return body

        reason = "blocked" if is_blocked(body) else f"status {response.status_code}"
        self.logger.debug(
            "attempt rejected (%s) profile=%s url=%s bytes=%s", reason, profile, url, len(body)
        )
        return None

    async def _run_async(
        self, url: str, attempt: Callable[[str], Awaitable[Optional[str]]]
    ) -> str:
        last_reason = "no attempt made"
        for index in range(self.max_attempts):
            profile = next(self._cycle)
            body = await attempt(profile)
            if body is not None:
                return body
            last_reason = f"profile={profile}"
            if index < self.max_attempts - 1:
                await asyncio.sleep(self.backoff * (2**index))
        raise TransportError(
            f"amazon blocked {url} after {self.max_attempts} attempts ({last_reason})"
        )

    # ----------------------------------------------------------------- close

    def close(self) -> None:
        """Close the sync session. Idempotent."""
        if self._session is not None:
            self._session.close()
            self._session = None

    async def aclose(self) -> None:
        """Close every async session. Idempotent.

        Must be awaited from a loop that is still running, so callers inside
        ``async with Amazon()`` use this while ``close()`` is the sync path's.
        """
        sessions = list(self._async_sessions.values())
        self._async_sessions.clear()
        for session in sessions:
            try:
                await session.close()
            except Exception:  # noqa: BLE001 - teardown must not raise
                self.logger.debug("async session close failed", exc_info=True)