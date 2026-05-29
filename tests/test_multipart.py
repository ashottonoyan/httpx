from __future__ import annotations

import io
import tempfile
import typing

import pytest

import httpx


def echo_request_content(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=request.content)


@pytest.mark.parametrize(("value,output"), (("abc", b"abc"), (b"abc", b"abc")))
def test_multipart(value, output):
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    # Test with a single-value 'data' argument, and a plain file 'files' argument.
    data = {"text": value}
    files = {"file": io.BytesIO(b"<file content>")}
    response = client.post("http://127.0.0.1:8000/", data=data, files=files)
    boundary = response.request.headers["Content-Type"].split("boundary=")[-1]
    boundary_bytes = boundary.encode("ascii")

    assert response.status_code == 200
    assert response.content == b"".join(
        [
            b"--" + boundary_bytes + b"\r\n",
            b'Content-Disposition: form-data; name="text"\r\n',
            b"\r\n",
            b"abc\r\n",
            b"--" + boundary_bytes + b"\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--" + boundary_bytes + b"--\r\n",
        ]
    )


@pytest.mark.parametrize(
    "header",
    [
        "multipart/form-data; boundary=+++; charset=utf-8",
        "multipart/form-data; charset=utf-8; boundary=+++",
        "multipart/form-data; boundary=+++",
        "multipart/form-data; boundary=+++ ;",
        'multipart/form-data; boundary="+++"; charset=utf-8',
        'multipart/form-data; charset=utf-8; boundary="+++"',
        'multipart/form-data; boundary="+++"',
        'multipart/form-data; boundary="+++" ;',
    ],
)
def test_multipart_explicit_boundary(header: str) -> None:
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    files = {"file": io.BytesIO(b"<file content>")}
    headers = {"content-type": header}
    response = client.post("http://127.0.0.1:8000/", files=files, headers=headers)
    boundary_bytes = b"+++"

    assert response.status_code == 200
    assert response.request.headers["Content-Type"] == header
    assert response.content == b"".join(
        [
            b"--" + boundary_bytes + b"\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--" + boundary_bytes + b"--\r\n",
        ]
    )


@pytest.mark.parametrize(
    "header",
    [
        "multipart/form-data; charset=utf-8",
        "multipart/form-data; charset=utf-8; ",
    ],
)
def test_multipart_header_without_boundary(header: str) -> None:
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    files = {"file": io.BytesIO(b"<file content>")}
    headers = {"content-type": header}
    response = client.post("http://127.0.0.1:8000/", files=files, headers=headers)

    assert response.status_code == 200
    assert response.request.headers["Content-Type"] == header


@pytest.mark.parametrize(("key"), (b"abc", 1, 2.3, None))
def test_multipart_invalid_key(key):
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    data = {key: "abc"}
    files = {"file": io.BytesIO(b"<file content>")}
    with pytest.raises(TypeError) as e:
        client.post(
            "http://127.0.0.1:8000/",
            data=data,
            files=files,
        )
    assert "Invalid type for name" in str(e.value)
    assert repr(key) in str(e.value)


@pytest.mark.parametrize(("value"), (object(), {"key": "value"}))
def test_multipart_invalid_value(value):
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    data = {"text": value}
    files = {"file": io.BytesIO(b"<file content>")}
    with pytest.raises(TypeError) as e:
        client.post("http://127.0.0.1:8000/", data=data, files=files)
    assert "Invalid type for value" in str(e.value)


def test_multipart_file_tuple():
    client = httpx.Client(transport=httpx.MockTransport(echo_request_content))

    # Test with a list of values 'data' argument,
    #     and a tuple style 'files' argument.
    data = {"text": ["abc"]}
    files = {"file": ("name.txt", io.BytesIO(b"<file content>"))}
    response = client.post("http://127.0.0.1:8000/", data=data, files=files)
    boundary = response.request.headers["Content-Type"].split("boundary=")[-1]
    boundary_bytes = boundary.encode("ascii")

    assert response.status_code == 200
    assert response.content == b"".join(
        [
            b"--" + boundary_bytes + b"\r\n",
            b'Content-Disposition: form-data; name="text"\r\n',
            b"\r\n",
            b"abc\r\n",
            b"--" + boundary_bytes + b"\r\n",
            b'Content-Disposition: form-data; name="file"; filename="name.txt"\r\n',
            b"Content-Type: text/plain\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--" + boundary_bytes + b"--\r\n",
        ]
    )


@pytest.mark.parametrize("file_content_type", [None, "text/plain"])
def test_multipart_file_tuple_headers(file_content_type: str | None) -> None:
    file_name = "test.txt"
    file_content = io.BytesIO(b"<file content>")
    file_headers = {"Expires": "0"}

    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": (file_name, file_content, file_content_type, file_headers)}

    request = httpx.Request("POST", url, headers=headers, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        f'--BOUNDARY\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{file_name}"\r\nExpires: 0\r\nContent-Type: '
        f"text/plain\r\n\r\n<file content>\r\n--BOUNDARY--\r\n"
        "".encode("ascii")
    )


def test_multipart_headers_include_content_type() -> None:
    """
    Content-Type from 4th tuple parameter (headers) should
    override the 3rd parameter (content_type)
    """
    file_name = "test.txt"
    file_content = io.BytesIO(b"<file content>")
    file_content_type = "text/plain"
    file_headers = {"Content-Type": "image/png"}

    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": (file_name, file_content, file_content_type, file_headers)}

    request = httpx.Request("POST", url, headers=headers, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        f'--BOUNDARY\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{file_name}"\r\nContent-Type: '
        f"image/png\r\n\r\n<file content>\r\n--BOUNDARY--\r\n"
        "".encode("ascii")
    )


def test_multipart_encode(tmp_path: typing.Any) -> None:
    path = str(tmp_path / "name.txt")
    with open(path, "wb") as f:
        f.write(b"<file content>")

    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    data = {
        "a": "1",
        "b": b"C",
        "c": ["11", "22", "33"],
        "d": "",
        "e": True,
        "f": "",
    }
    with open(path, "rb") as input_file:
        files = {"file": ("name.txt", input_file)}

        request = httpx.Request("POST", url, headers=headers, data=data, files=files)
        request.read()

        assert request.headers == {
            "Host": "www.example.com",
            "Content-Type": "multipart/form-data; boundary=BOUNDARY",
            "Content-Length": str(len(request.content)),
        }
        assert request.content == (
            '--BOUNDARY\r\nContent-Disposition: form-data; name="a"\r\n\r\n1\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="b"\r\n\r\nC\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="c"\r\n\r\n11\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="c"\r\n\r\n22\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="c"\r\n\r\n33\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="d"\r\n\r\n\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="e"\r\n\r\ntrue\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="f"\r\n\r\n\r\n'
            '--BOUNDARY\r\nContent-Disposition: form-data; name="file";'
            ' filename="name.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n<file content>\r\n"
            "--BOUNDARY--\r\n"
            "".encode("ascii")
        )


def test_multipart_encode_unicode_file_contents() -> None:
    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": ("name.txt", b"<bytes content>")}

    request = httpx.Request("POST", url, headers=headers, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        b'--BOUNDARY\r\nContent-Disposition: form-data; name="file";'
        b' filename="name.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n<bytes content>\r\n"
        b"--BOUNDARY--\r\n"
    )


def test_multipart_encode_files_allows_filenames_as_none() -> None:
    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": (None, io.BytesIO(b"<file content>"))}

    request = httpx.Request("POST", url, headers=headers, data={}, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        '--BOUNDARY\r\nContent-Disposition: form-data; name="file"\r\n\r\n'
        "<file content>\r\n--BOUNDARY--\r\n"
        "".encode("ascii")
    )


@pytest.mark.parametrize(
    "file_name,expected_content_type",
    [
        ("example.json", "application/json"),
        ("example.txt", "text/plain"),
        ("no-extension", "application/octet-stream"),
    ],
)
def test_multipart_encode_files_guesses_correct_content_type(
    file_name: str, expected_content_type: str
) -> None:
    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": (file_name, io.BytesIO(b"<file content>"))}

    request = httpx.Request("POST", url, headers=headers, data={}, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        f'--BOUNDARY\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{file_name}"\r\nContent-Type: '
        f"{expected_content_type}\r\n\r\n<file content>\r\n--BOUNDARY--\r\n"
        "".encode("ascii")
    )


def test_multipart_encode_files_allows_bytes_content() -> None:
    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": ("test.txt", b"<bytes content>", "text/plain")}

    request = httpx.Request("POST", url, headers=headers, data={}, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        '--BOUNDARY\r\nContent-Disposition: form-data; name="file"; '
        'filename="test.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n<bytes content>\r\n"
        "--BOUNDARY--\r\n"
        "".encode("ascii")
    )


def test_multipart_encode_files_allows_str_content() -> None:
    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    files = {"file": ("test.txt", "<str content>", "text/plain")}

    request = httpx.Request("POST", url, headers=headers, data={}, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Content-Length": str(len(request.content)),
    }
    assert request.content == (
        '--BOUNDARY\r\nContent-Disposition: form-data; name="file"; '
        'filename="test.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n<str content>\r\n"
        "--BOUNDARY--\r\n"
        "".encode("ascii")
    )


def test_multipart_encode_files_raises_exception_with_StringIO_content() -> None:
    url = "https://www.example.com"
    files = {"file": ("test.txt", io.StringIO("content"), "text/plain")}
    with pytest.raises(TypeError):
        httpx.Request("POST", url, data={}, files=files)  # type: ignore


def test_multipart_encode_files_raises_exception_with_text_mode_file() -> None:
    url = "https://www.example.com"
    with tempfile.TemporaryFile(mode="w") as upload:
        files = {"file": ("test.txt", upload, "text/plain")}
        with pytest.raises(TypeError):
            httpx.Request("POST", url, data={}, files=files)  # type: ignore


def test_multipart_encode_non_seekable_filelike() -> None:
    """
    Test that special readable but non-seekable filelike objects are supported.
    In this case uploads with use 'Transfer-Encoding: chunked', instead of
    a 'Content-Length' header.
    """

    class IteratorIO(io.IOBase):
        def __init__(self, iterator: typing.Iterator[bytes]) -> None:
            self._iterator = iterator

        def read(self, *args: typing.Any) -> bytes:
            return b"".join(self._iterator)

    def data() -> typing.Iterator[bytes]:
        yield b"Hello"
        yield b"World"

    url = "https://www.example.com/"
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    fileobj: typing.Any = IteratorIO(data())
    files = {"file": fileobj}

    request = httpx.Request("POST", url, headers=headers, files=files)
    request.read()

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        "Transfer-Encoding": "chunked",
    }
    assert request.content == (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"; filename="upload"\r\n'
        b"Content-Type: application/octet-stream\r\n"
        b"\r\n"
        b"HelloWorld\r\n"
        b"--BOUNDARY--\r\n"
    )


def test_multipart_rewinds_files():
    with tempfile.TemporaryFile() as upload:
        upload.write(b"Hello, world!")

        transport = httpx.MockTransport(echo_request_content)
        client = httpx.Client(transport=transport)

        files = {"file": upload}
        response = client.post("http://127.0.0.1:8000/", files=files)
        assert response.status_code == 200
        assert b"\r\nHello, world!\r\n" in response.content

        # POSTing the same file instance a second time should have the same content.
        files = {"file": upload}
        response = client.post("http://127.0.0.1:8000/", files=files)
        assert response.status_code == 200
        assert b"\r\nHello, world!\r\n" in response.content


class TestHeaderParamHTML5Formatting:
    def test_unicode(self):
        filename = "n\u00e4me"
        expected = b'filename="n\xc3\xa4me"'
        files = {"upload": (filename, b"<file content>")}
        request = httpx.Request("GET", "https://www.example.com", files=files)
        assert expected in request.read()

    def test_ascii(self):
        filename = "name"
        expected = b'filename="name"'
        files = {"upload": (filename, b"<file content>")}
        request = httpx.Request("GET", "https://www.example.com", files=files)
        assert expected in request.read()

    def test_unicode_escape(self):
        filename = "hello\\world\u0022"
        expected = b'filename="hello\\\\world%22"'
        files = {"upload": (filename, b"<file content>")}
        request = httpx.Request("GET", "https://www.example.com", files=files)
        assert expected in request.read()

    def test_unicode_with_control_character(self):
        filename = "hello\x1a\x1b\x1c"
        expected = b'filename="hello%1A\x1b%1C"'
        files = {"upload": (filename, b"<file content>")}
        request = httpx.Request("GET", "https://www.example.com", files=files)
        assert expected in request.read()


# Direct unit tests against the _multipart module internals to exercise
# code paths not easily reached via the public httpx.Request interface.

from httpx._multipart import (  # noqa: E402
    DataField,
    FileField,
    MultipartStream,
    get_multipart_boundary_from_content_type,
)


class TestGetMultipartBoundaryFromContentType:
    def test_none_content_type_returns_none(self):
        assert get_multipart_boundary_from_content_type(None) is None

    def test_non_multipart_content_type_returns_none(self):
        assert (
            get_multipart_boundary_from_content_type(b"application/json") is None
        )

    def test_multipart_without_semicolon_returns_none(self):
        # No `;` in the header means no boundary parameter section to parse.
        assert (
            get_multipart_boundary_from_content_type(b"multipart/form-data") is None
        )

    def test_multipart_with_boundary_returns_bytes(self):
        result = get_multipart_boundary_from_content_type(
            b"multipart/form-data; boundary=abc123"
        )
        assert result == b"abc123"

    def test_multipart_with_quoted_boundary_strips_quotes(self):
        result = get_multipart_boundary_from_content_type(
            b'multipart/form-data; boundary="abc 123"'
        )
        assert result == b"abc 123"

    def test_multipart_with_other_parameters_only_returns_none(self):
        # Has a `;` but no `boundary=` parameter.
        assert (
            get_multipart_boundary_from_content_type(
                b"multipart/form-data; charset=utf-8"
            )
            is None
        )

    def test_multipart_boundary_is_case_insensitive(self):
        # The `boundary=` token match is lowercased before comparison.
        result = get_multipart_boundary_from_content_type(
            b"multipart/form-data; BOUNDARY=xyz"
        )
        assert result == b"xyz"


class TestDataField:
    def test_invalid_name_type_raises(self):
        with pytest.raises(TypeError) as exc:
            DataField(name=123, value="x")  # type: ignore[arg-type]
        assert "Invalid type for name" in str(exc.value)

    def test_invalid_value_type_raises(self):
        with pytest.raises(TypeError) as exc:
            DataField(name="x", value=[1, 2])  # type: ignore[arg-type]
        assert "Invalid type for value" in str(exc.value)

    def test_none_value_is_coerced_to_empty_string(self):
        field = DataField(name="x", value=None)
        assert field.render_data() == b""

    def test_int_value_is_coerced_to_string(self):
        field = DataField(name="x", value=42)
        assert field.render_data() == b"42"

    def test_float_value_is_coerced_to_string(self):
        field = DataField(name="x", value=1.5)
        assert field.render_data() == b"1.5"

    def test_bytes_value_is_preserved(self):
        field = DataField(name="x", value=b"\x00\x01raw")
        assert field.render_data() == b"\x00\x01raw"

    def test_render_headers_is_cached(self):
        # Second call should return the exact same bytes object (memoised).
        field = DataField(name="x", value="v")
        first = field.render_headers()
        second = field.render_headers()
        assert first is second

    def test_render_data_is_cached(self):
        field = DataField(name="x", value="v")
        first = field.render_data()
        second = field.render_data()
        assert first is second

    def test_get_length_matches_rendered_output(self):
        field = DataField(name="key", value="value")
        rendered = b"".join(field.render())
        assert field.get_length() == len(rendered)

    def test_render_yields_headers_then_data(self):
        field = DataField(name="k", value="v")
        chunks = list(field.render())
        assert len(chunks) == 2
        assert chunks[0] == field.render_headers()
        assert chunks[1] == field.render_data()


class TestFileField:
    def test_four_tuple_form(self):
        # All 4 elements: filename, fileobj, content_type, headers
        field = FileField(
            name="f",
            value=("n.txt", b"data", "text/csv", {"X-Custom": "1"}),
        )
        headers = field.render_headers()
        assert b'name="f"' in headers
        assert b'filename="n.txt"' in headers
        assert b"X-Custom: 1" in headers
        assert b"Content-Type: text/csv" in headers

    def test_filename_inferred_from_file_object_name_attribute(self):
        # `value` is not a tuple; FileField pulls `.name` off the object.
        fileobj = io.BytesIO(b"abc")
        fileobj.name = "/tmp/some/path/inferred.txt"  # type: ignore[attr-defined]
        field = FileField(name="f", value=fileobj)
        assert field.filename == "inferred.txt"

    def test_filename_defaults_to_upload_when_no_name(self):
        field = FileField(name="f", value=io.BytesIO(b"abc"))
        assert field.filename == "upload"

    def test_stringio_raises_typeerror(self):
        with pytest.raises(TypeError, match="io.StringIO"):
            FileField(name="f", value=io.StringIO("nope"))  # type: ignore[arg-type]

    def test_text_mode_file_raises_typeerror(self):
        with tempfile.TemporaryFile(mode="w") as upload:
            with pytest.raises(TypeError, match="binary mode"):
                FileField(name="f", value=upload)  # type: ignore[arg-type]

    def test_content_type_in_headers_not_overridden_by_guess(self):
        # When 4th-tuple headers include Content-Type (any case), the
        # tuple's 3rd content_type / guessed one is NOT injected again.
        field = FileField(
            name="f",
            value=("a.txt", b"x", None, {"content-type": "application/x-keep"}),
        )
        headers = field.render_headers()
        assert headers.count(b"Content-Type") + headers.count(b"content-type") == 1
        assert b"content-type: application/x-keep" in headers

    def test_get_length_with_bytes_content(self):
        field = FileField(name="f", value=("a.txt", b"hello"))
        headers_len = len(field.render_headers())
        assert field.get_length() == headers_len + len(b"hello")

    def test_get_length_with_str_content(self):
        field = FileField(name="f", value=("a.txt", "hello"))
        headers_len = len(field.render_headers())
        assert field.get_length() == headers_len + len(b"hello")

    def test_get_length_with_unknown_file_length_returns_none(self):
        # A non-seekable file-like with no fileno → peek_filelike_length
        # cannot determine the size, so get_length returns None.
        class UnknownLen(io.IOBase):
            def read(self, *a):
                return b""

        field = FileField(name="f", value=UnknownLen())  # type: ignore[arg-type]
        assert field.get_length() is None

    def test_render_data_with_str_yields_bytes(self):
        field = FileField(name="f", value=("a.txt", "abc"))
        assert list(field.render_data()) == [b"abc"]

    def test_render_data_chunks_large_file(self):
        # File larger than CHUNK_SIZE should be yielded in multiple chunks.
        payload = b"x" * (FileField.CHUNK_SIZE + 100)
        field = FileField(name="f", value=("big.bin", io.BytesIO(payload)))
        chunks = list(field.render_data())
        assert len(chunks) >= 2
        assert b"".join(chunks) == payload

    def test_render_data_seek_unsupported_is_swallowed(self):
        # If the underlying file's seek() raises UnsupportedOperation,
        # render_data must continue rather than propagating the error.
        class NonSeekable(io.RawIOBase):
            def __init__(self, data: bytes):
                self._data = data
                self._read = False

            def readable(self) -> bool:
                return True

            def seekable(self) -> bool:
                return False

            def seek(self, *a, **kw):
                raise io.UnsupportedOperation("seek")

            def read(self, *a):
                if self._read:
                    return b""
                self._read = True
                return self._data

        field = FileField(
            name="f", value=("a.bin", typing.cast(typing.Any, NonSeekable(b"payload")))
        )
        assert b"".join(field.render_data()) == b"payload"


class TestMultipartStream:
    def test_auto_boundary_is_32_char_ascii_hex(self):
        stream = MultipartStream(data={}, files={})
        assert len(stream.boundary) == 32
        # All characters should be valid ASCII hex digits.
        assert all(chr(b) in "0123456789abcdef" for b in stream.boundary)
        assert stream.content_type.startswith("multipart/form-data; boundary=")

    def test_files_passed_as_list_of_tuples(self):
        # The `files` argument supports list-of-(name, value) tuples,
        # not just a Mapping.
        stream = MultipartStream(
            data={},
            files=[
                ("a", io.BytesIO(b"1")),
                ("a", io.BytesIO(b"2")),
            ],
            boundary=b"B",
        )
        body = b"".join(stream.iter_chunks())
        # Both file fields named "a" should appear in the output.
        assert body.count(b'name="a"') == 2
        assert b"1" in body
        assert b"2" in body

    def test_get_headers_uses_content_length_for_known_size(self):
        stream = MultipartStream(
            data={"x": "y"}, files={}, boundary=b"BOUNDARY"
        )
        headers = stream.get_headers()
        assert "Content-Length" in headers
        assert "Transfer-Encoding" not in headers
        assert headers["Content-Length"] == str(stream.get_content_length())
        assert headers["Content-Type"] == "multipart/form-data; boundary=BOUNDARY"

    def test_get_headers_uses_chunked_when_length_unknown(self):
        class UnknownLen(io.IOBase):
            def read(self, *a):
                return b""

        stream = MultipartStream(
            data={},
            files={"f": typing.cast(typing.Any, UnknownLen())},
            boundary=b"BOUNDARY",
        )
        headers = stream.get_headers()
        assert headers == {
            "Transfer-Encoding": "chunked",
            "Content-Type": "multipart/form-data; boundary=BOUNDARY",
        }
        assert stream.get_content_length() is None

    def test_sync_iter_equals_iter_chunks(self):
        stream = MultipartStream(
            data={"k": "v"},
            files={"f": ("a.txt", b"body", "text/plain")},
            boundary=b"BOUNDARY",
        )
        assert b"".join(iter(stream)) == b"".join(stream.iter_chunks())

    @pytest.mark.anyio
    async def test_async_iter_equals_iter_chunks(self):
        stream = MultipartStream(
            data={"k": "v"},
            files={"f": ("a.txt", b"body", "text/plain")},
            boundary=b"BOUNDARY",
        )
        collected = b""
        async for chunk in stream:
            collected += chunk
        assert collected == b"".join(stream.iter_chunks())

    def test_data_list_value_emits_one_field_per_item(self):
        stream = MultipartStream(
            data={"k": ["a", "b", "c"]},
            files={},
            boundary=b"B",
        )
        body = b"".join(stream.iter_chunks())
        assert body.count(b'name="k"') == 3
        # Multiple boundary separators plus the closing one.
        assert body.count(b"--B\r\n") == 3
        assert body.endswith(b"--B--\r\n")

    def test_get_content_length_matches_actual_body_length(self):
        stream = MultipartStream(
            data={"k": "v", "n": "42"},
            files={"f": ("a.txt", b"body", "text/plain")},
            boundary=b"BOUNDARY",
        )
        assert stream.get_content_length() == len(b"".join(stream.iter_chunks()))
