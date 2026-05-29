"""
Pure unit tests for ``httpx.URL``.

All tests are network-free: they construct ``httpx.URL`` instances directly
and exercise parsing, accessors, ``copy_with``, ``join``, and ``params``.
"""

from __future__ import annotations

import pytest

import httpx


# ---------------------------------------------------------------------------
# Component parsing
# ---------------------------------------------------------------------------


def test_parses_all_components_of_a_full_url():
    url = httpx.URL("https://user:pw@example.org:8443/path/seg?x=1&y=2#frag")

    assert url.scheme == "https"
    assert url.username == "user"
    assert url.password == "pw"
    assert url.host == "example.org"
    assert url.port == 8443
    assert url.path == "/path/seg"
    assert url.query == b"x=1&y=2"
    assert url.raw_path == b"/path/seg?x=1&y=2"
    assert url.fragment == "frag"


def test_scheme_and_host_are_lowercased():
    url = httpx.URL("HTTPS://EXAMPLE.COM/Path")
    assert url.scheme == "https"
    assert url.raw_scheme == b"https"
    assert url.host == "example.com"
    assert url.raw_host == b"example.com"
    # Path case is preserved.
    assert url.path == "/Path"


@pytest.mark.parametrize(
    "scheme,default_port",
    [("http", 80), ("https", 443), ("ws", 80), ("wss", 443), ("ftp", 21)],
)
def test_default_ports_are_normalized_to_none(scheme: str, default_port: int) -> None:
    url_with_port = httpx.URL(f"{scheme}://example.com:{default_port}/")
    url_without_port = httpx.URL(f"{scheme}://example.com/")

    assert url_with_port.port is None
    assert url_without_port.port is None
    assert url_with_port == url_without_port


def test_non_default_port_is_preserved():
    url = httpx.URL("http://example.com:8080/")
    assert url.port == 8080
    assert url.netloc == b"example.com:8080"


def test_userinfo_is_percent_decoded_in_username_and_password():
    url = httpx.URL("https://jo%40email.com:a%20secret@example.com/")
    # Decoded form for ergonomic access.
    assert url.username == "jo@email.com"
    assert url.password == "a secret"
    # Raw bytes preserve the percent-encoding.
    assert url.userinfo == b"jo%40email.com:a%20secret"


def test_empty_path_is_normalized_to_slash():
    url = httpx.URL("https://example.com")
    assert url.path == "/"
    assert url.raw_path == b"/"


def test_query_string_preserves_raw_encoding():
    url = httpx.URL("https://example.com/?filter=some%20text&n=1")
    # `.query` is raw bytes, NOT percent-decoded — only the parsed params decode.
    assert url.query == b"filter=some%20text&n=1"
    assert url.params["filter"] == "some text"
    assert url.params["n"] == "1"


def test_fragment_is_percent_decoded():
    url = httpx.URL("https://example.com/p#a%20b")
    assert url.fragment == "a b"


# ---------------------------------------------------------------------------
# IDNA and IPv6 hosts
# ---------------------------------------------------------------------------


def test_internationalized_host_round_trips_via_idna():
    decoded = httpx.URL("http://中国.icom.museum/")
    punycoded = httpx.URL("http://xn--fiqs8s.icom.museum/")

    # `.host` always exposes the unicode form regardless of how it was given.
    assert decoded.host == "中国.icom.museum"
    assert punycoded.host == "中国.icom.museum"
    # `.raw_host` always exposes the IDNA-encoded bytes.
    assert decoded.raw_host == b"xn--fiqs8s.icom.museum"
    assert punycoded.raw_host == b"xn--fiqs8s.icom.museum"


def test_ipv6_host_strips_brackets_for_host_property():
    url = httpx.URL("https://[::1]:8080/path")
    assert url.host == "::1"
    assert url.port == 8080
    # netloc keeps the brackets so it is a valid Host header value.
    assert url.netloc == b"[::1]:8080"


# ---------------------------------------------------------------------------
# Absolute vs relative
# ---------------------------------------------------------------------------


def test_absolute_vs_relative_classification():
    absolute = httpx.URL("https://example.com/x")
    relative = httpx.URL("/x")

    assert absolute.is_absolute_url
    assert not absolute.is_relative_url
    assert relative.is_relative_url
    assert not relative.is_absolute_url


# ---------------------------------------------------------------------------
# Equality, hashing, and string forms
# ---------------------------------------------------------------------------


def test_equality_against_strings_and_url_instances():
    url = httpx.URL("https://example.com/x")
    assert url == "https://example.com/x"
    assert url == httpx.URL("https://example.com/x")
    assert url != "https://example.com/y"
    # Equality only accepts URL or str.
    assert url != 123
    assert url != None  # noqa: E711


def test_hash_matches_string_representation():
    url = httpx.URL("https://example.com/x?a=1")
    assert hash(url) == hash(str(url))
    # Equal URLs hash equally — usable as dict keys.
    bucket = {url: "value"}
    assert bucket[httpx.URL("https://example.com/x?a=1")] == "value"


def test_repr_masks_password_but_str_does_not():
    url = httpx.URL("https://user:supersecret@example.com/")
    representation = repr(url)
    assert "supersecret" not in representation
    assert "[secure]" in representation
    # __str__ preserves the original form (no masking) — required for round-tripping.
    assert "supersecret" in str(url)


# ---------------------------------------------------------------------------
# copy_with
# ---------------------------------------------------------------------------


def test_copy_with_replaces_individual_components():
    url = httpx.URL("https://example.com/path?a=1")

    swapped = url.copy_with(scheme="http", host="other.example.com", port=8080)
    assert swapped.scheme == "http"
    assert swapped.host == "other.example.com"
    assert swapped.port == 8080
    # Components not mentioned are preserved.
    assert swapped.path == "/path"
    assert swapped.query == b"a=1"
    # Original instance is unchanged — copy_with is non-mutating.
    assert url.host == "example.com"
    assert url.port is None


def test_copy_with_can_replace_query_via_params_kwarg():
    url = httpx.URL("https://example.com/x?a=1")
    updated = url.copy_with(params={"b": "2", "c": "3"})

    assert updated.params["b"] == "2"
    assert updated.params["c"] == "3"
    assert "a" not in updated.params


def test_copy_with_empty_params_drops_query_string_entirely():
    # Empty params should not leave a trailing "?" on the rendered URL.
    url = httpx.URL("https://example.com/x?a=1").copy_with(params={})
    assert str(url) == "https://example.com/x"
    assert url.query == b""


def test_copy_with_rejects_unknown_kwarg():
    url = httpx.URL("https://example.com/")
    with pytest.raises(TypeError):
        url.copy_with(bogus="value")


def test_copy_with_rejects_wrong_type():
    url = httpx.URL("https://example.com/")
    with pytest.raises(TypeError):
        # `port` must be int, not str.
        url.copy_with(port="not-a-number")


# ---------------------------------------------------------------------------
# Param-manipulation helpers
# ---------------------------------------------------------------------------


def test_copy_set_add_remove_merge_params_are_pure():
    url = httpx.URL("https://example.com/x?a=1&a=2")

    set_url = url.copy_set_param("a", "9")
    assert set_url.params.get_list("a") == ["9"]

    add_url = url.copy_add_param("b", "3")
    assert add_url.params.get_list("a") == ["1", "2"]
    assert add_url.params.get_list("b") == ["3"]

    removed = url.copy_remove_param("a")
    assert "a" not in removed.params

    merged = url.copy_merge_params({"a": "10", "c": "4"})
    # merge replaces a, keeps c, retains the original ordering of existing keys.
    assert merged.params.get_list("a") == ["10"]
    assert merged.params["c"] == "4"

    # Original is untouched after every helper call.
    assert url.params.get_list("a") == ["1", "2"]


# ---------------------------------------------------------------------------
# join
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base,target,expected",
    [
        ("https://example.com/a/b", "c", "https://example.com/a/c"),
        ("https://example.com/a/b", "/c", "https://example.com/c"),
        ("https://example.com/a/b/", "c", "https://example.com/a/b/c"),
        ("https://example.com/a/b", "../c", "https://example.com/c"),
        (
            "https://example.com/a/b",
            "https://other.example.com/x",
            "https://other.example.com/x",
        ),
    ],
)
def test_join_resolves_relative_and_absolute_targets(
    base: str, target: str, expected: str
) -> None:
    joined = httpx.URL(base).join(target)
    assert isinstance(joined, httpx.URL)
    assert str(joined) == expected


def test_join_accepts_url_instance_as_argument():
    base = httpx.URL("https://example.com/a/b")
    joined = base.join(httpx.URL("/c"))
    assert str(joined) == "https://example.com/c"


# ---------------------------------------------------------------------------
# Constructor errors
# ---------------------------------------------------------------------------


def test_url_rejects_non_string_non_url_input():
    with pytest.raises(TypeError):
        httpx.URL(12345)  # type: ignore[arg-type]
