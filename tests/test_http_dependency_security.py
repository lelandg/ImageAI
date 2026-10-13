"""Offline regression checks for the HTTP dependencies used by ImageAI.

Exercise malformed protocol input without sockets, credentials, large allocations,
or an unbounded loop. These test behavior, not just installed version strings.
"""
import io
import sys
import zlib
from http.client import HTTPResponse as StdlibResponse
from types import SimpleNamespace

import pytest
from multidict import CIMultiDict, MultiDict
from urllib3.exceptions import ProtocolError
from urllib3.response import DeflateDecoder, HTTPResponse


class BoundedLineStream(io.BytesIO):
    """Fail safely if a vulnerable parser attempts an unbounded body-line read."""

    checking_body = False

    def readline(self, size=-1):
        if self.checking_body:
            # Allow short buffered lines so the old parser reaches trailers
            # and legitimate controls without ever doing an unbounded read.
            if size < 0:
                end = self.getvalue().find(b"\n", self.tell())
                assert 0 <= end - self.tell() < 65537, "HTTP body line read must be bounded"
            else:
                assert 0 < size <= 65537, "HTTP body line read must be bounded"
        return super().readline(size)


def chunked_response(body):
    stream = BoundedLineStream(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + body
    )
    parsed = StdlibResponse(SimpleNamespace(makefile=lambda *args: stream), method="GET")
    parsed.begin()
    stream.checking_body = True
    return HTTPResponse(
        body=parsed, headers=parsed.headers.items(), original_response=parsed,
        preload_content=False,
    )


@pytest.mark.parametrize("body", [
    b"f" * 70000,
    b"0\r\nX-Trailer: " + b"a" * 70000,
], ids=["unterminated-size", "oversized-trailer"])
def test_chunk_metadata_is_rejected_with_bounded_reads(body):
    """SNYK-PYTHON-URLLIB3-20302846: size and trailer lines are bounded."""
    with (chunked_response(body) as response,
          pytest.raises(ProtocolError, match="maximum allowed length")):
        list(response.stream(8192))


def test_large_legitimate_chunk_body_still_streams():
    data = b"image bytes\x00" * 12000
    body = f"{len(data):x}\r\n".encode() + data + b"\r\n0\r\n\r\n"
    with chunked_response(body) as response:
        assert b"".join(response.stream(8192)) == data


@pytest.mark.parametrize("wbits", [zlib.MAX_WBITS, -zlib.MAX_WBITS])
@pytest.mark.parametrize("trailer", [b"", b"untrusted trailing data"])
def test_deflate_decoder_finishes_after_eof(wbits, trailer):
    """SNYK-PYTHON-URLLIB3-20302845: trailing bytes cannot stall draining."""
    expected = b"response body" * 20
    compressor = zlib.compressobj(wbits=wbits)
    wire = compressor.compress(expected) + compressor.flush() + trailer
    decoder = DeflateDecoder()
    decoded = decoder.decompress(wire, max_length=50)
    for _ in range(20):
        if not decoder.has_unconsumed_tail:
            break
        decoded += decoder.decompress(b"", max_length=50)
    assert not decoder.has_unconsumed_tail, "decoder stalled after EOF"
    assert decoded + decoder.flush() == expected


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython refcounts")
@pytest.mark.parametrize("mapping_type", [MultiDict, CIMultiDict])
@pytest.mark.parametrize("operation", ["union", "difference"])
def test_multidict_items_operations_release_references(mapping_type, operation):
    """SNYK-PYTHON-MULTIDICT-20510280: repeated set operations do not leak."""
    class Value:
        pass

    value = Value()
    mapping = mapping_type({"header": value})
    operand = {("header", value)}
    before = sys.getrefcount(value)
    for _ in range(20):
        if operation == "union":
            result = operand | mapping.items()
            assert result == operand
        else:
            result = mapping.items() - operand
            assert result == set()
        del result
    assert sys.getrefcount(value) == before
