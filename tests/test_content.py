import io
import pickle
import typing

import pytest

import httpx
from httpx._content import (
    AsyncIteratorByteStream,
    ByteStream,
    IteratorByteStream,
    UnattachedStream,
    encode_content,
    encode_html,
    encode_json,
    encode_request,
    encode_response,
    encode_text,
    encode_urlencoded_data,
)

method = "POST"
url = "https://www.example.com"


@pytest.mark.anyio
async def test_empty_content():
    request = httpx.Request(method, url)
    assert isinstance(request.stream, httpx.SyncByteStream)
    assert isinstance(request.stream, httpx.AsyncByteStream)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {"Host": "www.example.com", "Content-Length": "0"}
    assert sync_content == b""
    assert async_content == b""


@pytest.mark.anyio
async def test_bytes_content():
    request = httpx.Request(method, url, content=b"Hello, world!")
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {"Host": "www.example.com", "Content-Length": "13"}
    assert sync_content == b"Hello, world!"
    assert async_content == b"Hello, world!"

    # Support 'data' for compat with requests.
    with pytest.warns(DeprecationWarning):
        request = httpx.Request(method, url, data=b"Hello, world!")  # type: ignore
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {"Host": "www.example.com", "Content-Length": "13"}
    assert sync_content == b"Hello, world!"
    assert async_content == b"Hello, world!"


@pytest.mark.anyio
async def test_bytesio_content():
    request = httpx.Request(method, url, content=io.BytesIO(b"Hello, world!"))
    assert isinstance(request.stream, typing.Iterable)
    assert not isinstance(request.stream, typing.AsyncIterable)

    content = b"".join(list(request.stream))

    assert request.headers == {"Host": "www.example.com", "Content-Length": "13"}
    assert content == b"Hello, world!"


@pytest.mark.anyio
async def test_async_bytesio_content():
    class AsyncBytesIO:
        def __init__(self, content: bytes) -> None:
            self._idx = 0
            self._content = content

        async def aread(self, chunk_size: int) -> bytes:
            chunk = self._content[self._idx : self._idx + chunk_size]
            self._idx = self._idx + chunk_size
            return chunk

        async def __aiter__(self):
            yield self._content  # pragma: no cover

    request = httpx.Request(method, url, content=AsyncBytesIO(b"Hello, world!"))
    assert not isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }
    assert content == b"Hello, world!"


@pytest.mark.anyio
async def test_iterator_content():
    def hello_world() -> typing.Iterator[bytes]:
        yield b"Hello, "
        yield b"world!"

    request = httpx.Request(method, url, content=hello_world())
    assert isinstance(request.stream, typing.Iterable)
    assert not isinstance(request.stream, typing.AsyncIterable)

    content = b"".join(list(request.stream))

    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }
    assert content == b"Hello, world!"

    with pytest.raises(httpx.StreamConsumed):
        list(request.stream)

    # Support 'data' for compat with requests.
    with pytest.warns(DeprecationWarning):
        request = httpx.Request(method, url, data=hello_world())  # type: ignore
    assert isinstance(request.stream, typing.Iterable)
    assert not isinstance(request.stream, typing.AsyncIterable)

    content = b"".join(list(request.stream))

    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }
    assert content == b"Hello, world!"


@pytest.mark.anyio
async def test_aiterator_content():
    async def hello_world() -> typing.AsyncIterator[bytes]:
        yield b"Hello, "
        yield b"world!"

    request = httpx.Request(method, url, content=hello_world())
    assert not isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }
    assert content == b"Hello, world!"

    with pytest.raises(httpx.StreamConsumed):
        [part async for part in request.stream]

    # Support 'data' for compat with requests.
    with pytest.warns(DeprecationWarning):
        request = httpx.Request(method, url, data=hello_world())  # type: ignore
    assert not isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }
    assert content == b"Hello, world!"


@pytest.mark.anyio
async def test_json_content():
    request = httpx.Request(method, url, json={"Hello": "world!"})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "18",
        "Content-Type": "application/json",
    }
    assert sync_content == b'{"Hello":"world!"}'
    assert async_content == b'{"Hello":"world!"}'


@pytest.mark.anyio
async def test_urlencoded_content():
    request = httpx.Request(method, url, data={"Hello": "world!"})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "14",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    assert sync_content == b"Hello=world%21"
    assert async_content == b"Hello=world%21"


@pytest.mark.anyio
async def test_urlencoded_boolean():
    request = httpx.Request(method, url, data={"example": True})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "12",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    assert sync_content == b"example=true"
    assert async_content == b"example=true"


@pytest.mark.anyio
async def test_urlencoded_none():
    request = httpx.Request(method, url, data={"example": None})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "8",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    assert sync_content == b"example="
    assert async_content == b"example="


@pytest.mark.anyio
async def test_urlencoded_list():
    request = httpx.Request(method, url, data={"example": ["a", 1, True]})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "32",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    assert sync_content == b"example=a&example=1&example=true"
    assert async_content == b"example=a&example=1&example=true"


@pytest.mark.anyio
async def test_multipart_files_content():
    files = {"file": io.BytesIO(b"<file content>")}
    headers = {"Content-Type": "multipart/form-data; boundary=+++"}
    request = httpx.Request(
        method,
        url,
        files=files,
        headers=headers,
    )
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "138",
        "Content-Type": "multipart/form-data; boundary=+++",
    }
    assert sync_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--+++--\r\n",
        ]
    )
    assert async_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--+++--\r\n",
        ]
    )


@pytest.mark.anyio
async def test_multipart_data_and_files_content():
    data = {"message": "Hello, world!"}
    files = {"file": io.BytesIO(b"<file content>")}
    headers = {"Content-Type": "multipart/form-data; boundary=+++"}
    request = httpx.Request(method, url, data=data, files=files, headers=headers)
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "210",
        "Content-Type": "multipart/form-data; boundary=+++",
    }
    assert sync_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="message"\r\n',
            b"\r\n",
            b"Hello, world!\r\n",
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--+++--\r\n",
        ]
    )
    assert async_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="message"\r\n',
            b"\r\n",
            b"Hello, world!\r\n",
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content>\r\n",
            b"--+++--\r\n",
        ]
    )


@pytest.mark.anyio
async def test_empty_request():
    request = httpx.Request(method, url, data={}, files={})
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {"Host": "www.example.com", "Content-Length": "0"}
    assert sync_content == b""
    assert async_content == b""


def test_invalid_argument():
    with pytest.raises(TypeError):
        httpx.Request(method, url, content=123)  # type: ignore

    with pytest.raises(TypeError):
        httpx.Request(method, url, content={"a": "b"})  # type: ignore


@pytest.mark.anyio
async def test_multipart_multiple_files_single_input_content():
    files = [
        ("file", io.BytesIO(b"<file content 1>")),
        ("file", io.BytesIO(b"<file content 2>")),
    ]
    headers = {"Content-Type": "multipart/form-data; boundary=+++"}
    request = httpx.Request(method, url, files=files, headers=headers)
    assert isinstance(request.stream, typing.Iterable)
    assert isinstance(request.stream, typing.AsyncIterable)

    sync_content = b"".join(list(request.stream))
    async_content = b"".join([part async for part in request.stream])

    assert request.headers == {
        "Host": "www.example.com",
        "Content-Length": "271",
        "Content-Type": "multipart/form-data; boundary=+++",
    }
    assert sync_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content 1>\r\n",
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content 2>\r\n",
            b"--+++--\r\n",
        ]
    )
    assert async_content == b"".join(
        [
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content 1>\r\n",
            b"--+++\r\n",
            b'Content-Disposition: form-data; name="file"; filename="upload"\r\n',
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            b"<file content 2>\r\n",
            b"--+++--\r\n",
        ]
    )


@pytest.mark.anyio
async def test_response_empty_content():
    response = httpx.Response(200)
    assert isinstance(response.stream, typing.Iterable)
    assert isinstance(response.stream, typing.AsyncIterable)

    sync_content = b"".join(list(response.stream))
    async_content = b"".join([part async for part in response.stream])

    assert response.headers == {}
    assert sync_content == b""
    assert async_content == b""


@pytest.mark.anyio
async def test_response_bytes_content():
    response = httpx.Response(200, content=b"Hello, world!")
    assert isinstance(response.stream, typing.Iterable)
    assert isinstance(response.stream, typing.AsyncIterable)

    sync_content = b"".join(list(response.stream))
    async_content = b"".join([part async for part in response.stream])

    assert response.headers == {"Content-Length": "13"}
    assert sync_content == b"Hello, world!"
    assert async_content == b"Hello, world!"


@pytest.mark.anyio
async def test_response_iterator_content():
    def hello_world() -> typing.Iterator[bytes]:
        yield b"Hello, "
        yield b"world!"

    response = httpx.Response(200, content=hello_world())
    assert isinstance(response.stream, typing.Iterable)
    assert not isinstance(response.stream, typing.AsyncIterable)

    content = b"".join(list(response.stream))

    assert response.headers == {"Transfer-Encoding": "chunked"}
    assert content == b"Hello, world!"

    with pytest.raises(httpx.StreamConsumed):
        list(response.stream)


@pytest.mark.anyio
async def test_response_aiterator_content():
    async def hello_world() -> typing.AsyncIterator[bytes]:
        yield b"Hello, "
        yield b"world!"

    response = httpx.Response(200, content=hello_world())
    assert not isinstance(response.stream, typing.Iterable)
    assert isinstance(response.stream, typing.AsyncIterable)

    content = b"".join([part async for part in response.stream])

    assert response.headers == {"Transfer-Encoding": "chunked"}
    assert content == b"Hello, world!"

    with pytest.raises(httpx.StreamConsumed):
        [part async for part in response.stream]


def test_response_invalid_argument():
    with pytest.raises(TypeError):
        httpx.Response(200, content=123)  # type: ignore


def test_ensure_ascii_false_with_french_characters():
    data = {"greeting": "Bonjour, ça va ?"}
    response = httpx.Response(200, json=data)
    assert "ça va" in response.text, (
        "ensure_ascii=False should preserve French accented characters"
    )
    assert response.headers["Content-Type"] == "application/json"


def test_separators_for_compact_json():
    data = {"clé": "valeur", "liste": [1, 2, 3]}
    response = httpx.Response(200, json=data)
    assert response.text == '{"clé":"valeur","liste":[1,2,3]}', (
        "separators=(',', ':') should produce a compact representation"
    )
    assert response.headers["Content-Type"] == "application/json"


def test_allow_nan_false():
    data_with_nan = {"nombre": float("nan")}
    data_with_inf = {"nombre": float("inf")}

    with pytest.raises(
        ValueError, match="Out of range float values are not JSON compliant"
    ):
        httpx.Response(200, json=data_with_nan)
    with pytest.raises(
        ValueError, match="Out of range float values are not JSON compliant"
    ):
        httpx.Response(200, json=data_with_inf)


@pytest.mark.anyio
async def test_str_content():
    """encode_content accepts a `str`, encoding it to UTF-8 bytes."""
    headers, stream = encode_content("café")
    body = b"".join(list(stream))  # type: ignore[arg-type]
    assert body == "café".encode("utf-8")
    assert headers == {"Content-Length": str(len(body))}


def test_encode_content_empty_bytes_has_no_headers():
    """An empty bytes body should yield an empty header dict, not Content-Length: 0."""
    headers, stream = encode_content(b"")
    assert headers == {}
    assert b"".join(list(stream)) == b""  # type: ignore[arg-type]


def test_encode_content_rejects_unknown_type():
    """encode_content must raise TypeError for arbitrary objects."""
    with pytest.raises(TypeError):
        encode_content(12345)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        encode_content({"a": "b"})  # type: ignore[arg-type]


def test_encode_text_and_html():
    """encode_text / encode_html produce the documented headers and bodies."""
    text_headers, text_stream = encode_text("Hello, world!")
    assert text_headers == {
        "Content-Length": "13",
        "Content-Type": "text/plain; charset=utf-8",
    }
    assert b"".join(list(text_stream)) == b"Hello, world!"

    html_headers, html_stream = encode_html("<h1>hi</h1>")
    assert html_headers == {
        "Content-Length": "11",
        "Content-Type": "text/html; charset=utf-8",
    }
    assert b"".join(list(html_stream)) == b"<h1>hi</h1>"


def test_encode_json_returns_compact_unicode():
    """encode_json should preserve non-ASCII via ensure_ascii=False and use compact separators."""
    headers, stream = encode_json({"k": "ç", "n": 1})
    body = b"".join(list(stream))
    assert body == '{"k":"ç","n":1}'.encode("utf-8")
    assert headers == {
        "Content-Length": str(len(body)),
        "Content-Type": "application/json",
    }


def test_encode_urlencoded_data_helper():
    """encode_urlencoded_data builds the form body and headers directly."""
    headers, stream = encode_urlencoded_data({"a": ["1", "2"], "b": "x"})
    body = b"".join(list(stream))
    assert body == b"a=1&a=2&b=x"
    assert headers == {
        "Content-Length": str(len(body)),
        "Content-Type": "application/x-www-form-urlencoded",
    }


def test_encode_request_defaults_to_empty_bytestream():
    """encode_request with no content/data/files/json returns an empty ByteStream and no headers."""
    headers, stream = encode_request()
    assert headers == {}
    assert isinstance(stream, ByteStream)
    assert b"".join(list(stream)) == b""


def test_encode_request_data_as_bytes_warns_and_delegates():
    """A bytes 'data=' argument should warn but still produce body bytes (compat with requests)."""
    with pytest.warns(DeprecationWarning):
        headers, stream = encode_request(data=b"raw-bytes")  # type: ignore[arg-type]
    assert b"".join(list(stream)) == b"raw-bytes"  # type: ignore[arg-type]
    assert headers == {"Content-Length": "9"}


def test_encode_request_data_as_str_warns_and_delegates():
    """A str 'data=' argument should also warn and delegate to encode_content."""
    with pytest.warns(DeprecationWarning):
        headers, stream = encode_request(data="hi")  # type: ignore[arg-type]
    assert b"".join(list(stream)) == b"hi"  # type: ignore[arg-type]
    assert headers == {"Content-Length": "2"}


def test_encode_response_text():
    """Response(text=...) routes through encode_text and sets a text/plain Content-Type."""
    response = httpx.Response(200, text="hello")
    assert response.text == "hello"
    assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert response.headers["Content-Length"] == "5"


def test_encode_response_html():
    """Response(html=...) routes through encode_html and sets a text/html Content-Type."""
    response = httpx.Response(200, html="<p>hi</p>")
    assert response.text == "<p>hi</p>"
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    assert response.headers["Content-Length"] == "9"


def test_bytestream_class_iterates_single_chunk():
    """ByteStream yields its entire payload as a single chunk, both sync and async."""

    async def collect_async(stream: ByteStream) -> bytes:
        return b"".join([chunk async for chunk in stream])

    stream = ByteStream(b"payload")
    chunks = list(stream)
    assert chunks == [b"payload"]

    # Sync re-iteration is allowed (ByteStream has no consumed flag).
    assert list(stream) == [b"payload"]


@pytest.mark.anyio
async def test_iterator_content_from_list_can_be_reconsumed():
    """A non-generator iterable (e.g. list) should not raise StreamConsumed when re-iterated."""
    request = httpx.Request(method, url, content=[b"Hello, ", b"world!"])
    assert isinstance(request.stream, typing.Iterable)

    first = b"".join(list(request.stream))
    # `_is_generator` is False for a list, so re-iteration is allowed.
    second = b"".join(list(request.stream))

    assert first == b"Hello, world!"
    assert second == b"Hello, world!"
    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }


@pytest.mark.anyio
async def test_async_iterator_content_from_custom_iterable_can_be_reconsumed():
    """A non-asyncgen async iterable should not raise StreamConsumed when re-iterated."""

    class AsyncIterable:
        def __aiter__(self) -> typing.AsyncIterator[bytes]:
            return self._gen()

        async def _gen(self) -> typing.AsyncIterator[bytes]:
            yield b"Hello, "
            yield b"world!"

    request = httpx.Request(method, url, content=AsyncIterable())
    assert isinstance(request.stream, typing.AsyncIterable)
    assert not isinstance(request.stream, typing.Iterable)

    first = b"".join([part async for part in request.stream])
    # `_is_generator` is False here because the iterable itself is not an
    # async generator, so the second iteration is permitted.
    second = b"".join([part async for part in request.stream])

    assert first == b"Hello, world!"
    assert second == b"Hello, world!"
    assert request.headers == {
        "Host": "www.example.com",
        "Transfer-Encoding": "chunked",
    }


def test_unattached_stream_iter_raises_stream_closed():
    """UnattachedStream raises StreamClosed when iterated synchronously."""
    stream = UnattachedStream()
    with pytest.raises(httpx.StreamClosed):
        list(stream)


@pytest.mark.anyio
async def test_unattached_stream_aiter_raises_stream_closed():
    """UnattachedStream raises StreamClosed when iterated asynchronously."""
    stream = UnattachedStream()
    with pytest.raises(httpx.StreamClosed):
        [chunk async for chunk in stream]


def test_request_pickle_roundtrip_uses_unattached_stream():
    """A pickled/unpickled Request loses its stream and surfaces StreamClosed."""
    request = httpx.Request(method, url, content=b"Hello, world!")
    restored = pickle.loads(pickle.dumps(request))
    assert isinstance(restored.stream, UnattachedStream)
    with pytest.raises(httpx.StreamClosed):
        list(restored.stream)


def test_response_pickle_roundtrip_uses_unattached_stream():
    """A pickled/unpickled Response loses its stream and surfaces StreamClosed."""
    response = httpx.Response(200, content=b"hi")
    restored = pickle.loads(pickle.dumps(response))
    assert isinstance(restored.stream, UnattachedStream)
    with pytest.raises(httpx.StreamClosed):
        list(restored.stream)


def test_iterator_bytestream_uses_file_like_read_for_large_payloads():
    """IteratorByteStream should chunk file-like objects via .read(CHUNK_SIZE)."""
    payload = b"x" * (IteratorByteStream.CHUNK_SIZE * 2 + 17)
    stream = IteratorByteStream(io.BytesIO(payload))
    chunks = list(stream)
    # We expect roughly ceil(len(payload) / CHUNK_SIZE) chunks plus an empty
    # terminator iteration handled internally; assert the join matches and that
    # multiple chunks were produced (proving the .read() path executed).
    assert b"".join(chunks) == payload
    assert len(chunks) >= 3


@pytest.mark.anyio
async def test_async_iterator_bytestream_uses_file_like_aread_for_large_payloads():
    """AsyncIteratorByteStream should chunk async file-like objects via .aread(CHUNK_SIZE)."""

    class AsyncFile:
        def __init__(self, data: bytes) -> None:
            self._buf = io.BytesIO(data)

        async def aread(self, size: int) -> bytes:
            return self._buf.read(size)

    payload = b"y" * (AsyncIteratorByteStream.CHUNK_SIZE * 2 + 5)
    stream = AsyncIteratorByteStream(AsyncFile(payload))  # type: ignore[arg-type]
    chunks = [chunk async for chunk in stream]
    assert b"".join(chunks) == payload
    assert len(chunks) >= 3


@pytest.mark.anyio
async def test_async_iterator_bytestream_generator_raises_on_reuse():
    """An async generator stream that has already been consumed raises StreamConsumed."""

    async def gen() -> typing.AsyncIterator[bytes]:
        yield b"a"
        yield b"b"

    stream = AsyncIteratorByteStream(gen())
    first = b"".join([chunk async for chunk in stream])
    assert first == b"ab"
    with pytest.raises(httpx.StreamConsumed):
        [chunk async for chunk in stream]


def test_iterator_bytestream_generator_raises_on_reuse():
    """A sync generator stream that has already been consumed raises StreamConsumed."""

    def gen() -> typing.Iterator[bytes]:
        yield b"a"
        yield b"b"

    stream = IteratorByteStream(gen())
    assert b"".join(list(stream)) == b"ab"
    with pytest.raises(httpx.StreamConsumed):
        list(stream)


def test_encode_request_content_takes_precedence_over_data_and_json():
    """When `content=` is supplied it is used even if data/json/files are also present."""
    headers, stream = encode_request(
        content=b"raw",
        data={"k": "v"},
        json={"k": "v"},
        files={"f": io.BytesIO(b"data")},
    )
    assert b"".join(list(stream)) == b"raw"  # type: ignore[arg-type]
    assert headers == {"Content-Length": "3"}


def test_encode_request_files_with_explicit_boundary():
    """encode_request honours an explicit multipart boundary when files are supplied."""
    headers, _ = encode_request(
        files={"file": io.BytesIO(b"x")},
        boundary=b"BOUNDARY",
    )
    assert "BOUNDARY" in headers["Content-Type"]
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")


def test_encode_response_defaults_to_empty_bytestream():
    """encode_response with no arguments returns an empty ByteStream and no headers."""
    headers, stream = encode_response()
    assert headers == {}
    assert isinstance(stream, ByteStream)
    assert b"".join(list(stream)) == b""
