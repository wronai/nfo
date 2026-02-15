"""Tests for nfo.extractors — metadata extraction for binary/large data."""

import hashlib
import io
import struct

import pytest

from nfo.extractors import (
    MAGIC_SIGNATURES,
    detect_format,
    extract_binary_meta,
    extract_file_meta,
    extract_image_meta,
    extract_meta,
    extract_numpy_meta,
    extract_wav_meta,
    register_extractor,
    unregister_all_extractors,
)


# ---------------------------------------------------------------------------
# Helpers — minimal valid binary headers
# ---------------------------------------------------------------------------

def _make_png(width: int = 100, height: int = 200) -> bytes:
    """Build minimal PNG header (first 24 bytes)."""
    header = b"\x89PNG\r\n\x1a\n"  # 8 bytes magic
    # IHDR chunk: length(4) + "IHDR"(4) + width(4) + height(4)
    ihdr = b"\x00\x00\x00\r" + b"IHDR"
    ihdr += struct.pack(">I", width) + struct.pack(">I", height)
    ihdr += b"\x08\x02\x00\x00\x00"  # bit depth, color type, etc.
    return header + ihdr


def _make_jpeg(width: int = 640, height: int = 480) -> bytes:
    """Build minimal JPEG with SOF0 marker."""
    data = b"\xff\xd8\xff"  # SOI + APP0 marker byte
    data += b"\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    # SOF0 marker
    data += b"\xff\xc0"
    data += b"\x00\x11"  # length
    data += b"\x08"  # precision
    data += struct.pack(">H", height) + struct.pack(">H", width)
    data += b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    return data


def _make_bmp(width: int = 320, height: int = 240) -> bytes:
    """Build minimal BMP header."""
    header = b"BM"
    header += b"\x00" * 16  # file size + reserved + offset (padding)
    header += struct.pack("<I", width) + struct.pack("<I", height)
    return header


def _make_wav(channels: int = 2, sample_rate: int = 44100, bits: int = 16, data_size: int = 88200) -> bytes:
    """Build minimal WAV header (44 bytes RIFF/WAVE)."""
    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)  # chunk size
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)  # subchunk1 size
    header += struct.pack("<H", 1)  # PCM
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", sample_rate * channels * bits // 8)  # byte rate
    header += struct.pack("<H", channels * bits // 8)  # block align
    header += struct.pack("<H", bits)
    header += b"data"
    header += struct.pack("<I", data_size)
    return header


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

class TestDetectFormat:

    def test_png(self):
        assert detect_format(_make_png()) == "PNG"

    def test_jpeg(self):
        assert detect_format(_make_jpeg()) == "JPEG"

    def test_bmp(self):
        assert detect_format(_make_bmp()) == "BMP"

    def test_gzip(self):
        assert detect_format(b"\x1f\x8b\x08\x00") == "GZIP"

    def test_pdf(self):
        assert detect_format(b"%PDF-1.5 ...") == "PDF"

    def test_unknown(self):
        assert detect_format(b"\x00\x01\x02\x03") is None

    def test_empty(self):
        assert detect_format(b"") is None

    def test_wav(self):
        assert detect_format(_make_wav()) == "RIFF/WAV/AVI"


# ---------------------------------------------------------------------------
# extract_image_meta
# ---------------------------------------------------------------------------

class TestExtractImageMeta:

    def test_png_dimensions(self):
        meta = extract_image_meta(_make_png(1920, 1080))
        assert meta["type"] == "image"
        assert meta["format"] == "PNG"
        assert meta["width"] == 1920
        assert meta["height"] == 1080
        assert "hash_sha256_prefix" in meta
        assert len(meta["hash_sha256_prefix"]) == 16

    def test_jpeg_dimensions(self):
        meta = extract_image_meta(_make_jpeg(800, 600))
        assert meta["format"] == "JPEG"
        assert meta["width"] == 800
        assert meta["height"] == 600

    def test_bmp_dimensions(self):
        meta = extract_image_meta(_make_bmp(320, 240))
        assert meta["format"] == "BMP"
        assert meta["width"] == 320
        assert meta["height"] == 240

    def test_size_bytes(self):
        data = _make_png()
        meta = extract_image_meta(data)
        assert meta["size_bytes"] == len(data)


# ---------------------------------------------------------------------------
# extract_binary_meta
# ---------------------------------------------------------------------------

class TestExtractBinaryMeta:

    def test_basic_fields(self):
        data = b"hello world"
        meta = extract_binary_meta(data)
        assert meta["type"] == "binary"
        assert meta["size_bytes"] == len(data)
        assert "entropy" in meta
        assert "hash_sha256_prefix" in meta

    def test_high_entropy_detection(self):
        import os
        random_data = os.urandom(4096)
        meta = extract_binary_meta(random_data)
        assert meta["entropy"] > 7.0
        # Truly random data should have very high entropy
        assert meta["is_compressed_or_encrypted"] is True

    def test_low_entropy(self):
        data = b"\x00" * 1000
        meta = extract_binary_meta(data)
        assert meta["entropy"] == 0.0
        assert meta["is_compressed_or_encrypted"] is False

    def test_empty_bytes(self):
        meta = extract_binary_meta(b"")
        assert meta["size_bytes"] == 0
        assert "entropy" not in meta

    def test_known_format_detection(self):
        data = b"%PDF-1.5 rest of file..."
        meta = extract_binary_meta(data)
        assert meta["format"] == "PDF"


# ---------------------------------------------------------------------------
# extract_file_meta
# ---------------------------------------------------------------------------

class TestExtractFileMeta:

    def test_bytesio(self):
        f = io.BytesIO(b"hello world")
        f.seek(3)  # set position
        meta = extract_file_meta(f)
        assert meta["type"] == "file_handle"
        assert meta["position"] == 3
        assert meta["size_bytes"] == 11
        # Position should be restored
        assert f.tell() == 3

    def test_stringio(self):
        f = io.StringIO("hello")
        meta = extract_file_meta(f)
        assert meta["type"] == "file_handle"
        assert meta["size_bytes"] == 5

    def test_real_file(self, tmp_path):
        fp = tmp_path / "test.bin"
        fp.write_bytes(b"x" * 100)
        with open(fp, "rb") as f:
            meta = extract_file_meta(f)
        assert meta["type"] == "file_handle"
        assert meta["name"] is not None
        assert meta["mode"] == "rb"
        assert meta["size_bytes"] == 100


# ---------------------------------------------------------------------------
# extract_wav_meta
# ---------------------------------------------------------------------------

class TestExtractWavMeta:

    def test_stereo_44100(self):
        data = _make_wav(channels=2, sample_rate=44100, bits=16, data_size=88200)
        meta = extract_wav_meta(data)
        assert meta["type"] == "audio"
        assert meta["format"] == "WAV"
        assert meta["channels"] == 2
        assert meta["sample_rate"] == 44100
        assert meta["bits_per_sample"] == 16
        assert abs(meta["duration_seconds"] - 0.5) < 0.01

    def test_mono_16000(self):
        data = _make_wav(channels=1, sample_rate=16000, bits=16, data_size=32000)
        meta = extract_wav_meta(data)
        assert meta["channels"] == 1
        assert meta["sample_rate"] == 16000
        assert abs(meta["duration_seconds"] - 1.0) < 0.01


# ---------------------------------------------------------------------------
# extract_numpy_meta (duck-typed)
# ---------------------------------------------------------------------------

class TestExtractNumpyMeta:

    def test_duck_typed_ndarray(self):
        class FakeArray:
            shape = (32, 3, 224, 224)
            dtype = "float32"
            nbytes = 32 * 3 * 224 * 224 * 4
            size = 32 * 3 * 224 * 224
            def min(self): return 0.0
            def max(self): return 1.0
            def mean(self): return 0.5

        meta = extract_numpy_meta(FakeArray())
        assert meta["type"] == "ndarray"
        assert meta["shape"] == [32, 3, 224, 224]
        assert meta["dtype"] == "float32"
        assert meta["min"] == 0.0
        assert meta["max"] == 1.0
        assert meta["mean"] == 0.5


# ---------------------------------------------------------------------------
# extract_meta (unified entry point)
# ---------------------------------------------------------------------------

class TestExtractMeta:

    def test_png_auto_detected(self):
        meta = extract_meta(_make_png(640, 480))
        assert meta["type"] == "image"
        assert meta["format"] == "PNG"

    def test_wav_auto_detected(self):
        meta = extract_meta(_make_wav())
        assert meta["type"] == "audio"
        assert meta["format"] == "WAV"

    def test_generic_bytes(self):
        meta = extract_meta(b"some random data here")
        assert meta["type"] == "binary"

    def test_memoryview(self):
        meta = extract_meta(memoryview(b"hello"))
        assert meta["type"] == "binary"

    def test_file_like(self):
        meta = extract_meta(io.BytesIO(b"data"))
        assert meta["type"] == "file_handle"

    def test_int_returns_none(self):
        assert extract_meta(42) is None

    def test_string_returns_none(self):
        assert extract_meta("hello") is None

    def test_list_returns_none(self):
        assert extract_meta([1, 2, 3]) is None

    def test_none_returns_none(self):
        assert extract_meta(None) is None


# ---------------------------------------------------------------------------
# Custom extractor registry
# ---------------------------------------------------------------------------

class TestCustomExtractors:

    def setup_method(self):
        unregister_all_extractors()

    def teardown_method(self):
        unregister_all_extractors()

    def test_register_and_use(self):
        class FakeTensor:
            shape = (32, 256)
            dtype = "float16"
            device = "cuda:0"
            requires_grad = True
            def is_cuda(self): return True

        register_extractor(
            lambda v: hasattr(v, "is_cuda") and hasattr(v, "shape"),
            lambda t: {"type": "Tensor", "shape": list(t.shape), "dtype": str(t.dtype)},
        )

        meta = extract_meta(FakeTensor())
        assert meta["type"] == "Tensor"
        assert meta["shape"] == [32, 256]

    def test_custom_takes_priority(self):
        # Custom extractor for bytes should override built-in
        register_extractor(
            lambda v: isinstance(v, bytes),
            lambda v: {"type": "custom_bytes", "len": len(v)},
        )
        meta = extract_meta(b"hello")
        assert meta["type"] == "custom_bytes"
        assert meta["len"] == 5

    def test_failing_check_is_skipped(self):
        register_extractor(
            lambda v: 1 / 0,  # always raises
            lambda v: {"type": "never_reached"},
        )
        # Should fall through to built-in
        meta = extract_meta(b"hello")
        assert meta["type"] == "binary"

    def test_unregister_all(self):
        register_extractor(
            lambda v: isinstance(v, bytes),
            lambda v: {"type": "custom"},
        )
        unregister_all_extractors()
        meta = extract_meta(b"hello")
        assert meta["type"] == "binary"
