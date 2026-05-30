import pytest

import httpx


@pytest.mark.parametrize("value", [100, 101, 150, 199])
def test_is_informational_true(value):
    assert httpx.codes.is_informational(value) is True


@pytest.mark.parametrize("value", [99, 200, 301, 404, 500])
def test_is_informational_false(value):
    assert httpx.codes.is_informational(value) is False


@pytest.mark.parametrize("value", [200, 201, 250, 299])
def test_is_success_true(value):
    assert httpx.codes.is_success(value) is True


@pytest.mark.parametrize("value", [199, 300, 404, 500])
def test_is_success_false(value):
    assert httpx.codes.is_success(value) is False


@pytest.mark.parametrize("value", [300, 301, 307, 399])
def test_is_redirect_true(value):
    assert httpx.codes.is_redirect(value) is True


@pytest.mark.parametrize("value", [299, 400, 404, 500])
def test_is_redirect_false(value):
    assert httpx.codes.is_redirect(value) is False


@pytest.mark.parametrize("value", [400, 401, 404, 499])
def test_is_client_error_true(value):
    assert httpx.codes.is_client_error(value) is True


@pytest.mark.parametrize("value", [399, 500, 200, 600])
def test_is_client_error_false(value):
    assert httpx.codes.is_client_error(value) is False


@pytest.mark.parametrize("value", [500, 501, 503, 599])
def test_is_server_error_true(value):
    assert httpx.codes.is_server_error(value) is True


@pytest.mark.parametrize("value", [499, 600, 200, 404])
def test_is_server_error_false(value):
    assert httpx.codes.is_server_error(value) is False


@pytest.mark.parametrize("value", [400, 404, 499, 500, 503, 599])
def test_is_error_true(value):
    assert httpx.codes.is_error(value) is True


@pytest.mark.parametrize("value", [100, 200, 301, 399, 600])
def test_is_error_false(value):
    assert httpx.codes.is_error(value) is False
