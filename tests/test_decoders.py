from __future__ import annotations

import io
import typing
import zlib

import chardet
import pytest
import zstandard as zstd

import httpx
from httpx._decoders import (
    BrotliDecoder,
    ByteChunker,
    ContentDecoder,
    DeflateDecoder,
    GZipDecoder,
    IdentityDecoder,
    LineDecoder,
    MultiDecoder,
    TextChunker,
    TextDecoder,
    ZStandardDecoder,
)


def test_deflate():
    """
    Deflate encoding may use either 'zlib' or 'deflate' in the wild.

    https://stackoverflow.com/questions/1838699/how-can-i-decompress-a-gzip-stream-with-zlib#answer-22311297
    """
    body = b"test 123"
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    compressed_body = compressor.compress(body) + compressor.flush()

    headers = [(b"Content-Encoding", b"deflate")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_zlib():
    """
    Deflate encoding may use either 'zlib' or 'deflate' in the wild.

    https://stackoverflow.com/questions/1838699/how-can-i-decompress-a-gzip-stream-with-zlib#answer-22311297
    """
    body = b"test 123"
    compressed_body = zlib.compress(body)

    headers = [(b"Content-Encoding", b"deflate")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_gzip():
    body = b"test 123"
    compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    compressed_body = compressor.compress(body) + compressor.flush()

    headers = [(b"Content-Encoding", b"gzip")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_brotli():
    body = b"test 123"
    compressed_body = b"\x8b\x03\x80test 123\x03"

    headers = [(b"Content-Encoding", b"br")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_zstd():
    body = b"test 123"
    compressed_body = zstd.compress(body)

    headers = [(b"Content-Encoding", b"zstd")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_zstd_decoding_error():
    compressed_body = "this_is_not_zstd_compressed_data"

    headers = [(b"Content-Encoding", b"zstd")]
    with pytest.raises(httpx.DecodingError):
        httpx.Response(
            200,
            headers=headers,
            content=compressed_body,
        )


def test_zstd_empty():
    headers = [(b"Content-Encoding", b"zstd")]
    response = httpx.Response(200, headers=headers, content=b"")
    assert response.content == b""


def test_zstd_truncated():
    body = b"test 123"
    compressed_body = zstd.compress(body)

    headers = [(b"Content-Encoding", b"zstd")]
    with pytest.raises(httpx.DecodingError):
        httpx.Response(
            200,
            headers=headers,
            content=compressed_body[1:3],
        )


def test_zstd_multiframe():
    # test inspired by urllib3 test suite
    data = (
        # Zstandard frame
        zstd.compress(b"foo")
        # skippable frame (must be ignored)
        + bytes.fromhex(
            "50 2A 4D 18"  # Magic_Number (little-endian)
            "07 00 00 00"  # Frame_Size (little-endian)
            "00 00 00 00 00 00 00"  # User_Data
        )
        # Zstandard frame
        + zstd.compress(b"bar")
    )
    compressed_body = io.BytesIO(data)

    headers = [(b"Content-Encoding", b"zstd")]
    response = httpx.Response(200, headers=headers, content=compressed_body)
    response.read()
    assert response.content == b"foobar"


def test_multi():
    body = b"test 123"

    deflate_compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    compressed_body = deflate_compressor.compress(body) + deflate_compressor.flush()

    gzip_compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    compressed_body = (
        gzip_compressor.compress(compressed_body) + gzip_compressor.flush()
    )

    headers = [(b"Content-Encoding", b"deflate, gzip")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


def test_multi_with_identity():
    body = b"test 123"
    compressed_body = b"\x8b\x03\x80test 123\x03"

    headers = [(b"Content-Encoding", b"br, identity")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body

    headers = [(b"Content-Encoding", b"identity, br")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compressed_body,
    )
    assert response.content == body


@pytest.mark.anyio
async def test_streaming():
    body = b"test 123"
    compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)

    async def compress(body: bytes) -> typing.AsyncIterator[bytes]:
        yield compressor.compress(body)
        yield compressor.flush()

    headers = [(b"Content-Encoding", b"gzip")]
    response = httpx.Response(
        200,
        headers=headers,
        content=compress(body),
    )
    assert not hasattr(response, "body")
    assert await response.aread() == body


@pytest.mark.parametrize("header_value", (b"deflate", b"gzip", b"br", b"identity"))
def test_empty_content(header_value):
    headers = [(b"Content-Encoding", header_value)]
    response = httpx.Response(
        200,
        headers=headers,
        content=b"",
    )
    assert response.content == b""


@pytest.mark.parametrize("header_value", (b"deflate", b"gzip", b"br", b"identity"))
def test_decoders_empty_cases(header_value):
    headers = [(b"Content-Encoding", header_value)]
    response = httpx.Response(content=b"", status_code=200, headers=headers)
    assert response.read() == b""


@pytest.mark.parametrize("header_value", (b"deflate", b"gzip", b"br"))
def test_decoding_errors(header_value):
    headers = [(b"Content-Encoding", header_value)]
    compressed_body = b"invalid"
    with pytest.raises(httpx.DecodingError):
        request = httpx.Request("GET", "https://example.org")
        httpx.Response(200, headers=headers, content=compressed_body, request=request)

    with pytest.raises(httpx.DecodingError):
        httpx.Response(200, headers=headers, content=compressed_body)


@pytest.mark.parametrize(
    ["data", "encoding"],
    [
        ((b"Hello,", b" world!"), "ascii"),
        ((b"\xe3\x83", b"\x88\xe3\x83\xa9", b"\xe3", b"\x83\x99\xe3\x83\xab"), "utf-8"),
        ((b"Euro character: \x88! abcdefghijklmnopqrstuvwxyz", b""), "cp1252"),
        ((b"Accented: \xd6sterreich abcdefghijklmnopqrstuvwxyz", b""), "iso-8859-1"),
    ],
)
@pytest.mark.anyio
async def test_text_decoder_with_autodetect(data, encoding):
    async def iterator() -> typing.AsyncIterator[bytes]:
        nonlocal data
        for chunk in data:
            yield chunk

    def autodetect(content):
        return chardet.detect(content).get("encoding")

    # Accessing `.text` on a read response.
    response = httpx.Response(200, content=iterator(), default_encoding=autodetect)
    await response.aread()
    assert response.text == (b"".join(data)).decode(encoding)

    # Streaming `.aiter_text` iteratively.
    # Note that if we streamed the text *without* having read it first, then
    # we won't get a `charset_normalizer` guess, and will instead always rely
    # on utf-8 if no charset is specified.
    text = "".join([part async for part in response.aiter_text()])
    assert text == (b"".join(data)).decode(encoding)


@pytest.mark.anyio
async def test_text_decoder_known_encoding():
    async def iterator() -> typing.AsyncIterator[bytes]:
        yield b"\x83g"
        yield b"\x83"
        yield b"\x89\x83x\x83\x8b"

    response = httpx.Response(
        200,
        headers=[(b"Content-Type", b"text/html; charset=shift-jis")],
        content=iterator(),
    )

    await response.aread()
    assert "".join(response.text) == "トラベル"


def test_text_decoder_empty_cases():
    response = httpx.Response(200, content=b"")
    assert response.text == ""

    response = httpx.Response(200, content=[b""])
    response.read()
    assert response.text == ""


@pytest.mark.parametrize(
    ["data", "expected"],
    [((b"Hello,", b" world!"), ["Hello,", " world!"])],
)
def test_streaming_text_decoder(
    data: typing.Iterable[bytes], expected: list[str]
) -> None:
    response = httpx.Response(200, content=iter(data))
    assert list(response.iter_text()) == expected


def test_line_decoder_nl():
    response = httpx.Response(200, content=[b""])
    assert list(response.iter_lines()) == []

    response = httpx.Response(200, content=[b"", b"a\n\nb\nc"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    # Issue #1033
    response = httpx.Response(
        200, content=[b"", b"12345\n", b"foo ", b"bar ", b"baz\n"]
    )
    assert list(response.iter_lines()) == ["12345", "foo bar baz"]


def test_line_decoder_cr():
    response = httpx.Response(200, content=[b"", b"a\r\rb\rc"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    response = httpx.Response(200, content=[b"", b"a\r\rb\rc\r"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    # Issue #1033
    response = httpx.Response(
        200, content=[b"", b"12345\r", b"foo ", b"bar ", b"baz\r"]
    )
    assert list(response.iter_lines()) == ["12345", "foo bar baz"]


def test_line_decoder_crnl():
    response = httpx.Response(200, content=[b"", b"a\r\n\r\nb\r\nc"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    response = httpx.Response(200, content=[b"", b"a\r\n\r\nb\r\nc\r\n"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    response = httpx.Response(200, content=[b"", b"a\r", b"\n\r\nb\r\nc"])
    assert list(response.iter_lines()) == ["a", "", "b", "c"]

    # Issue #1033
    response = httpx.Response(200, content=[b"", b"12345\r\n", b"foo bar baz\r\n"])
    assert list(response.iter_lines()) == ["12345", "foo bar baz"]


def test_invalid_content_encoding_header():
    headers = [(b"Content-Encoding", b"invalid-header")]
    body = b"test 123"

    response = httpx.Response(
        200,
        headers=headers,
        content=body,
    )
    assert response.content == body


# ---------------------------------------------------------------------------
# Direct unit tests for the decoder helper classes in httpx._decoders
# ---------------------------------------------------------------------------


def test_identity_decoder_unit():
    decoder = IdentityDecoder()
    assert decoder.decode(b"abc") == b"abc"
    assert decoder.decode(b"") == b""
    assert decoder.flush() == b""


def test_gzip_decoder_unit_flush_after_full_payload():
    body = b"the quick brown fox"
    compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    compressed = compressor.compress(body) + compressor.flush()

    decoder = GZipDecoder()
    assert decoder.decode(compressed) == body
    # flush() on the GZip decoder should be safe to call and return empty bytes
    # because the decompressor has already consumed the entire payload.
    assert decoder.flush() == b""


def test_gzip_decoder_unit_invalid_payload_raises_decoding_error():
    decoder = GZipDecoder()
    with pytest.raises(httpx.DecodingError):
        decoder.decode(b"this-is-not-gzip-data")


def test_deflate_decoder_unit_zlib_then_fallback_to_raw_deflate():
    body = b"hello deflate"

    # Raw deflate stream (no zlib header). The DeflateDecoder must first try
    # zlib decoding and, when that fails on the first call, transparently
    # retry with raw deflate (negative MAX_WBITS).
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    raw_deflate = compressor.compress(body) + compressor.flush()

    decoder = DeflateDecoder()
    assert decoder.first_attempt is True
    assert decoder.decode(raw_deflate) == body
    assert decoder.first_attempt is False
    assert decoder.flush() == b""


def test_deflate_decoder_unit_decode_error_after_first_attempt():
    # First successfully decode a valid raw-deflate chunk so that the
    # `first_attempt` flag flips to False, then feed garbage on the
    # following call. The decoder must surface the failure as DecodingError
    # rather than recursing back into the zlib retry branch.
    body = b"valid raw deflate"
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    raw_deflate_prefix = compressor.compress(body)

    decoder = DeflateDecoder()
    decoder.decode(raw_deflate_prefix)
    assert decoder.first_attempt is False
    with pytest.raises(httpx.DecodingError):
        decoder.decode(b"\xff\xff\xff\xff garbage bytes")


def test_deflate_decoder_unit_accepts_zlib_stream():
    body = b"zlib framed"
    compressed = zlib.compress(body)
    decoder = DeflateDecoder()
    assert decoder.decode(compressed) == body
    assert decoder.flush() == b""


def test_brotli_decoder_unit_empty_decode_short_circuits():
    decoder = BrotliDecoder()
    # An empty decode call should not mark seen_data, and flush() must
    # therefore return an empty byte string without invoking the underlying
    # brotli decompressor's finish/finalize.
    assert decoder.decode(b"") == b""
    assert decoder.seen_data is False
    assert decoder.flush() == b""


def test_brotli_decoder_unit_decoding_error():
    decoder = BrotliDecoder()
    with pytest.raises(httpx.DecodingError):
        decoder.decode(b"\x00not-brotli-data\xff")


def test_zstandard_decoder_unit_decode_and_flush():
    body = b"zstd payload"
    compressed = zstd.compress(body)
    decoder = ZStandardDecoder()
    # seen_data flips to True the first time decode() is invoked.
    assert decoder.seen_data is False
    out = decoder.decode(compressed)
    assert out == body
    assert decoder.seen_data is True
    # flush() should return empty bytes; the decompressor has reached EOF.
    assert decoder.flush() == b""


def test_zstandard_decoder_unit_flush_without_data_is_empty():
    decoder = ZStandardDecoder()
    assert decoder.flush() == b""


def test_zstandard_decoder_unit_invalid_data_raises():
    decoder = ZStandardDecoder()
    with pytest.raises(httpx.DecodingError):
        decoder.decode(b"clearly-not-a-zstd-frame")


def test_multi_decoder_unit_flush_propagates_through_children():
    """MultiDecoder.flush() must call decode(b'') + flush() on every child."""

    class _RecordingDecoder(ContentDecoder):
        def __init__(self, name: str, tail: bytes) -> None:
            self.name = name
            self.tail = tail
            self.decoded: list[bytes] = []
            self.flushed = False

        def decode(self, data: bytes) -> bytes:
            self.decoded.append(data)
            return data

        def flush(self) -> bytes:
            self.flushed = True
            return self.tail

    first = _RecordingDecoder("first", b"-A")
    second = _RecordingDecoder("second", b"-B")
    multi = MultiDecoder(children=[first, second])

    # Encoding order is [first, second]; decode order is reversed.
    # decode(b"x") -> second.decode(b"x") -> first.decode(b"x")
    assert multi.decode(b"x") == b"x"
    assert second.decoded == [b"x"]
    assert first.decoded == [b"x"]

    # flush() must walk children in decode order and accumulate tails.
    # iteration 1 (second): decode(b"") + flush() -> b"" + b"-B" -> b"-B"
    # iteration 2 (first):  decode(b"-B") + flush() -> b"-B" + b"-A" -> b"-B-A"
    assert multi.flush() == b"-B-A"
    assert first.flushed is True
    assert second.flushed is True


# ---------------------------------------------------------------------------
# ByteChunker / TextChunker direct tests
# ---------------------------------------------------------------------------


def test_byte_chunker_no_chunk_size_passthrough():
    chunker = ByteChunker()
    assert chunker.decode(b"hello") == [b"hello"]
    # Empty input with no chunk size should not produce a chunk.
    assert chunker.decode(b"") == []
    assert chunker.flush() == []


def test_byte_chunker_buffers_until_chunk_size_reached():
    chunker = ByteChunker(chunk_size=4)
    # 3 bytes < chunk_size -> buffered, nothing emitted.
    assert chunker.decode(b"abc") == []
    # Total is now 6 bytes; one full chunk of 4 emitted, 2 carried over.
    assert chunker.decode(b"de") == [b"abcd"]
    # Flush should drain the remaining 2 buffered bytes.
    assert chunker.flush() == [b"e"]


def test_byte_chunker_exact_multiple_of_chunk_size():
    chunker = ByteChunker(chunk_size=3)
    # An input that lands exactly on a chunk boundary must clear the buffer.
    assert chunker.decode(b"abcdef") == [b"abc", b"def"]
    # Nothing should remain to be flushed.
    assert chunker.flush() == []


def test_byte_chunker_flush_with_empty_buffer_returns_empty_list():
    chunker = ByteChunker(chunk_size=8)
    assert chunker.flush() == []


def test_text_chunker_no_chunk_size_passthrough():
    chunker = TextChunker()
    assert chunker.decode("hello") == ["hello"]
    assert chunker.decode("") == []
    assert chunker.flush() == []


def test_text_chunker_buffers_until_chunk_size_reached():
    chunker = TextChunker(chunk_size=4)
    assert chunker.decode("ab") == []
    assert chunker.decode("cdef") == ["abcd"]
    assert chunker.flush() == ["ef"]


def test_text_chunker_exact_multiple_of_chunk_size():
    chunker = TextChunker(chunk_size=2)
    assert chunker.decode("abcd") == ["ab", "cd"]
    assert chunker.flush() == []


# ---------------------------------------------------------------------------
# TextDecoder direct tests
# ---------------------------------------------------------------------------


def test_text_decoder_unit_handles_split_multibyte_sequence():
    decoder = TextDecoder(encoding="utf-8")
    # The multi-byte UTF-8 sequence for "é" is split across two decode calls;
    # the incremental decoder must buffer the partial byte and emit only the
    # safely-decodable portion of the input on each call.
    assert decoder.decode(b"caf\xc3") == "caf"
    assert decoder.decode(b"\xa9!") == "é!"
    assert decoder.flush() == ""


def test_text_decoder_unit_flush_emits_replacement_for_incomplete_sequence():
    decoder = TextDecoder(encoding="utf-8")
    # Feed an incomplete multibyte prefix and never finish it. With
    # errors="replace", flush() must emit the U+FFFD replacement char.
    assert decoder.decode(b"hi\xc3") == "hi"
    assert decoder.flush() == "�"


# ---------------------------------------------------------------------------
# LineDecoder direct tests
# ---------------------------------------------------------------------------


def test_line_decoder_unit_buffers_partial_line():
    decoder = LineDecoder()
    # A line with no trailing newline must be buffered and produce no output.
    assert decoder.decode("partial") == []
    # Continuation still has no newline; buffer grows.
    assert decoder.decode(" line") == []
    # flush() emits the accumulated buffer as a single line.
    assert decoder.flush() == ["partial line"]


def test_line_decoder_unit_trailing_cr_state_is_carried_across_calls():
    decoder = LineDecoder()
    # Trailing CR must be held back until the next chunk so that a CRLF
    # spanning a chunk boundary is not interpreted as two separate newlines.
    # The trailing CR is stripped from the input; "first" has no newline so
    # it is buffered (no lines emitted).
    assert decoder.decode("first\r") == []
    assert decoder.trailing_cr is True
    # The next chunk arriving with a leading LF re-prepends the CR; the
    # combined buffer + "\r\nsecond\n" yields the two completed lines.
    assert decoder.decode("\nsecond\n") == ["first", "second"]
    assert decoder.trailing_cr is False
    assert decoder.flush() == []


def test_line_decoder_unit_flush_with_only_trailing_cr():
    decoder = LineDecoder()
    decoder.decode("a\n")
    # Feed an isolated CR; the decoder strips it and records trailing_cr.
    # Buffer is empty (nothing preceded the CR in this chunk).
    decoder.decode("\r")
    assert decoder.trailing_cr is True
    assert decoder.buffer == []
    # flush() must still emit a line for the dangling CR and reset state,
    # even though the buffer is empty.
    assert decoder.flush() == [""]
    assert decoder.trailing_cr is False
    assert decoder.buffer == []


def test_line_decoder_unit_flush_with_empty_state_returns_empty():
    decoder = LineDecoder()
    assert decoder.flush() == []


# ---------------------------------------------------------------------------
# End-to-end iter_bytes/iter_text/iter_raw exercising the chunker integration
# ---------------------------------------------------------------------------


def test_response_iter_bytes_with_chunk_size_splits_decoded_content():
    body = b"abcdefghij"  # 10 bytes
    compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    compressed = compressor.compress(body) + compressor.flush()

    response = httpx.Response(
        200,
        headers=[(b"Content-Encoding", b"gzip")],
        content=compressed,
    )
    # When the response is read into _content already, iter_bytes yields
    # fixed-size slices from that buffer.
    chunks = list(response.iter_bytes(chunk_size=3))
    assert b"".join(chunks) == body
    assert chunks == [b"abc", b"def", b"ghi", b"j"]


def test_response_iter_bytes_streaming_with_chunk_size():
    body = b"0123456789abcdef"

    def stream() -> typing.Iterator[bytes]:
        yield body[:5]
        yield body[5:11]
        yield body[11:]

    response = httpx.Response(200, content=stream())
    chunks = list(response.iter_bytes(chunk_size=4))
    assert b"".join(chunks) == body
    # All but possibly the last chunk should match the requested chunk size.
    for chunk in chunks[:-1]:
        assert len(chunk) == 4


def test_response_iter_text_with_chunk_size():
    response = httpx.Response(200, content=b"Hello, world!")
    chunks = list(response.iter_text(chunk_size=5))
    assert "".join(chunks) == "Hello, world!"
    assert chunks[0] == "Hello"


def test_response_iter_raw_with_chunk_size_exercises_byte_chunker_flush():
    def stream() -> typing.Iterator[bytes]:
        yield b"hello "
        yield b"world!"

    response = httpx.Response(200, content=stream())
    chunks = list(response.iter_raw(chunk_size=5))
    # Reassembly preserves the original bytes regardless of chunk boundaries.
    assert b"".join(chunks) == b"hello world!"
    # iter_raw with chunk_size=5 over 12 bytes should yield at least one chunk
    # from the ByteChunker.flush() path (the trailing 2-byte remainder).
    assert any(len(chunk) < 5 for chunk in chunks)


def test_response_iter_lines_handles_split_cr_between_chunks():
    """Trailing CR carried across chunks must produce the expected line set."""
    response = httpx.Response(
        200,
        content=[b"first\r", b"\nsecond\nthird"],
    )
    assert list(response.iter_lines()) == ["first", "second", "third"]
