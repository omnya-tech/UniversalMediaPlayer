# -*- coding: utf-8 -*-
"""اختبارات قراءة وكتابة ملفات القوائم (core/playlist_files.py)
وتعديل القائمة نفسها (core/playlist.py)."""

import os

import pytest

from core.playlist import Playlist
from core.playlist_files import (
    PlaylistFileError,
    is_playlist_file,
    read_playlist,
    write_m3u8,
)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x")
    return path


def test_m3u8_roundtrip_keeps_order_titles_urls_and_arabic_names(tmp_path):
    inside = _touch(str(tmp_path / "سور" / "الفاتحة.mp3"))
    outside = _touch(str(tmp_path.parent / f"{tmp_path.name}_other" / "b.mp3"))
    url = "http://radio.example.com/live"
    playlist_path = str(tmp_path / "قائمتي.m3u8")

    write_m3u8(playlist_path, [inside, url, outside], titles={url: "إذاعة القرآن"})

    with open(playlist_path, encoding="utf-8") as handle:
        text = handle.read()
    # الملف اللي جوه مجلد القائمة بيتكتب نسبي عشان القائمة تتنقل معاه
    assert os.path.join("سور", "الفاتحة.mp3") in text
    assert os.path.abspath(outside) in text

    entries = read_playlist(playlist_path)
    assert [e for e, _ in entries] == [os.path.normpath(inside), url, os.path.normpath(outside)]
    assert entries[1][1] == "إذاعة القرآن"


def test_reads_legacy_m3u_in_windows_arabic_encoding(tmp_path):
    playlist_path = tmp_path / "old.m3u"
    playlist_path.write_bytes("#EXTM3U\n#EXTINF:12,أغنية\nأغنية.mp3\n".encode("cp1256"))
    entries = read_playlist(str(playlist_path))
    assert entries == [(os.path.normpath(str(tmp_path / "أغنية.mp3")), "أغنية")]


def test_reads_pls(tmp_path):
    playlist_path = tmp_path / "radio.pls"
    playlist_path.write_text(
        "[playlist]\nFile2=b.mp3\nFile1=http://x.org/live\nTitle1=Live\nNumberOfEntries=2\n",
        encoding="utf-8",
    )
    entries = read_playlist(str(playlist_path))
    assert entries == [("http://x.org/live", "Live"), (os.path.normpath(str(tmp_path / "b.mp3")), None)]


def test_missing_playlist_raises_clear_error(tmp_path):
    with pytest.raises(PlaylistFileError):
        read_playlist(str(tmp_path / "nope.m3u8"))


def test_is_playlist_file():
    assert is_playlist_file("a.M3U8")
    assert is_playlist_file("a.pls")
    assert not is_playlist_file("a.mp3")


def test_playlist_accepts_urls_and_drops_missing_files(tmp_path):
    real = _touch(str(tmp_path / "a.mp3"))
    playlist = Playlist()
    ok = playlist.load_custom_list(
        [real, str(tmp_path / "gone.mp3"), "https://x.org/live"], initial_path="https://x.org/live")
    assert ok
    assert playlist.entries == [real, "https://x.org/live"]
    assert playlist.current == "https://x.org/live"


def test_playlist_edit_operations_track_current_item(tmp_path):
    a, b, c = (_touch(str(tmp_path / f"{n}.mp3")) for n in "abc")
    playlist = Playlist()
    playlist.load_custom_list([a, b, c], initial_path=b)

    assert playlist.move(1, -1) == 0          # b لفوق: الحالي بيتبعه
    assert playlist.current == b
    assert playlist.move(0, -1) == -1         # برّه الحدود
    assert playlist.entries == [b, a, c]

    assert playlist.remove(0)                 # شيل الحالي نفسه
    assert playlist.current_index == -1
    assert playlist.has_next()
    assert playlist.next() == a               # التالي هو اللي خد مكانه

    assert playlist.add([c, str(tmp_path / "gone.mp3")]) == 1
    assert playlist.entries == [a, c, c]
    assert playlist.select(2) == c
    assert playlist.select(9) is None


def test_playlist_remove_last_item_empties_it(tmp_path):
    a = _touch(str(tmp_path / "a.mp3"))
    playlist = Playlist()
    playlist.load_custom_list([a])
    assert playlist.remove(0)
    assert len(playlist) == 0
    assert playlist.current is None
    assert not playlist.has_next()
    assert not playlist.has_previous()


def test_folder_scan_ignores_playlist_files(tmp_path):
    song = _touch(str(tmp_path / "a.mp3"))
    _touch(str(tmp_path / "list.m3u"))
    playlist = Playlist()
    playlist.load_folder_of(song)
    assert playlist.entries == [song]
