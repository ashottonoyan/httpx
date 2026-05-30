"""
Dedicated regression tests for httpx._urlparse — the URL parsing and normalization
utility module.  These tests target the module's public API directly so that regressions
are surfaced in a focused, easy-to-diagnose place rather than buried inside higher-level
URL class tests.
"""
import typing

import pytest

from httpx._exceptions import InvalidURL
from httpx._urlparse import (
    FRAG_SAFE,
    MAX_URL_LENGTH,
    PATH_SAFE,
    PERCENT,
    QUERY_SAFE,
    ParseResult,
    encode_host,
    normalize_path,
    normalize_port,
    percent_encoded,
    quote,
    urlparse,
    validate_path,
)

# ---------------------------------------------------------------------------
# PERCENT / percent_encoded / quote
# ---------------------------------------------------------------------------


class TestPERCENT:
    def test_ascii_char(self):
        assert PERCENT(" ") == "%20"

    def test_multi_char(self):
        assert PERCENT("ab") == "%61%62"

    def test_unicode_char(self):
        # "é" encodes to 0xC3 0xA9 in UTF-8
        assert PERCENT("é") == "%C3%A9"


class TestPercentEncoded:
    def test_safe_chars_unchanged(self):
        s = "abcABC123-._~"
        assert percent_encoded(s, safe="") == s

    def test_space_is_encoded(self):
        assert percent_encoded("hello world", safe="") == "hello%20world"

    def test_safe_parameter_is_respected(self):
        # "/" is not an UNRESERVED_CHARACTER, but marking it safe keeps it
        assert percent_encoded("/path", safe="/") == "/path"

    def test_non_ascii_is_encoded(self):
        result = percent_encoded("ñ", safe="")
        assert result == "%C3%B1"


class TestQuote:
    def test_no_special_chars(self):
        assert quote("hello", safe=PATH_SAFE) == "hello"

    def test_preserves_existing_percent_sequence(self):
        # %20 is already encoded — quote() must not double-encode it
        assert quote("%20", safe=PATH_SAFE) == "%20"

    def test_encodes_unencoded_chars(self):
        result = quote(" hello", safe=PATH_SAFE)
        assert result == "%20hello"

    def test_mixed_encoded_and_unencoded(self):
        # Text before and after a %xx sequence: leading text must be encoded
        result = quote("hello%20world", safe=PATH_SAFE)
        assert result == "hello%20world"

    def test_text_before_percent_sequence_is_encoded(self):
        # " " before "%20" — leading text gets percent-encoded, existing %xx preserved
        result = quote("say %20hi", safe=PATH_SAFE)
        assert result == "say%20%20hi"

    def test_query_safe(self):
        # '#' is NOT safe for query strings; '?' is safe
        result = quote("a=b&c#d", safe=QUERY_SAFE)
        assert "#" not in result
        assert "a=b&c" in result

    def test_fragment_safe(self):
        # '"' must be encoded in fragments
        result = quote('say "hi"', safe=FRAG_SAFE)
        assert '"' not in result

    def test_empty_string(self):
        assert quote("", safe=PATH_SAFE) == ""


# ---------------------------------------------------------------------------
# encode_host
# ---------------------------------------------------------------------------


class TestEncodeHost:
    def test_empty_string(self):
        assert encode_host("") == ""

    def test_valid_ipv4(self):
        assert encode_host("192.168.1.1") == "192.168.1.1"

    def test_invalid_ipv4_raises(self):
        with pytest.raises(InvalidURL, match="Invalid IPv4"):
            encode_host("999.999.999.999")

    def test_valid_ipv6_strips_brackets(self):
        # encode_host stores the bare address; brackets are added by authority
        assert encode_host("[::1]") == "::1"

    def test_valid_ipv6_full_address(self):
        assert encode_host("[2001:db8::1]") == "2001:db8::1"

    def test_invalid_ipv6_raises(self):
        with pytest.raises(InvalidURL, match="Invalid IPv6"):
            encode_host("[not:valid:ipv6:addr:!!!]")

    def test_ascii_hostname_lowercased(self):
        assert encode_host("EXAMPLE.COM") == "example.com"

    def test_ascii_hostname_with_subdomain(self):
        assert encode_host("sub.example.org") == "sub.example.org"

    def test_idna_hostname(self):
        result = encode_host("bücher.example")
        assert result == "xn--bcher-kva.example"

    def test_invalid_idna_raises(self):
        with pytest.raises(InvalidURL, match="Invalid IDNA"):
            # Emoji domain names are disallowed by IDNA 2008
            encode_host("\U0001F4A9.example")


# ---------------------------------------------------------------------------
# normalize_port
# ---------------------------------------------------------------------------


class TestNormalizePort:
    def test_none_returns_none(self):
        assert normalize_port(None, "https") is None

    def test_empty_string_returns_none(self):
        assert normalize_port("", "https") is None

    def test_http_default_port_omitted(self):
        assert normalize_port("80", "http") is None
        assert normalize_port(80, "http") is None

    def test_https_default_port_omitted(self):
        assert normalize_port("443", "https") is None

    def test_ws_default_port_omitted(self):
        assert normalize_port("80", "ws") is None

    def test_wss_default_port_omitted(self):
        assert normalize_port("443", "wss") is None

    def test_ftp_default_port_omitted(self):
        assert normalize_port("21", "ftp") is None

    def test_non_default_port_returned(self):
        assert normalize_port("8080", "http") == 8080

    def test_non_default_https_port_returned(self):
        assert normalize_port("8443", "https") == 8443

    def test_integer_input(self):
        assert normalize_port(9000, "http") == 9000

    def test_invalid_port_string_raises(self):
        with pytest.raises(InvalidURL, match="Invalid port"):
            normalize_port("abc", "http")

    def test_unknown_scheme_with_port(self):
        # Scheme not in the defaults table — port is kept
        assert normalize_port("80", "custom") == 80


# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------


class TestValidatePath:
    def test_empty_path_with_authority(self):
        # Should not raise
        validate_path("", has_scheme=True, has_authority=True)

    def test_slash_path_with_authority(self):
        validate_path("/some/path", has_scheme=True, has_authority=True)

    def test_non_slash_path_with_authority_raises(self):
        with pytest.raises(InvalidURL, match="must be empty or begin with '/'"):
            validate_path("no-slash", has_scheme=True, has_authority=True)

    def test_double_slash_path_without_scheme_or_authority_raises(self):
        with pytest.raises(InvalidURL, match="cannot have a path starting with '//'"):
            validate_path("//bad", has_scheme=False, has_authority=False)

    def test_colon_path_without_scheme_or_authority_raises(self):
        with pytest.raises(InvalidURL, match="cannot have a path starting with ':'"):
            validate_path(":bad", has_scheme=False, has_authority=False)

    def test_relative_path_without_scheme_or_authority_ok(self):
        validate_path("relative/path", has_scheme=False, has_authority=False)

    def test_path_with_scheme_no_authority_ok(self):
        validate_path("relative/path", has_scheme=True, has_authority=False)


# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_no_dots_fast_return(self):
        assert normalize_path("/a/b/c") == "/a/b/c"

    def test_single_dot_removed(self):
        assert normalize_path("/a/./b") == "/a/b"

    def test_double_dot_goes_up(self):
        assert normalize_path("/a/b/../c") == "/a/c"

    def test_complex_normalization(self):
        assert normalize_path("/path/./to/somewhere/..") == "/path/to"

    def test_leading_double_dot_does_not_escape_root(self):
        result = normalize_path("/a/../../b")
        # Cannot go above root — output should not start with ".."
        assert not result.startswith("..")

    def test_multiple_dots_in_filename_unchanged(self):
        assert normalize_path("/a/b.tar.gz") == "/a/b.tar.gz"

    def test_empty_path(self):
        assert normalize_path("") == ""

    def test_single_dot_only(self):
        result = normalize_path(".")
        # "." in a relative path normalizes to empty
        assert result == ""

    def test_double_dot_only(self):
        result = normalize_path("..")
        assert result == ""


# ---------------------------------------------------------------------------
# ParseResult
# ---------------------------------------------------------------------------


class TestParseResult:
    def _make(self, **kwargs: typing.Any) -> ParseResult:
        defaults: dict[str, typing.Any] = dict(
            scheme="https",
            userinfo="",
            host="example.com",
            port=None,
            path="/",
            query=None,
            fragment=None,
        )
        defaults.update(kwargs)
        return ParseResult(**defaults)

    def test_authority_plain_host(self):
        p = self._make()
        assert p.authority == "example.com"

    def test_authority_with_port(self):
        p = self._make(port=8080)
        assert p.authority == "example.com:8080"

    def test_authority_with_userinfo(self):
        p = self._make(userinfo="user:pass")
        assert p.authority == "user:pass@example.com"

    def test_authority_ipv6_adds_brackets(self):
        p = self._make(host="::1")
        assert p.authority == "[::1]"

    def test_netloc_without_port(self):
        p = self._make()
        assert p.netloc == "example.com"

    def test_netloc_with_port(self):
        p = self._make(port=9000)
        assert p.netloc == "example.com:9000"

    def test_netloc_ipv6(self):
        p = self._make(host="2001:db8::1")
        assert p.netloc == "[2001:db8::1]"

    def test_str_full_url(self):
        p = self._make(query="a=1", fragment="top")
        assert str(p) == "https://example.com/?a=1#top"

    def test_str_no_query_no_fragment(self):
        p = self._make()
        assert str(p) == "https://example.com/"

    def test_str_empty_query(self):
        p = self._make(query="")
        assert str(p) == "https://example.com/?"

    def test_str_no_scheme(self):
        p = self._make(scheme="", host="")
        assert str(p) == "/"

    def test_copy_with_no_kwargs_returns_same(self):
        p = self._make()
        assert p.copy_with() is p

    def test_copy_with_new_scheme(self):
        p = self._make()
        p2 = p.copy_with(scheme="http")
        assert p2.scheme == "http"
        assert p2.host == p.host

    def test_copy_with_new_path(self):
        p = self._make()
        p2 = p.copy_with(path="/new/path")
        assert p2.path == "/new/path"


# ---------------------------------------------------------------------------
# urlparse — top-level function
# ---------------------------------------------------------------------------


class TestUrlparse:
    def test_basic_https_url(self):
        p = urlparse("https://example.com/")
        assert p.scheme == "https"
        assert p.host == "example.com"
        assert p.port is None
        assert p.path == "/"
        assert p.query is None
        assert p.fragment is None

    def test_scheme_is_lowercased(self):
        p = urlparse("HTTPS://example.com/")
        assert p.scheme == "https"

    def test_host_is_lowercased(self):
        p = urlparse("https://EXAMPLE.COM/")
        assert p.host == "example.com"

    def test_non_default_port_preserved(self):
        p = urlparse("https://example.com:8443/")
        assert p.port == 8443

    def test_default_port_omitted(self):
        p = urlparse("https://example.com:443/")
        assert p.port is None

    def test_query_string_captured(self):
        p = urlparse("https://example.com/?a=1&b=2")
        assert p.query == "a=1&b=2"

    def test_empty_query_string_captured(self):
        p = urlparse("https://example.com/?")
        assert p.query == ""

    def test_fragment_captured(self):
        p = urlparse("https://example.com/#anchor")
        assert p.fragment == "anchor"

    def test_userinfo_captured(self):
        p = urlparse("https://user:pass@example.com/")
        assert "user" in p.userinfo
        assert "pass" in p.userinfo

    def test_url_too_long_raises(self):
        with pytest.raises(InvalidURL, match="URL too long"):
            urlparse("https://example.com/" + "a" * MAX_URL_LENGTH)

    def test_non_printable_char_raises(self):
        with pytest.raises(InvalidURL, match="non-printable ASCII"):
            urlparse("https://example.com/\x00path")

    def test_tab_char_raises(self):
        with pytest.raises(InvalidURL, match="non-printable ASCII"):
            urlparse("https://example.com/\tpath")

    def test_newline_raises(self):
        with pytest.raises(InvalidURL, match="non-printable ASCII"):
            urlparse("https://example.com/\npath")

    def test_kwargs_port_as_int(self):
        p = urlparse("https://example.com/", port=9000)  # type: ignore[arg-type]
        assert p.port == 9000

    def test_kwargs_port_as_none(self):
        p = urlparse("https://example.com/", port=None)
        assert p.port is None

    def test_kwargs_netloc(self):
        p = urlparse(netloc="example.com:9000", scheme="https", path="/")
        assert p.host == "example.com"
        assert p.port == 9000

    def test_kwargs_username_password(self):
        p = urlparse("https://example.com/", username="alice", password="secret")
        assert "alice" in p.userinfo

    def test_kwargs_raw_path_with_query(self):
        p = urlparse("https://example.com", raw_path="/search?q=hello")
        assert p.path == "/search"
        assert p.query == "q=hello"

    def test_kwargs_raw_path_without_query(self):
        p = urlparse("https://example.com", raw_path="/search")
        assert p.path == "/search"
        assert p.query is None

    def test_kwargs_ipv6_host_auto_brackets(self):
        p = urlparse(scheme="https", host="::1", path="/")
        assert p.host == "::1"

    def test_kwargs_component_too_long_raises(self):
        with pytest.raises(InvalidURL, match="too long"):
            urlparse(scheme="https", path="/" + "a" * MAX_URL_LENGTH)

    def test_kwargs_component_non_printable_raises(self):
        with pytest.raises(InvalidURL, match="non-printable ASCII"):
            urlparse(scheme="https", path="/\x01bad")

    def test_kwargs_invalid_component_regex_raises(self):
        with pytest.raises(InvalidURL, match="Invalid URL component"):
            urlparse(scheme="invalid scheme!")

    def test_path_normalization_applied(self):
        p = urlparse("https://example.com/a/b/../c")
        assert p.path == "/a/c"

    def test_relative_url(self):
        p = urlparse("/relative/path?q=1")
        assert p.scheme == ""
        assert p.host == ""
        assert p.path == "/relative/path"
        assert p.query == "q=1"

    def test_empty_url(self):
        p = urlparse("")
        assert p.scheme == ""
        assert p.host == ""
        assert p.path == ""
