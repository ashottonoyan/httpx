"""
Pure unit tests for httpx.codes: the public IntEnum and its classifier helpers.

Network-free, transport-free, event-loop-free. Each test exercises the enum
or its classmethods directly.
"""

import pytest

import httpx


# ---------------------------------------------------------------------------
# Classifier predicates: is_informational / is_success / is_redirect /
# is_client_error / is_server_error / is_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [100, 101, 150, 199])
def test_is_informational_true_for_1xx(code):
    assert httpx.codes.is_informational(code) is True


@pytest.mark.parametrize("code", [99, 200, 300, 404, 500, 0, -1, 1000])
def test_is_informational_false_outside_1xx(code):
    assert httpx.codes.is_informational(code) is False


@pytest.mark.parametrize("code", [200, 201, 250, 299])
def test_is_success_true_for_2xx(code):
    assert httpx.codes.is_success(code) is True


@pytest.mark.parametrize("code", [199, 300, 100, 404, 500])
def test_is_success_false_outside_2xx(code):
    assert httpx.codes.is_success(code) is False


@pytest.mark.parametrize("code", [300, 301, 350, 399])
def test_is_redirect_true_for_3xx(code):
    assert httpx.codes.is_redirect(code) is True


@pytest.mark.parametrize("code", [299, 400, 200, 100, 500])
def test_is_redirect_false_outside_3xx(code):
    assert httpx.codes.is_redirect(code) is False


@pytest.mark.parametrize("code", [400, 401, 418, 451, 499])
def test_is_client_error_true_for_4xx(code):
    assert httpx.codes.is_client_error(code) is True


@pytest.mark.parametrize("code", [399, 500, 200, 100, 300])
def test_is_client_error_false_outside_4xx(code):
    assert httpx.codes.is_client_error(code) is False


@pytest.mark.parametrize("code", [500, 501, 550, 599])
def test_is_server_error_true_for_5xx(code):
    assert httpx.codes.is_server_error(code) is True


@pytest.mark.parametrize("code", [499, 600, 200, 100, 300, 400])
def test_is_server_error_false_outside_5xx(code):
    assert httpx.codes.is_server_error(code) is False


@pytest.mark.parametrize("code", [400, 404, 451, 499, 500, 503, 599])
def test_is_error_true_for_4xx_and_5xx(code):
    assert httpx.codes.is_error(code) is True


@pytest.mark.parametrize("code", [100, 199, 200, 299, 300, 399, 600])
def test_is_error_false_outside_4xx_5xx(code):
    assert httpx.codes.is_error(code) is False


def test_predicates_accept_enum_members_not_just_ints():
    # Because codes is an IntEnum, members must be accepted by the
    # classifier predicates that are typed `value: int`.
    assert httpx.codes.is_success(httpx.codes.OK) is True
    assert httpx.codes.is_client_error(httpx.codes.NOT_FOUND) is True
    assert httpx.codes.is_server_error(httpx.codes.INTERNAL_SERVER_ERROR) is True
    assert httpx.codes.is_redirect(httpx.codes.MOVED_PERMANENTLY) is True
    assert httpx.codes.is_informational(httpx.codes.CONTINUE) is True


def test_predicate_classifiers_are_mutually_exclusive_for_known_codes():
    # For every defined member, exactly one of the five band predicates
    # should be true.
    bands = (
        httpx.codes.is_informational,
        httpx.codes.is_success,
        httpx.codes.is_redirect,
        httpx.codes.is_client_error,
        httpx.codes.is_server_error,
    )
    for member in httpx.codes:
        true_bands = sum(1 for fn in bands if fn(int(member)))
        assert true_bands == 1, (
            f"{member.name}={int(member)} matched {true_bands} bands"
        )


# ---------------------------------------------------------------------------
# Reason-phrase lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,phrase",
    [
        (100, "Continue"),
        (200, "OK"),
        (301, "Moved Permanently"),
        (418, "I'm a teapot"),
        (451, "Unavailable For Legal Reasons"),
        (500, "Internal Server Error"),
        (511, "Network Authentication Required"),
    ],
)
def test_get_reason_phrase_known_codes(value, phrase):
    assert httpx.codes.get_reason_phrase(value) == phrase


@pytest.mark.parametrize("value", [0, 1, 306, 309, 432, 499, 600, 999, -1])
def test_get_reason_phrase_unknown_codes_returns_empty_string(value):
    # Unknown codes must yield an empty string, never raise.
    assert httpx.codes.get_reason_phrase(value) == ""


def test_phrase_attribute_matches_get_reason_phrase():
    for member in httpx.codes:
        assert httpx.codes.get_reason_phrase(int(member)) == member.phrase


# ---------------------------------------------------------------------------
# IntEnum semantics
# ---------------------------------------------------------------------------


def test_codes_is_int_subclass():
    assert issubclass(httpx.codes, int)
    assert isinstance(httpx.codes.OK, int)


def test_arithmetic_with_codes_member_yields_int():
    result = httpx.codes.OK + 1
    assert result == 201
    assert isinstance(result, int)


def test_codes_member_usable_as_dict_key_and_equal_to_int():
    d = {httpx.codes.NOT_FOUND: "missing"}
    assert d[404] == "missing"
    assert d[httpx.codes.NOT_FOUND] == "missing"


def test_codes_member_hash_equals_int_hash():
    assert hash(httpx.codes.OK) == hash(200)


def test_str_returns_decimal_value_not_enum_repr():
    # Different from default IntEnum behavior on some Python versions —
    # codes.__str__ is overridden to return the numeric value.
    assert str(httpx.codes.OK) == "200"
    assert str(httpx.codes.NOT_FOUND) == "404"
    assert str(httpx.codes.INTERNAL_SERVER_ERROR) == "500"


# ---------------------------------------------------------------------------
# Numeric / name lookups
# ---------------------------------------------------------------------------


def test_lookup_by_value_returns_member():
    assert httpx.codes(200) is httpx.codes.OK
    assert httpx.codes(404) is httpx.codes.NOT_FOUND
    assert httpx.codes(418) is httpx.codes.IM_A_TEAPOT


def test_lookup_by_unknown_value_raises_value_error():
    with pytest.raises(ValueError):
        httpx.codes(499)
    with pytest.raises(ValueError):
        httpx.codes(0)


def test_lookup_by_name_via_item_access():
    assert httpx.codes["OK"] is httpx.codes.OK
    assert httpx.codes["NOT_FOUND"] is httpx.codes.NOT_FOUND


def test_lookup_by_unknown_name_raises_key_error():
    with pytest.raises(KeyError):
        httpx.codes["DEFINITELY_NOT_A_REAL_STATUS"]


# ---------------------------------------------------------------------------
# Lowercase aliases (requests compatibility)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,value",
    [
        ("ok", 200),
        ("not_found", 404),
        ("internal_server_error", 500),
        ("im_a_teapot", 418),
        ("moved_permanently", 301),
        ("continue_", None),  # not aliased; ensures we don't invent names
    ],
)
def test_lowercase_aliases_are_present_for_known_members(name, value):
    if value is None:
        # Sanity: lowercase aliases are exactly the lowercased member names;
        # there is no rename for Python keywords. `CONTINUE` becomes `continue`.
        assert not hasattr(httpx.codes, name)
    else:
        assert getattr(httpx.codes, name) == value


def test_every_member_has_a_lowercase_alias_equal_to_its_value():
    for member in httpx.codes:
        alias = getattr(httpx.codes, member.name.lower())
        assert alias == int(member)


# ---------------------------------------------------------------------------
# Stability of well-known, frequently-referenced codes
# ---------------------------------------------------------------------------


def test_well_known_status_code_values():
    # Guard against accidental reassignment of the most commonly referenced
    # public constants.
    assert int(httpx.codes.OK) == 200
    assert int(httpx.codes.CREATED) == 201
    assert int(httpx.codes.NO_CONTENT) == 204
    assert int(httpx.codes.MOVED_PERMANENTLY) == 301
    assert int(httpx.codes.FOUND) == 302
    assert int(httpx.codes.NOT_MODIFIED) == 304
    assert int(httpx.codes.BAD_REQUEST) == 400
    assert int(httpx.codes.UNAUTHORIZED) == 401
    assert int(httpx.codes.FORBIDDEN) == 403
    assert int(httpx.codes.NOT_FOUND) == 404
    assert int(httpx.codes.TOO_MANY_REQUESTS) == 429
    assert int(httpx.codes.INTERNAL_SERVER_ERROR) == 500
    assert int(httpx.codes.SERVICE_UNAVAILABLE) == 503
