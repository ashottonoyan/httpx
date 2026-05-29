"""
Pure, in-memory unit tests for ``httpx.Headers``.

These tests construct ``httpx.Headers`` objects directly and exercise the
public surface area (case-insensitive access, multi-value handling,
``get_list``, ``update``/``copy``, and ``repr`` redaction of sensitive
headers). No network, no transports, no event loop.
"""

import pytest

import httpx


# ---------------------------------------------------------------------------
# Case-insensitive access
# ---------------------------------------------------------------------------


def test_case_insensitive_membership_and_lookup():
    h = httpx.Headers({"Content-Type": "application/json"})

    # Membership tests ignore case on both sides.
    assert "Content-Type" in h
    assert "content-type" in h
    assert "CONTENT-TYPE" in h
    assert "X-Other" not in h

    # __getitem__ and get() return the same value regardless of casing.
    assert h["Content-Type"] == "application/json"
    assert h["content-type"] == "application/json"
    assert h.get("CONTENT-TYPE") == "application/json"


def test_case_insensitive_delete_preserves_canonical_key_on_set():
    h = httpx.Headers({"X-Foo": "1"})

    # Deletion is case-insensitive.
    del h["x-foo"]
    assert "X-Foo" not in h
    assert list(h.keys()) == []

    # Re-setting via __setitem__ preserves the original (mixed-case) key form
    # in the raw list while still being retrievable case-insensitively.
    h["X-Foo"] = "2"
    assert h.raw == [(b"X-Foo", b"2")]
    assert h["x-foo"] == "2"


def test_setitem_replaces_existing_case_insensitively():
    h = httpx.Headers([("Accept", "text/plain"), ("accept", "text/html")])

    # Two entries exist for the same case-insensitive key.
    assert h.get_list("accept") == ["text/plain", "text/html"]

    # Assigning via __setitem__ collapses *all* duplicates into a single entry
    # at the position of the first occurrence.
    h["ACCEPT"] = "application/json"
    assert h.get_list("accept") == ["application/json"]
    assert h.raw == [(b"ACCEPT", b"application/json")]


# ---------------------------------------------------------------------------
# Multi-value headers
# ---------------------------------------------------------------------------


def test_multi_value_getitem_joins_with_comma():
    h = httpx.Headers([("Vary", "Accept"), ("Vary", "Accept-Encoding")])

    # __getitem__ for a duplicated key returns the comma-joined value
    # (RFC 7230 §3.2.2 behaviour).
    assert h["Vary"] == "Accept, Accept-Encoding"
    assert h.get("vary") == "Accept, Accept-Encoding"


def test_multi_value_items_vs_multi_items():
    h = httpx.Headers(
        [("Set-Cookie", "a=1"), ("Set-Cookie", "b=2"), ("X-Trace", "abc")]
    )

    # items() collapses repeated keys with comma joining.
    assert list(h.items()) == [
        ("set-cookie", "a=1, b=2"),
        ("x-trace", "abc"),
    ]

    # multi_items() preserves every original (key, value) pair in order.
    assert h.multi_items() == [
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
        ("x-trace", "abc"),
    ]


def test_missing_key_raises_keyerror_and_get_returns_default():
    h = httpx.Headers({"Content-Type": "text/plain"})
    with pytest.raises(KeyError):
        h["X-Missing"]
    assert h.get("X-Missing") is None
    assert h.get("X-Missing", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# get_list (with and without split_commas)
# ---------------------------------------------------------------------------


def test_get_list_returns_values_in_insertion_order():
    h = httpx.Headers(
        [("X-Tag", "alpha"), ("X-Other", "z"), ("x-tag", "beta")]
    )
    # get_list collects every entry for a case-insensitive key, in order.
    assert h.get_list("X-Tag") == ["alpha", "beta"]
    assert h.get_list("X-MISSING") == []


def test_get_list_split_commas_expands_and_strips():
    h = httpx.Headers(
        [
            ("Accept-Encoding", "gzip, deflate"),
            ("accept-encoding", "br"),
        ]
    )

    # Without split_commas each raw header value is returned verbatim.
    assert h.get_list("Accept-Encoding") == ["gzip, deflate", "br"]

    # With split_commas each value is split on ',' and whitespace stripped.
    assert h.get_list("Accept-Encoding", split_commas=True) == [
        "gzip",
        "deflate",
        "br",
    ]


# ---------------------------------------------------------------------------
# update() and copy()
# ---------------------------------------------------------------------------


def test_update_replaces_existing_and_appends_new():
    h = httpx.Headers(
        [("Accept", "text/plain"), ("Accept", "text/html"), ("Host", "example.com")]
    )

    # update() with a key already present in self should *remove* the prior
    # entries (regardless of case) and append the new one(s) at the end.
    h.update({"accept": "application/json", "X-New": "yes"})

    # The original 'Host' header is preserved untouched.
    assert h["Host"] == "example.com"

    # Both old 'Accept' entries are gone; one new entry was appended.
    assert h.get_list("Accept") == ["application/json"]
    assert h["X-New"] == "yes"

    # The new entries are at the end of the raw list.
    assert h.raw[-2:] == [(b"accept", b"application/json"), (b"X-New", b"yes")]


def test_update_with_none_is_noop():
    h = httpx.Headers({"A": "1"})
    h.update(None)
    assert dict(h) == {"a": "1"}


def test_copy_is_independent_of_original():
    original = httpx.Headers(
        [("Authorization", "Bearer xyz"), ("X-Trace", "1")]
    )
    clone = original.copy()

    # The copy compares equal to the original but is a distinct object.
    assert clone == original
    assert clone is not original
    assert clone.raw == original.raw

    # Mutating the clone does not affect the original.
    clone["X-Trace"] = "2"
    del clone["Authorization"]
    assert original["X-Trace"] == "1"
    assert original["Authorization"] == "Bearer xyz"
    assert "Authorization" not in clone

    # Mutating the original does not affect the clone either.
    original["X-Trace"] = "999"
    assert clone["X-Trace"] == "2"


# ---------------------------------------------------------------------------
# repr() redacts sensitive headers
# ---------------------------------------------------------------------------


def test_repr_redacts_authorization_header():
    h = httpx.Headers({"Authorization": "Bearer super-secret-token"})
    rendered = repr(h)
    # The actual secret must never appear in the repr.
    assert "super-secret-token" not in rendered
    # The conventional redaction marker is present.
    assert "[secure]" in rendered
    # The header *name* is still shown (Headers exposes keys lower-cased).
    assert "authorization" in rendered


def test_repr_redacts_proxy_authorization_header():
    h = httpx.Headers({"Proxy-Authorization": "Basic dXNlcjpwYXNz"})
    rendered = repr(h)
    assert "dXNlcjpwYXNz" not in rendered
    assert "[secure]" in rendered
    assert "proxy-authorization" in rendered


def test_repr_does_not_redact_non_sensitive_headers():
    h = httpx.Headers({"Content-Type": "application/json"})
    rendered = repr(h)
    assert "[secure]" not in rendered
    assert "application/json" in rendered


def test_repr_redacts_sensitive_header_case_insensitively():
    # Even though the user supplied the header with unusual casing, the
    # redaction matcher is case-insensitive, so the secret should still be
    # masked.
    h = httpx.Headers({"AUTHORIZATION": "Bearer leak-me-if-you-can"})
    rendered = repr(h)
    assert "leak-me-if-you-can" not in rendered
    assert "[secure]" in rendered


def test_repr_uses_list_form_when_duplicate_keys_present():
    # When there are duplicate keys, repr falls back to a list-of-tuples form,
    # so that information isn't lost. Sensitive values must still be masked.
    h = httpx.Headers(
        [("Authorization", "Bearer one"), ("Authorization", "Bearer two")]
    )
    rendered = repr(h)
    assert "Bearer one" not in rendered
    assert "Bearer two" not in rendered
    assert rendered.count("[secure]") == 2
