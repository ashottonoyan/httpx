"""
Pure, in-memory unit tests for ``httpx.URL``.

All tests construct objects directly and exercise parsing, component access,
``copy_with``, ``join``, and ``params``. No network, no transport, no event loop.
"""

from __future__ import annotations

import pytest

import httpx


def test_scheme_is_lowercased() -> None:
    url = httpx.URL("HTTPS://example.com/")
    assert url.scheme == "https"
    assert url.raw_scheme == b"https"


def test_basic_component_parsing() -> None:
    url = httpx.URL(
        "HTTPS://Jo%40email.com:a%20secret@example.com:1234/pa%20th?q=ab#frag"
    )
    assert url.scheme == "https"
    assert url.username == "Jo@email.com"
    assert url.password == "a secret"
    assert url.userinfo == b"Jo%40email.com:a%20secret"
    assert url.host == "example.com"
    assert url.port == 1234
    assert url.path == "/pa th"
    assert url.query == b"q=ab"
    assert url.raw_path == b"/pa%20th?q=ab"
    assert url.fragment == "frag"


def test_idna_host_round_trip() -> None:
    url = httpx.URL("http://中国.icom.museum/")
    assert url.host == "中国.icom.museum"
    assert url.raw_host == b"xn--fiqs8s.icom.museum"

    # Constructing from the ASCII-compatible form yields the same unicode host.
    encoded = httpx.URL("http://xn--fiqs8s.icom.museum/")
    assert encoded.host == "中国.icom.museum"
    assert encoded.raw_host == b"xn--fiqs8s.icom.museum"
    assert url == encoded


def test_ipv6_host_is_unbracketed_but_str_brackets_it() -> None:
    url = httpx.URL("https://[::1]:8080/")
    assert url.host == "::1"
    assert url.raw_host == b"::1"
    assert url.port == 8080
    # ``str(url)`` must restore the bracketed form so it remains a valid URL.
    assert str(url) == "https://[::1]:8080/"


@pytest.mark.parametrize(
    "url_str",
    [
        "http://example.com:80/",
        "https://example.com:443/",
        "ws://example.com:80/",
        "wss://example.com:443/",
        "ftp://example.com:21/",
    ],
)
def test_default_ports_normalize_to_none(url_str: str) -> None:
    assert httpx.URL(url_str).port is None


def test_non_default_port_is_preserved() -> None:
    assert httpx.URL("http://example.com:8080/").port == 8080
    assert httpx.URL("https://example.com:8443/").port == 8443


def test_default_port_equality_normalization() -> None:
    assert httpx.URL("http://example.com") == httpx.URL("http://example.com:80")
    assert httpx.URL("https://example.com/") == httpx.URL("https://example.com:443/")


def test_path_defaults_to_root() -> None:
    url = httpx.URL("https://example.com")
    assert url.path == "/"
    assert url.raw_path == b"/"


def test_query_and_params_round_trip_multi_values() -> None:
    url = httpx.URL("https://example.com/?a=1&a=2&b=3")
    assert url.query == b"a=1&a=2&b=3"
    assert list(url.params.multi_items()) == [("a", "1"), ("a", "2"), ("b", "3")]
    # Single-key lookup returns the first value, matching QueryParams semantics.
    assert url.params["a"] == "1"
    assert url.params.get_list("a") == ["1", "2"]


def test_is_absolute_and_relative_url() -> None:
    absolute = httpx.URL("http://example.com/x")
    relative = httpx.URL("/x")
    assert absolute.is_absolute_url is True
    assert absolute.is_relative_url is False
    assert relative.is_absolute_url is False
    assert relative.is_relative_url is True


def test_copy_with_replaces_components() -> None:
    url = httpx.URL("https://example.com/path?old=1")
    updated = url.copy_with(host="other.example.org", port=9000, path="/new")
    assert updated.host == "other.example.org"
    assert updated.port == 9000
    assert updated.path == "/new"
    # ``copy_with`` keeps unspecified components and does not mutate the source.
    assert updated.query == b"old=1"
    assert url.host == "example.com"
    assert url.port is None


def test_copy_with_rejects_unknown_kwargs() -> None:
    url = httpx.URL("http://example.com/")
    with pytest.raises(TypeError, match="invalid keyword argument"):
        url.copy_with(bogus="nope")


def test_copy_with_rejects_wrong_type() -> None:
    url = httpx.URL("http://example.com/")
    with pytest.raises(TypeError, match="must be int"):
        url.copy_with(port="80")  # type: ignore[arg-type]


def test_constructor_rejects_non_str_non_url() -> None:
    with pytest.raises(TypeError, match="Expected str or httpx.URL"):
        httpx.URL(12345)  # type: ignore[arg-type]


def test_params_kwarg_replaces_query() -> None:
    url = httpx.URL("https://example.com/", params={"a": "1", "b": 2})
    # Order is preserved from the source mapping.
    assert url.query in (b"a=1&b=2", b"b=2&a=1")
    assert dict(url.params) == {"a": "1", "b": "2"}


def test_empty_params_drops_query_marker() -> None:
    # An empty ``params`` argument must not produce a trailing "?".
    url = httpx.URL("https://example.com/", params={})
    assert str(url) == "https://example.com/"
    assert url.raw_path == b"/"


def test_join_relative_path() -> None:
    base = httpx.URL("https://example.com/a/b/")
    assert base.join("c.html") == httpx.URL("https://example.com/a/b/c.html")


def test_join_absolute_path() -> None:
    base = httpx.URL("https://example.com/a/b/")
    assert base.join("/x") == httpx.URL("https://example.com/x")


def test_join_absolute_url_replaces_base() -> None:
    base = httpx.URL("https://example.com/a/b/")
    joined = base.join("http://other.example.org/y")
    assert joined == httpx.URL("http://other.example.org/y")


def test_url_equality_and_hash() -> None:
    a = httpx.URL("https://example.com/path")
    b = httpx.URL("https://example.com/path")
    assert a == b
    assert hash(a) == hash(b)
    # Equality also accepts a matching ``str``.
    assert a == "https://example.com/path"
    # Equality should not match arbitrary other types.
    assert a != 42


def test_repr_masks_password() -> None:
    url = httpx.URL("https://user:supersecret@example.com/")
    representation = repr(url)
    assert "supersecret" not in representation
    assert "[secure]" in representation
    assert "user" in representation


def test_str_round_trips_for_simple_url() -> None:
    raw = "https://example.com/path?x=1#frag"
    assert str(httpx.URL(raw)) == raw


def test_url_from_url_is_equal_copy() -> None:
    original = httpx.URL("https://example.com/path?x=1")
    copy = httpx.URL(original)
    assert copy == original
    assert copy is not original


def test_copy_set_add_remove_merge_params() -> None:
    url = httpx.URL("https://example.com/?a=1")
    assert url.copy_set_param("a", "2").query == b"a=2"
    assert url.copy_add_param("a", "2").query == b"a=1&a=2"
    assert url.copy_remove_param("a").query == b""
    merged = url.copy_merge_params({"b": "9"})
    assert dict(merged.params) == {"a": "1", "b": "9"}
