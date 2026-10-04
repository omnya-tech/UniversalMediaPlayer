# -*- coding: utf-8 -*-
"""اختبارات التعرّف على روابط البث وتنظيفها (core/streams.py)."""

import pytest

from core.streams import is_stream_url, normalize_stream_url, stream_display_name


@pytest.mark.parametrize("text, expected", [
    ("http://radio.example.com/live", "http://radio.example.com/live"),
    ("  https://x.org/a.mp3 \n", "https://x.org/a.mp3"),
    ('"https://x.org/a.mp3"', "https://x.org/a.mp3"),
    ("rtsp://cam.local/stream", "rtsp://cam.local/stream"),
    ("www.example.com/live", "http://www.example.com/live"),
    ("example.com:8000/stream", "http://example.com:8000/stream"),
    (r"C:\Music\song.mp3", None),
    ("song.mp3", None),
    ("file:///C:/x.mp3", None),
    ("javascript:alert(1)", None),
    ("http://a b.com", None),
    ("", None),
    ("just words", None),
    (None, None),
])
def test_normalize_stream_url(text, expected):
    assert normalize_stream_url(text) == expected


def test_is_stream_url_rejects_local_paths():
    assert is_stream_url("https://x.org/a")
    assert not is_stream_url(r"C:\x.mp3")
    assert not is_stream_url("/home/x.mp3")
    assert not is_stream_url("ftp://x.org/a")
    assert not is_stream_url("http://")


def test_stream_display_name_prefers_meaningful_tail():
    assert stream_display_name("http://radio.example.com/quran.mp3") == "quran.mp3 (radio.example.com)"
    assert stream_display_name("http://radio.example.com/stream") == "radio.example.com"
    assert stream_display_name("http://radio.example.com:8000/") == "radio.example.com"
    assert stream_display_name("http://x.com/%D9%82%D8%B1%D8%A2%D9%86") == "قرآن (x.com)"
