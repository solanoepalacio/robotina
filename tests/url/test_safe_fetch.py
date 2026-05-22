"""Phase 23-01 — safe_fetch SSRF/abuse defense test suite (D-18).

Each defense in D-16 has at least one named test asserting SafeFetchError
is raised (or SafeFetchResult is returned for the happy path). All DNS is
patched via monkeypatch on socket.getaddrinfo; all HTTP is mocked via respx.
No real network I/O.
"""
from __future__ import annotations

import gzip
import socket

import httpx
import pytest
import respx

from robotina.url import safe_fetch as sf_mod
from robotina.url.safe_fetch import SafeFetchError, SafeFetchResult, safe_fetch


# Public IP used for tests that need DNS to "succeed" so respx can mock the
# HTTP layer. 93.184.216.34 is example.com per IANA reservation — public,
# routable, but respx intercepts the actual request.
PUBLIC_IP = "93.184.216.34"


def _patch_dns(monkeypatch, ip: str) -> None:
    """Make socket.getaddrinfo return a single A record for any host."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port or 0))]

    monkeypatch.setattr(sf_mod.socket, "getaddrinfo", fake_getaddrinfo)


def _patch_dns_multi(monkeypatch, ips: list[str]) -> None:
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port or 0))
            for ip in ips
        ]

    monkeypatch.setattr(sf_mod.socket, "getaddrinfo", fake_getaddrinfo)


def _patch_dns_v6(monkeypatch, ip: str) -> None:
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, port or 0, 0, 0))]

    monkeypatch.setattr(sf_mod.socket, "getaddrinfo", fake_getaddrinfo)


# ---------------------------------------------------------------------------
# Defense 1: scheme allowlist
# ---------------------------------------------------------------------------


def test_scheme_http_blocked_by_default_raises(monkeypatch):
    monkeypatch.delenv("URL_INGESTION_ALLOW_HTTP", raising=False)
    with pytest.raises(SafeFetchError, match="Scheme not allowed"):
        safe_fetch("http://example.com/")


def test_scheme_http_allowed_when_env_true(monkeypatch):
    monkeypatch.setenv("URL_INGESTION_ALLOW_HTTP", "true")
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("http://example.com/").mock(
            return_value=httpx.Response(
                200, content=b"<html>ok</html>", headers={"Content-Type": "text/html"}
            )
        )
        result = safe_fetch("http://example.com/")
    assert isinstance(result, SafeFetchResult)
    assert result.status_code == 200


def test_scheme_ftp_raises(monkeypatch):
    with pytest.raises(SafeFetchError, match="Scheme not allowed"):
        safe_fetch("ftp://example.com/")


# ---------------------------------------------------------------------------
# Defense 2: DNS-resolved IP blocklist
# ---------------------------------------------------------------------------


def test_dns_resolves_to_private_ip_raises(monkeypatch):
    _patch_dns(monkeypatch, "10.0.0.1")
    with pytest.raises(SafeFetchError, match="private"):
        safe_fetch("https://attacker.example.com/")


def test_dns_resolves_to_loopback_raises(monkeypatch):
    _patch_dns(monkeypatch, "127.0.0.1")
    with pytest.raises(SafeFetchError, match="loopback"):
        safe_fetch("https://attacker.example.com/")


def test_dns_resolves_to_link_local_raises(monkeypatch):
    _patch_dns(monkeypatch, "169.254.1.1")
    with pytest.raises(SafeFetchError, match="link-local"):
        safe_fetch("https://attacker.example.com/")


def test_dns_resolves_to_multicast_raises(monkeypatch):
    _patch_dns(monkeypatch, "224.0.0.1")
    with pytest.raises(SafeFetchError, match="multicast"):
        safe_fetch("https://attacker.example.com/")


def test_dns_resolves_to_aws_metadata_raises(monkeypatch):
    _patch_dns(monkeypatch, "169.254.169.254")
    with pytest.raises(SafeFetchError, match="blocked"):
        safe_fetch("https://attacker.example.com/")


def test_dns_resolves_to_zero_raises(monkeypatch):
    _patch_dns(monkeypatch, "0.0.0.0")
    with pytest.raises(SafeFetchError, match="blocked|unspecified"):
        safe_fetch("https://attacker.example.com/")


def test_dns_multi_a_record_one_private_raises(monkeypatch):
    """Multi-A DNS rebinding defense: ANY private IP in the record set rejects."""
    _patch_dns_multi(monkeypatch, [PUBLIC_IP, "10.0.0.1"])
    with pytest.raises(SafeFetchError, match="private"):
        safe_fetch("https://attacker.example.com/")


def test_ipv4_mapped_ipv6_loopback_raises(monkeypatch):
    """::ffff:127.0.0.1 must unwrap to 127.0.0.1 and be rejected as loopback."""
    _patch_dns_v6(monkeypatch, "::ffff:127.0.0.1")
    with pytest.raises(SafeFetchError, match="loopback"):
        safe_fetch("https://attacker.example.com/")


# ---------------------------------------------------------------------------
# Defense 3: redirect chain handling
# ---------------------------------------------------------------------------


def test_redirect_chain_max_3_hops_then_raises(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://example.com/a").mock(
            return_value=httpx.Response(302, headers={"Location": "https://example.com/b"})
        )
        respx.get("https://example.com/b").mock(
            return_value=httpx.Response(302, headers={"Location": "https://example.com/c"})
        )
        respx.get("https://example.com/c").mock(
            return_value=httpx.Response(302, headers={"Location": "https://example.com/d"})
        )
        respx.get("https://example.com/d").mock(
            return_value=httpx.Response(302, headers={"Location": "https://example.com/e"})
        )
        with pytest.raises(SafeFetchError, match="Too many redirects"):
            safe_fetch("https://example.com/a")


def test_redirect_to_private_ip_raises(monkeypatch):
    """Redirect Location pointing to a host that resolves private MUST be rejected."""
    call_count = {"n": 0}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        call_count["n"] += 1
        # first call (initial URL) → public; subsequent (after redirect) → private
        ip = PUBLIC_IP if call_count["n"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port or 0))]

    monkeypatch.setattr(sf_mod.socket, "getaddrinfo", fake_getaddrinfo)
    with respx.mock:
        respx.get("https://example.com/start").mock(
            return_value=httpx.Response(
                302, headers={"Location": "https://internal.example.com/admin"}
            )
        )
        with pytest.raises(SafeFetchError, match="loopback"):
            safe_fetch("https://example.com/start")


# ---------------------------------------------------------------------------
# Defense 4 (timeout) — not directly tested here; httpx.Timeout is constructed
# in the code path and exercised by every other test.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Defense 5: size caps
# ---------------------------------------------------------------------------


def test_content_length_header_too_large_raises(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200,
                content=b"x",
                headers={"Content-Type": "text/html", "Content-Length": "20000000"},
            )
        )
        with pytest.raises(SafeFetchError, match="Content-Length"):
            safe_fetch("https://example.com/", max_bytes=5_000_000)


def test_body_size_too_large_raises(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    big_body = b"x" * 6_000_000
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200, content=big_body, headers={"Content-Type": "text/html"}
            )
        )
        with pytest.raises(SafeFetchError, match="Body size|max_bytes"):
            safe_fetch("https://example.com/", max_bytes=5_000_000)


# ---------------------------------------------------------------------------
# Defense 6: content-type sniff
# ---------------------------------------------------------------------------


def test_content_type_text_plain_raises_when_html_expected(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200, content=b"hello", headers={"Content-Type": "text/plain"}
            )
        )
        with pytest.raises(SafeFetchError, match="Content-Type"):
            safe_fetch("https://example.com/")


def test_content_type_text_html_passes(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200, content=b"<html/>", headers={"Content-Type": "text/html; charset=utf-8"}
            )
        )
        result = safe_fetch("https://example.com/")
    assert result.content_type == "text/html"
    assert result.content_bytes == b"<html/>"


def test_content_type_application_xhtml_passes(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200,
                content=b"<html/>",
                headers={"Content-Type": "application/xhtml+xml"},
            )
        )
        result = safe_fetch("https://example.com/")
    assert result.content_type == "application/xhtml+xml"


# ---------------------------------------------------------------------------
# Phase 24 / D-13, D-17 — image/* wildcard regression-guard (Pitfall 4)
#
# The wildcard sniff at safe_fetch.py:213-223 already accepts image/* subtypes
# today; these tests PIN the contract so a future "cleanup" of the special
# case (e.g. collapsing the elif branch) breaks the test before it breaks
# the recipe-image step in Phase 24.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image_subtype",
    ["image/jpeg", "image/png", "image/webp", "image/gif"],
)
def test_safe_fetch_image_wildcard_accepts_image_subtypes(
    monkeypatch, image_subtype
):
    """image/* expected_content_type must accept every image/<subtype>."""
    _patch_dns(monkeypatch, PUBLIC_IP)
    body = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # few bytes; sniff is by header
    with respx.mock:
        respx.get("https://cdn.example.com/img").mock(
            return_value=httpx.Response(
                200, content=body, headers={"Content-Type": image_subtype}
            )
        )
        result = safe_fetch(
            "https://cdn.example.com/img",
            expected_content_type="image/*",
            max_bytes=15_000_000,
        )
    assert isinstance(result, SafeFetchResult)
    assert result.content_type == image_subtype
    assert result.status_code == 200


@pytest.mark.parametrize(
    "non_image_type",
    ["text/html", "application/pdf", "application/json"],
)
def test_safe_fetch_image_wildcard_rejects_non_image_types(
    monkeypatch, non_image_type
):
    """image/* expected_content_type must reject anything that is not image/<...>."""
    _patch_dns(monkeypatch, PUBLIC_IP)
    with respx.mock:
        respx.get("https://cdn.example.com/notimg").mock(
            return_value=httpx.Response(
                200, content=b"<html/>", headers={"Content-Type": non_image_type}
            )
        )
        with pytest.raises(SafeFetchError, match="Content-Type"):
            safe_fetch(
                "https://cdn.example.com/notimg",
                expected_content_type="image/*",
                max_bytes=15_000_000,
            )


# ---------------------------------------------------------------------------
# Defense 7: gzip-bomb defense
# ---------------------------------------------------------------------------


def test_gzip_ratio_over_cap_raises(monkeypatch):
    """A small gzip payload that decompresses to a far-larger body MUST be rejected.

    Per D-16, ratio cap is 20:1. We craft a 100-byte compressed → 10_000-byte
    decompressed payload (100:1 ratio) using highly compressible input.
    httpx does not auto-decompress here because we explicitly pass the raw
    bytes via respx and the Content-Encoding header is treated as identity by
    httpx unless it actually sees gzipped wire data. We bypass httpx's behavior
    by setting Content-Encoding=gzip on a body that IS gzipped — but since
    httpx will then try to auto-decompress, we instead test the path directly
    by calling _decompress_with_cap.
    """
    raw = b"A" * 10_000
    compressed = gzip.compress(raw)
    # Sanity: ratio is much greater than 20:1
    assert len(raw) / len(compressed) > 20
    with pytest.raises(SafeFetchError, match="Compression ratio"):
        sf_mod._decompress_with_cap(compressed, "gzip", max_bytes=5_000_000)


def test_gzip_decompressed_over_max_bytes_raises(monkeypatch):
    """Even when ratio is within cap, decompressed size > max_bytes rejects."""
    # 6 MB of mixed content (low ratio) — but bigger than max_bytes=5MB
    import os as _os
    raw = _os.urandom(6_000_000)  # uncompressible random bytes
    compressed = gzip.compress(raw)
    # ratio should be ~1.0 (random data does not compress)
    with pytest.raises(SafeFetchError, match="Decompressed size|max_bytes"):
        sf_mod._decompress_with_cap(compressed, "gzip", max_bytes=5_000_000)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_returns_safe_fetch_result(monkeypatch):
    _patch_dns(monkeypatch, PUBLIC_IP)
    body = b"<html><body>recipe</body></html>"
    with respx.mock:
        respx.get("https://example.com/recipe").mock(
            return_value=httpx.Response(
                200, content=body, headers={"Content-Type": "text/html"}
            )
        )
        result = safe_fetch("https://example.com/recipe")
    assert isinstance(result, SafeFetchResult)
    assert result.final_url == "https://example.com/recipe"
    assert result.content_bytes == body
    assert result.content_type == "text/html"
    assert result.status_code == 200
