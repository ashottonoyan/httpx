"""
Focused unit tests for ``httpx.codes``.

These tests exercise the public ``httpx.codes`` IntEnum and its helper
predicates with edge-case inputs (range boundaries, out-of-range values,
unknown/known names) without performing any I/O.
"""

from __future__ import annotations

import pytest

import httpx


# ---------------------------------------------------------------------------
# is_* predicate boundary behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (99, False),
        (100, True),
        (150, True),
        (199, True),
        (200, False),
        (404, False),
        (-1, False),
        (0, False),
    ],
)
def test_is_informational_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_informational(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (199, False),
        (200, True),
        (204, True),
        (299, True),
        (300, False),
        (100, False),
        (500, False),
    ],
)
def test_is_success_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_success(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (299, False),
        (300, True),
        (304, True),
        (399, True),
        (400, False),
        (200, False),
    ],
)
def test_is_redirect_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_redirect(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (399, False),
        (400, True),
        (404, True),
        (418, True),
        (499, True),
        (500, False),
        (200, False),
    ],
)
def test_is_client_error_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_client_error(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (499, False),
        (500, True),
        (503, True),
        (599, True),
        (600, False),
        (200, False),
    ],
)
def test_is_server_error_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_server_error(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (399, False),
        (400, True),
        (404, True),
        (500, True),
        (599, True),
        (600, False),
        (200, False),
        (100, False),
    ],
)
def test_is_error_boundaries(value: int, expected: bool) -> None:
    assert httpx.codes.is_error(value) is expected


def test_predicate_categories_are_disjoint() -> None:
    """
    Every standard status code should land in exactly one of the five
    informational/success/redirect/client_error/server_error categories.
    """
    predicates = [
        httpx.codes.is_informational,
        httpx.codes.is_success,
        httpx.codes.is_redirect,
        httpx.codes.is_client_error,
        httpx.codes.is_server_error,
    ]
    for code in httpx.codes:
        matches = [p(int(code)) for p in predicates]
        assert sum(matches) == 1, (
            f"status code {int(code)} matched {sum(matches)} categories"
        )


def test_is_error_matches_client_or_server_error() -> None:
    for value in range(0, 700):
        expected = httpx.codes.is_client_error(value) or httpx.codes.is_server_error(
            value
        )
        assert httpx.codes.is_error(value) is expected


def test_predicates_accept_enum_members() -> None:
    assert httpx.codes.is_informational(httpx.codes.CONTINUE)
    assert httpx.codes.is_success(httpx.codes.OK)
    assert httpx.codes.is_redirect(httpx.codes.FOUND)
    assert httpx.codes.is_client_error(httpx.codes.NOT_FOUND)
    assert httpx.codes.is_server_error(httpx.codes.INTERNAL_SERVER_ERROR)
    assert httpx.codes.is_error(httpx.codes.BAD_GATEWAY)


# ---------------------------------------------------------------------------
# get_reason_phrase
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, phrase",
    [
        (100, "Continue"),
        (200, "OK"),
        (301, "Moved Permanently"),
        (418, "I'm a teapot"),
        (451, "Unavailable For Legal Reasons"),
        (500, "Internal Server Error"),
    ],
)
def test_get_reason_phrase_known(value: int, phrase: str) -> None:
    assert httpx.codes.get_reason_phrase(value) == phrase


@pytest.mark.parametrize("value", [0, 99, 306, 309, 499, 600, 999, -1])
def test_get_reason_phrase_unknown_returns_empty(value: int) -> None:
    assert httpx.codes.get_reason_phrase(value) == ""


def test_phrase_attribute_matches_get_reason_phrase() -> None:
    for code in httpx.codes:
        assert code.phrase == httpx.codes.get_reason_phrase(int(code))


def test_every_member_has_non_empty_phrase() -> None:
    for code in httpx.codes:
        assert isinstance(code.phrase, str)
        assert code.phrase != ""


# ---------------------------------------------------------------------------
# Enum identity / lookup semantics
# ---------------------------------------------------------------------------


def test_member_is_int_subclass() -> None:
    assert isinstance(httpx.codes.OK, int)
    assert int(httpx.codes.OK) == 200


def test_str_returns_numeric_value() -> None:
    assert str(httpx.codes.OK) == "200"
    assert str(httpx.codes.IM_A_TEAPOT) == "418"


def test_value_lookup_returns_same_member() -> None:
    assert httpx.codes(200) is httpx.codes.OK
    assert httpx.codes(404) is httpx.codes.NOT_FOUND


def test_value_lookup_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError):
        httpx.codes(499)


def test_name_lookup_returns_member() -> None:
    assert httpx.codes["OK"] is httpx.codes.OK
    assert httpx.codes["INTERNAL_SERVER_ERROR"] is httpx.codes.INTERNAL_SERVER_ERROR


def test_name_lookup_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError):
        httpx.codes["NOT_A_REAL_STATUS"]


def test_lowercase_aliases_match_member_value() -> None:
    # The module installs lowercase attribute aliases (`requests` compat).
    for code in httpx.codes:
        alias = getattr(httpx.codes, code.name.lower())
        assert alias == int(code)


def test_lowercase_aliases_are_plain_ints_not_members() -> None:
    # The aliases are set via int(code), so they are not enum members.
    not_found_alias = httpx.codes.not_found  # type: ignore[attr-defined]
    assert not_found_alias == 404
    assert not isinstance(not_found_alias, httpx.codes)


# ---------------------------------------------------------------------------
# Membership semantics
# ---------------------------------------------------------------------------


def test_known_codes_are_enum_members() -> None:
    known = {100, 200, 301, 404, 418, 500}
    member_values = {int(c) for c in httpx.codes}
    assert known.issubset(member_values)


def test_no_duplicate_member_values() -> None:
    values = [int(c) for c in httpx.codes]
    assert len(values) == len(set(values))
