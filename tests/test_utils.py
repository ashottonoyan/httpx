import io
import json
import logging
import os
import random
import tempfile

import pytest

import httpx
from httpx._utils import (
    URLPattern,
    get_environment_proxies,
    is_ipv4_hostname,
    is_ipv6_hostname,
    peek_filelike_length,
    primitive_value_to_str,
    to_bytes,
    to_bytes_or_str,
    to_str,
    unquote,
)


@pytest.mark.parametrize(
    "encoding",
    (
        "utf-32",
        "utf-8-sig",
        "utf-16",
        "utf-8",
        "utf-16-be",
        "utf-16-le",
        "utf-32-be",
        "utf-32-le",
    ),
)
def test_encoded(encoding):
    content = '{"abc": 123}'.encode(encoding)
    response = httpx.Response(200, content=content)
    assert response.json() == {"abc": 123}


def test_bad_utf_like_encoding():
    content = b"\x00\x00\x00\x00"
    response = httpx.Response(200, content=content)
    with pytest.raises(json.decoder.JSONDecodeError):
        response.json()


@pytest.mark.parametrize(
    ("encoding", "expected"),
    (
        ("utf-16-be", "utf-16"),
        ("utf-16-le", "utf-16"),
        ("utf-32-be", "utf-32"),
        ("utf-32-le", "utf-32"),
    ),
)
def test_guess_by_bom(encoding, expected):
    content = '\ufeff{"abc": 123}'.encode(encoding)
    response = httpx.Response(200, content=content)
    assert response.json() == {"abc": 123}


def test_logging_request(server, caplog):
    caplog.set_level(logging.INFO)
    with httpx.Client() as client:
        response = client.get(server.url)
        assert response.status_code == 200

    assert caplog.record_tuples == [
        (
            "httpx",
            logging.INFO,
            'HTTP Request: GET http://127.0.0.1:8000/ "HTTP/1.1 200 OK"',
        )
    ]


def test_logging_redirect_chain(server, caplog):
    caplog.set_level(logging.INFO)
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(server.url.copy_with(path="/redirect_301"))
        assert response.status_code == 200

    assert caplog.record_tuples == [
        (
            "httpx",
            logging.INFO,
            "HTTP Request: GET http://127.0.0.1:8000/redirect_301"
            ' "HTTP/1.1 301 Moved Permanently"',
        ),
        (
            "httpx",
            logging.INFO,
            'HTTP Request: GET http://127.0.0.1:8000/ "HTTP/1.1 200 OK"',
        ),
    ]


@pytest.mark.parametrize(
    ["environment", "proxies"],
    [
        ({}, {}),
        ({"HTTP_PROXY": "http://127.0.0.1"}, {"http://": "http://127.0.0.1"}),
        (
            {"https_proxy": "http://127.0.0.1", "HTTP_PROXY": "https://127.0.0.1"},
            {"https://": "http://127.0.0.1", "http://": "https://127.0.0.1"},
        ),
        ({"all_proxy": "http://127.0.0.1"}, {"all://": "http://127.0.0.1"}),
        ({"TRAVIS_APT_PROXY": "http://127.0.0.1"}, {}),
        ({"no_proxy": "127.0.0.1"}, {"all://127.0.0.1": None}),
        ({"no_proxy": "192.168.0.0/16"}, {"all://192.168.0.0/16": None}),
        ({"no_proxy": "::1"}, {"all://[::1]": None}),
        ({"no_proxy": "localhost"}, {"all://localhost": None}),
        ({"no_proxy": "github.com"}, {"all://*github.com": None}),
        ({"no_proxy": ".github.com"}, {"all://*.github.com": None}),
        ({"no_proxy": "http://github.com"}, {"http://github.com": None}),
    ],
)
def test_get_environment_proxies(environment, proxies):
    os.environ.update(environment)

    assert get_environment_proxies() == proxies


@pytest.mark.parametrize(
    ["pattern", "url", "expected"],
    [
        ("http://example.com", "http://example.com", True),
        ("http://example.com", "https://example.com", False),
        ("http://example.com", "http://other.com", False),
        ("http://example.com:123", "http://example.com:123", True),
        ("http://example.com:123", "http://example.com:456", False),
        ("http://example.com:123", "http://example.com", False),
        ("all://example.com", "http://example.com", True),
        ("all://example.com", "https://example.com", True),
        ("http://", "http://example.com", True),
        ("http://", "https://example.com", False),
        ("all://", "https://example.com:123", True),
        ("", "https://example.com:123", True),
    ],
)
def test_url_matches(pattern, url, expected):
    pattern = URLPattern(pattern)
    assert pattern.matches(httpx.URL(url)) == expected


def test_pattern_priority():
    matchers = [
        URLPattern("all://"),
        URLPattern("http://"),
        URLPattern("http://example.com"),
        URLPattern("http://example.com:123"),
    ]
    random.shuffle(matchers)
    assert sorted(matchers) == [
        URLPattern("http://example.com:123"),
        URLPattern("http://example.com"),
        URLPattern("http://"),
        URLPattern("all://"),
    ]


@pytest.mark.parametrize(
    ["value", "expected"],
    [
        (True, "true"),
        (False, "false"),
        (None, ""),
        ("abc", "abc"),
        (123, "123"),
        (1.5, "1.5"),
        (0, "0"),
        ("", ""),
    ],
)
def test_primitive_value_to_str(value, expected):
    assert primitive_value_to_str(value) == expected


def test_to_bytes_from_str():
    assert to_bytes("hello") == b"hello"


def test_to_bytes_from_bytes_is_passthrough():
    data = b"\x00\x01\x02"
    assert to_bytes(data) is data


def test_to_bytes_with_custom_encoding():
    assert to_bytes("café", encoding="latin-1") == "café".encode("latin-1")


def test_to_str_from_bytes():
    assert to_str(b"hello") == "hello"


def test_to_str_from_str_is_passthrough():
    s = "already a string"
    assert to_str(s) is s


def test_to_str_with_custom_encoding():
    encoded = "café".encode("latin-1")
    assert to_str(encoded, encoding="latin-1") == "café"


def test_to_bytes_or_str_matching_str():
    # match_type_of is a str → return str
    result = to_bytes_or_str("value", match_type_of="other")
    assert isinstance(result, str)
    assert result == "value"


def test_to_bytes_or_str_matching_bytes():
    # match_type_of is bytes → return bytes
    result = to_bytes_or_str("value", match_type_of=b"other")
    assert isinstance(result, bytes)
    assert result == b"value"


@pytest.mark.parametrize(
    ["value", "expected"],
    [
        ('"quoted"', "quoted"),
        ("not quoted", "not quoted"),
        ('"', '"'),  # single char, both ends same char but length 1 → value[0]==value[-1]
        ('"unbalanced', '"unbalanced'),
        ('unbalanced"', 'unbalanced"'),
        ('""', ""),
        ("'single'", "'single'"),  # only double-quote stripping
    ],
)
def test_unquote(value, expected):
    assert unquote(value) == expected


def test_peek_filelike_length_with_real_file():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"hello world")
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            assert peek_filelike_length(f) == 11
    finally:
        os.unlink(tmp_path)


def test_peek_filelike_length_with_bytesio():
    stream = io.BytesIO(b"hello world")
    # Advance the position to confirm it is preserved after peeking.
    stream.read(3)
    assert peek_filelike_length(stream) == 11
    # Position should be restored after peek.
    assert stream.tell() == 3


def test_peek_filelike_length_with_empty_bytesio():
    assert peek_filelike_length(io.BytesIO()) == 0


def test_peek_filelike_length_unsupported_object():
    class NoTellOrFileno:
        pass

    assert peek_filelike_length(NoTellOrFileno()) is None


def test_peek_filelike_length_partial_support():
    # Object has .tell() but seek raises → falls through to None.
    class Broken:
        def tell(self):
            return 0

        def seek(self, *args, **kwargs):
            raise OSError("not seekable")

    assert peek_filelike_length(Broken()) is None


@pytest.mark.parametrize(
    ["hostname", "expected"],
    [
        ("127.0.0.1", True),
        ("192.168.0.0/16", True),  # CIDR split on "/"
        ("0.0.0.0", True),
        ("not-an-ip", False),
        ("::1", False),
        ("example.com", False),
        ("999.999.999.999", False),
    ],
)
def test_is_ipv4_hostname(hostname, expected):
    assert is_ipv4_hostname(hostname) == expected


@pytest.mark.parametrize(
    ["hostname", "expected"],
    [
        ("::1", True),
        ("fe80::1/64", True),  # CIDR split on "/"
        ("2001:db8::1", True),
        ("127.0.0.1", False),
        ("not-an-ip", False),
        ("example.com", False),
    ],
)
def test_is_ipv6_hostname(hostname, expected):
    assert is_ipv6_hostname(hostname) == expected


def test_urlpattern_raises_for_scheme_without_colon():
    with pytest.raises(ValueError, match="proper URL forms"):
        URLPattern("http")


def test_urlpattern_empty_pattern_does_not_raise():
    # An empty string falsy short-circuits the validation check.
    pattern = URLPattern("")
    assert pattern.scheme == ""
    assert pattern.host == ""
    assert pattern.port is None


def test_urlpattern_equality_and_hash():
    a = URLPattern("https://example.com")
    b = URLPattern("https://example.com")
    c = URLPattern("https://other.com")

    assert a == b
    assert a != c
    assert a != "https://example.com"  # comparison with non-URLPattern
    assert hash(a) == hash(b)
    # Hash-equal patterns can be deduped in a set.
    assert len({a, b, c}) == 2


def test_urlpattern_wildcard_subdomain_matching():
    # "*.example.com" should match subdomains, NOT the bare domain.
    pattern = URLPattern("all://*.example.com")
    assert pattern.matches(httpx.URL("http://www.example.com"))
    assert pattern.matches(httpx.URL("http://api.v2.example.com"))
    assert not pattern.matches(httpx.URL("http://example.com"))


def test_urlpattern_wildcard_anywhere_matching():
    # "*example.com" should match subdomains AND the bare domain.
    pattern = URLPattern("all://*example.com")
    assert pattern.matches(httpx.URL("http://www.example.com"))
    assert pattern.matches(httpx.URL("http://example.com"))
    # But not domains that merely contain the substring without a dot boundary.
    assert not pattern.matches(httpx.URL("http://notexample.com"))


def test_urlpattern_priority_tuple():
    # Patterns with a port should outrank those without.
    with_port = URLPattern("http://example.com:8080")
    without_port = URLPattern("http://example.com")
    assert with_port.priority < without_port.priority

    # Longer hosts outrank shorter ones.
    longer = URLPattern("http://api.example.com")
    shorter = URLPattern("http://example.com")
    assert longer.priority < shorter.priority
