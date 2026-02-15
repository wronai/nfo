"""Tests for nfo.meta — ThresholdPolicy."""

import io
import sys

import pytest

from nfo.meta import ThresholdPolicy, sizeof


class TestThresholdPolicy:

    def test_default_thresholds(self):
        p = ThresholdPolicy()
        assert p.max_arg_bytes == 8192
        assert p.max_return_bytes == 8192
        assert p.max_total_bytes == 65536

    def test_small_bytes_below_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        assert p.should_extract_meta(b"hello") is False

    def test_large_bytes_above_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        assert p.should_extract_meta(b"x" * 2000) is True

    def test_small_bytearray_below_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        assert p.should_extract_meta(bytearray(b"hello")) is False

    def test_large_bytearray_above_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        assert p.should_extract_meta(bytearray(2000)) is True

    def test_memoryview_above_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=100)
        mv = memoryview(b"x" * 200)
        assert p.should_extract_meta(mv) is True

    def test_memoryview_below_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        mv = memoryview(b"x" * 10)
        assert p.should_extract_meta(mv) is False

    def test_small_string_below_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=1024)
        assert p.should_extract_meta("short string") is False

    def test_large_string_above_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=100)
        assert p.should_extract_meta("a" * 200) is True

    def test_file_like_always_extracts(self):
        p = ThresholdPolicy()
        f = io.BytesIO(b"data")
        assert p.should_extract_meta(f) is True

    def test_int_never_extracts(self):
        p = ThresholdPolicy(max_arg_bytes=0)
        assert p.should_extract_meta(42) is False

    def test_list_never_extracts(self):
        p = ThresholdPolicy(max_arg_bytes=0)
        assert p.should_extract_meta([1, 2, 3]) is False

    def test_none_never_extracts(self):
        p = ThresholdPolicy()
        assert p.should_extract_meta(None) is False

    def test_should_extract_return_meta_uses_return_threshold(self):
        p = ThresholdPolicy(max_arg_bytes=10000, max_return_bytes=100)
        data = b"x" * 200
        # arg threshold is high, so should_extract_meta returns False
        assert p.should_extract_meta(data) is False
        # return threshold is low, so should_extract_return_meta returns True
        assert p.should_extract_return_meta(data) is True

    def test_custom_thresholds(self):
        p = ThresholdPolicy(max_arg_bytes=50, max_return_bytes=50)
        assert p.should_extract_meta(b"x" * 51) is True
        assert p.should_extract_meta(b"x" * 49) is False


class TestSizeof:

    def test_bytes(self):
        assert sizeof(b"hello") == 5

    def test_bytearray(self):
        assert sizeof(bytearray(b"hello")) == 5

    def test_memoryview(self):
        assert sizeof(memoryview(b"hello")) == 5

    def test_int(self):
        result = sizeof(42)
        assert result == sys.getsizeof(42)

    def test_fallback_negative(self):
        class BadObj:
            def __sizeof__(self):
                raise TypeError("nope")
        assert sizeof(BadObj()) == -1
