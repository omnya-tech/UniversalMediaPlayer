# -*- coding: utf-8 -*-
"""اختبارات لمنطق قائمة التشغيل المبنية على المجلد (core/playlist.py)."""

import pytest

from core.playlist import Playlist


@pytest.fixture
def media_folder(tmp_path):
    names = ["b_song.mp3", "a_song.flac", "c_video.mp4", "notes.txt", "d_song.wav"]
    for name in names:
        (tmp_path / name).write_bytes(b"fake content")
    return tmp_path


def test_load_folder_lists_only_supported_files_sorted(media_folder):
    playlist = Playlist()
    target = str(media_folder / "c_video.mp4")
    playlist.load_folder_of(target)

    assert len(playlist) == 4  # notes.txt متسثناة
    assert playlist.current == target


def test_navigation_next_and_previous(media_folder):
    playlist = Playlist()
    playlist.load_folder_of(str(media_folder / "a_song.flac"))  # أول ملف أبجديًا

    assert not playlist.has_previous()
    assert playlist.has_next()

    second = playlist.next()
    assert second is not None
    assert playlist.current == second

    back = playlist.previous()
    assert back == str(media_folder / "a_song.flac")


def test_next_returns_none_at_end(media_folder):
    playlist = Playlist()
    playlist.load_folder_of(str(media_folder / "d_song.wav"))  # آخر ملف أبجديًا
    assert not playlist.has_next()
    assert playlist.next() is None


def test_file_with_unlisted_extension_falls_back_to_single_item(tmp_path):
    odd_file = tmp_path / "clip.xyz"
    odd_file.write_bytes(b"data")
    playlist = Playlist()
    playlist.load_folder_of(str(odd_file))
    assert len(playlist) == 1
    assert playlist.current == str(odd_file)


def test_nonexistent_folder_falls_back_gracefully():
    playlist = Playlist()
    playlist.load_folder_of("/this/path/does/not/exist/file.mp3")
    assert len(playlist) == 1
    assert playlist.current == "/this/path/does/not/exist/file.mp3"


def test_ts_mpg_mpa_mas_are_treated_as_ordinary_supported_formats(tmp_path):
    """.ts وmpg. وmpa. وmas. لازم تتعامل بالظبط زي أي صيغة صوت/فيديو
    مدعومة تانية: تظهر في قائمة تشغيل المجلد ولا تُستثنى منها."""
    names = ["a_clip.ts", "b_clip.mpg", "c_track.mpa", "d_track.mas", "notes.txt"]
    for name in names:
        (tmp_path / name).write_bytes(b"fake content")

    playlist = Playlist()
    target = str(tmp_path / "a_clip.ts")
    playlist.load_folder_of(target)

    assert len(playlist) == 4  # notes.txt مستثناة فقط
    assert playlist.current == target
