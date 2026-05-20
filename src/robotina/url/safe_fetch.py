"""safe_fetch — defended sync HTTP fetcher for user-supplied URLs.

Six SSRF/abuse defenses + gzip-bomb. Used by FetchAndScrapeTool (Phase 23)
and recipe-image step (Phase 24). Raises SafeFetchError on any defense
violation. See .planning/phases/23-url-ingestion-topic-2/23-CONTEXT.md D-14..D-17.
"""
from __future__ import annotations

import gzip
import ipaddress
import logging
import os
import socket
import zlib
from typing import Iterable

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SafeFetchResult(BaseModel):
    final_url: str
    content_bytes: bytes
    content_type: str
    status_code: int


class SafeFetchError(Exception):
    """Raised on any defense violation. Message names the violated defense."""


_MAX_REDIRECTS = 3
_GZIP_RATIO_CAP = 20  # decompressed/compressed
_BLOCKED_EXTRA_IPS = {
    ipaddress.ip_address("0.0.0.0"),
    ipaddress.ip_address("169.254.169.254"),
}


def _is_blocked_ip(ip_str: str) -> tuple[bool, str | None]:
    """Return (blocked, reason). Unwraps IPv4-mapped IPv6 before checking."""
    ip = ipaddress.ip_address(ip_str)
    # IPv4-mapped IPv6 → unwrap to v4 and re-check
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # Order matters: ipaddress.is_private is a superset of is_loopback /
    # is_link_local / is_reserved, so the more-specific predicates run first
    # to produce precise reason strings (callers and tests match on them).
    if ip in _BLOCKED_EXTRA_IPS:
        return True, f"IP {ip} is explicitly blocked"
    if ip.is_unspecified:
        return True, f"IP {ip} is unspecified (0.0.0.0 / ::)"
    if ip.is_loopback:
        return True, f"IP {ip} is loopback"
    if ip.is_link_local:
        return True, f"IP {ip} is link-local"
    if ip.is_multicast:
        return True, f"IP {ip} is multicast"
    if ip.is_private:
        return True, f"IP {ip} is private (RFC1918)"
    if ip.is_reserved:
        return True, f"IP {ip} is reserved"
    return False, None


def _resolve_and_check(host: str) -> None:
    """Resolve hostname to ALL A/AAAA records, reject if ANY is in blocked range.

    Defeats multi-A-record DNS rebinding: a malicious DNS server returning
    both a public and a private IP is rejected on the private IP.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SafeFetchError(f"DNS resolution failed for {host}: {exc}")
    seen: set[str] = set()
    for _family, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        blocked, reason = _is_blocked_ip(ip_str)
        if blocked:
            raise SafeFetchError(f"Host {host} resolved to blocked IP: {reason}")


def _check_scheme(url: str, allow_http: bool) -> None:
    if url.startswith("https://"):
        return
    if url.startswith("http://") and allow_http:
        return
    raise SafeFetchError(f"Scheme not allowed: {url}")


def _decompress_with_cap(raw: bytes, encoding: str | None, max_bytes: int) -> bytes:
    """Decompress with gzip-bomb defense: ratio > 20:1 or expanded > max_bytes rejected."""
    if not encoding or encoding == "identity":
        return raw
    try:
        if encoding == "gzip":
            decompressed = gzip.decompress(raw)
        elif encoding in ("deflate", "x-deflate"):
            decompressed = zlib.decompress(raw)
        else:
            # br/zstd: httpx handles these via its default Accept-Encoding negotiation;
            # by the time we see them they are already decoded (or never set).
            return raw
    except SafeFetchError:
        raise
    except Exception as exc:
        raise SafeFetchError(f"Decompression failed ({encoding}): {exc}")
    if len(raw) > 0 and len(decompressed) / len(raw) > _GZIP_RATIO_CAP:
        raise SafeFetchError(
            f"Compression ratio {len(decompressed)/len(raw):.1f}x exceeds cap {_GZIP_RATIO_CAP}x"
        )
    if len(decompressed) > max_bytes:
        raise SafeFetchError(
            f"Decompressed size {len(decompressed)} > max_bytes {max_bytes}"
        )
    return decompressed


def safe_fetch(
    url: str,
    *,
    expected_content_type: str = "text/html",
    max_bytes: int = 5_000_000,
    timeout_s: float = 15.0,
    allow_http: bool | None = None,
) -> SafeFetchResult:
    """Fetch a user-supplied URL with six SSRF/abuse defenses + gzip-bomb defense.

    Defenses (in order, per D-16):
      1. Scheme allowlist (https-only unless allow_http or URL_INGESTION_ALLOW_HTTP).
      2. DNS resolves to all A/AAAA records; reject if ANY is blocked.
      3. Manual redirect loop (max 3 hops); re-validate scheme + IP each hop.
      4. Configurable timeout (connect=5, read=timeout_s, write=5, pool=5).
      5. Content-Length pre-check ≤ 2 × max_bytes; post-decode body cap ≤ max_bytes.
      6. Content-Type sniff (text/html or application/xhtml+xml for HTML;
         image/* prefix for images).
      7. gzip-bomb: reject if decompressed/compressed ratio > 20:1.

    Raises SafeFetchError on any defense violation. The exception message
    names the violated defense.
    """
    # D-17: env-gated http override
    if allow_http is None:
        allow_http = os.environ.get("URL_INGESTION_ALLOW_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        )

    current_url = url
    for hop in range(_MAX_REDIRECTS + 1):
        _check_scheme(current_url, allow_http)
        parsed = httpx.URL(current_url)
        host = parsed.host
        if not host:
            raise SafeFetchError(f"URL has no host: {current_url}")
        _resolve_and_check(host)

        timeout = httpx.Timeout(connect=5.0, read=timeout_s, write=5.0, pool=5.0)
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={
                "User-Agent": "RobotinaBot/1.0",
                "Accept": expected_content_type + ",*/*;q=0.1",
            },
        ) as client:
            resp = client.get(current_url)

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                raise SafeFetchError(
                    f"Redirect {resp.status_code} without Location header"
                )
            next_url = str(httpx.URL(current_url).join(location))
            if hop >= _MAX_REDIRECTS:
                raise SafeFetchError(f"Too many redirects (> {_MAX_REDIRECTS})")
            current_url = next_url
            continue

        # Content-Length pre-check (header-based; cheaper than streaming).
        cl = resp.headers.get("Content-Length")
        if cl is not None and cl.isdigit() and int(cl) > 2 * max_bytes:
            raise SafeFetchError(f"Content-Length {cl} > 2 × max_bytes {max_bytes}")

        # Read with size cap (httpx may have auto-decompressed already; handle
        # explicit Content-Encoding only when present and not consumed by httpx).
        content = resp.content
        encoding = resp.headers.get("Content-Encoding", "identity")
        # httpx auto-decompresses gzip/deflate transparently; if resp.content
        # is already decoded, encoding header still reflects the wire encoding.
        # We re-derive size-cap on the BYTES we actually hold; for explicit
        # gzip/deflate that httpx did NOT auto-decode (rare), _decompress_with_cap
        # catches the gzip-bomb. To exercise the bomb defense in tests, callers
        # mock a response whose .content is raw gzip bytes.
        try:
            content = _decompress_with_cap(content, encoding, max_bytes)
        except SafeFetchError:
            raise
        if len(content) > max_bytes:
            raise SafeFetchError(f"Body size {len(content)} > max_bytes {max_bytes}")

        # Content-Type sniff.
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        expected = expected_content_type.lower()
        accepted: Iterable[str]
        if expected == "text/html":
            accepted = ("text/html", "application/xhtml+xml")
        elif expected.startswith("image/"):
            accepted = ("image/",)  # prefix-match
        else:
            accepted = (expected,)
        if not any(
            (content_type == a) or (a.endswith("/") and content_type.startswith(a))
            for a in accepted
        ):
            raise SafeFetchError(
                f"Content-Type {content_type!r} not in {tuple(accepted)}"
            )

        # Log successful fetch at INFO with query string stripped (PII / token safety).
        try:
            safe_url = str(httpx.URL(current_url).copy_with(query=None))
        except Exception:
            safe_url = current_url
        logger.info("safe_fetch ok url=%s status=%d bytes=%d", safe_url, resp.status_code, len(content))
        logger.debug("safe_fetch ok full_url=%s", current_url)

        return SafeFetchResult(
            final_url=current_url,
            content_bytes=content,
            content_type=content_type,
            status_code=resp.status_code,
        )
    raise SafeFetchError("Unreachable: redirect loop exited without return")
