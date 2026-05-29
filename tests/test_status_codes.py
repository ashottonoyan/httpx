import pytest

import httpx


def test_status_code_as_int():
    # mypy doesn't (yet) recognize that IntEnum members are ints, so ignore it here
    assert httpx.codes.NOT_FOUND == 404  # type: ignore[comparison-overlap]
    assert str(httpx.codes.NOT_FOUND) == "404"


def test_status_code_value_lookup():
    assert httpx.codes(404) == 404


def test_status_code_phrase_lookup():
    assert httpx.codes["NOT_FOUND"] == 404


def test_lowercase_status_code():
    assert httpx.codes.not_found == 404  # type: ignore


def test_reason_phrase_for_status_code():
    assert httpx.codes.get_reason_phrase(404) == "Not Found"


def test_reason_phrase_for_unknown_status_code():
    assert httpx.codes.get_reason_phrase(499) == ""


def test_status_code_phrase_attribute():
    assert httpx.codes.OK.phrase == "OK"  # type: ignore[attr-defined]
    assert httpx.codes.NOT_FOUND.phrase == "Not Found"  # type: ignore[attr-defined]
    assert httpx.codes.IM_A_TEAPOT.phrase == "I'm a teapot"  # type: ignore[attr-defined]
    assert (
        httpx.codes.INTERNAL_SERVER_ERROR.phrase  # type: ignore[attr-defined]
        == "Internal Server Error"
    )


def test_str_returns_value_for_various_codes():
    assert str(httpx.codes.CONTINUE) == "100"
    assert str(httpx.codes.OK) == "200"
    assert str(httpx.codes.MOVED_PERMANENTLY) == "301"
    assert str(httpx.codes.INTERNAL_SERVER_ERROR) == "500"


def test_get_reason_phrase_known_codes():
    assert httpx.codes.get_reason_phrase(100) == "Continue"
    assert httpx.codes.get_reason_phrase(200) == "OK"
    assert httpx.codes.get_reason_phrase(301) == "Moved Permanently"
    assert httpx.codes.get_reason_phrase(418) == "I'm a teapot"
    assert httpx.codes.get_reason_phrase(500) == "Internal Server Error"
    assert httpx.codes.get_reason_phrase(511) == "Network Authentication Required"


def test_get_reason_phrase_unknown_codes_returns_empty():
    assert httpx.codes.get_reason_phrase(0) == ""
    assert httpx.codes.get_reason_phrase(99) == ""
    assert httpx.codes.get_reason_phrase(309) == ""
    assert httpx.codes.get_reason_phrase(420) == ""
    assert httpx.codes.get_reason_phrase(999) == ""


@pytest.mark.parametrize("value", [100, 101, 150, 199])
def test_is_informational_true(value):
    assert httpx.codes.is_informational(value) is True


@pytest.mark.parametrize("value", [0, 99, 200, 300, 400, 500, 600])
def test_is_informational_false(value):
    assert httpx.codes.is_informational(value) is False


@pytest.mark.parametrize("value", [200, 201, 250, 299])
def test_is_success_true(value):
    assert httpx.codes.is_success(value) is True


@pytest.mark.parametrize("value", [0, 100, 199, 300, 400, 500])
def test_is_success_false(value):
    assert httpx.codes.is_success(value) is False


@pytest.mark.parametrize("value", [300, 301, 350, 399])
def test_is_redirect_true(value):
    assert httpx.codes.is_redirect(value) is True


@pytest.mark.parametrize("value", [0, 100, 200, 299, 400, 500])
def test_is_redirect_false(value):
    assert httpx.codes.is_redirect(value) is False


@pytest.mark.parametrize("value", [400, 401, 404, 418, 451, 499])
def test_is_client_error_true(value):
    assert httpx.codes.is_client_error(value) is True


@pytest.mark.parametrize("value", [0, 100, 200, 300, 399, 500, 599])
def test_is_client_error_false(value):
    assert httpx.codes.is_client_error(value) is False


@pytest.mark.parametrize("value", [500, 501, 550, 599])
def test_is_server_error_true(value):
    assert httpx.codes.is_server_error(value) is True


@pytest.mark.parametrize("value", [0, 100, 200, 300, 400, 499, 600])
def test_is_server_error_false(value):
    assert httpx.codes.is_server_error(value) is False


@pytest.mark.parametrize("value", [400, 404, 450, 499, 500, 550, 599])
def test_is_error_true(value):
    assert httpx.codes.is_error(value) is True


@pytest.mark.parametrize("value", [0, 100, 199, 200, 299, 300, 399, 600])
def test_is_error_false(value):
    assert httpx.codes.is_error(value) is False


def test_classifier_accepts_codes_enum_member():
    # The classifiers accept ints, and codes members ARE ints.
    assert httpx.codes.is_informational(httpx.codes.CONTINUE) is True
    assert httpx.codes.is_success(httpx.codes.OK) is True
    assert httpx.codes.is_redirect(httpx.codes.FOUND) is True
    assert httpx.codes.is_client_error(httpx.codes.NOT_FOUND) is True
    assert httpx.codes.is_server_error(httpx.codes.BAD_GATEWAY) is True
    assert httpx.codes.is_error(httpx.codes.NOT_FOUND) is True
    assert httpx.codes.is_error(httpx.codes.BAD_GATEWAY) is True


def test_lookup_by_invalid_value_raises():
    with pytest.raises(ValueError):
        httpx.codes(999)


def test_lookup_by_invalid_name_raises():
    with pytest.raises(KeyError):
        httpx.codes["DOES_NOT_EXIST"]


def test_lowercase_aliases_cover_full_set():
    # The module assigns a lowercase alias for every member; spot-check several.
    assert httpx.codes.ok == 200  # type: ignore[attr-defined]
    assert httpx.codes.created == 201  # type: ignore[attr-defined]
    assert httpx.codes.moved_permanently == 301  # type: ignore[attr-defined]
    assert httpx.codes.im_a_teapot == 418  # type: ignore[attr-defined]
    assert httpx.codes.internal_server_error == 500  # type: ignore[attr-defined]


def test_lowercase_aliases_are_plain_ints():
    # The setattr loop stores int(code), not the enum member.
    assert type(httpx.codes.ok) is int  # type: ignore[attr-defined]
    assert type(httpx.codes.not_found) is int  # type: ignore[attr-defined]


def test_codes_member_is_int_instance():
    assert isinstance(httpx.codes.OK, int)
    assert int(httpx.codes.OK) == 200


def test_codes_equality_with_int():
    assert httpx.codes.OK == 200
    assert httpx.codes.NOT_FOUND != 200
