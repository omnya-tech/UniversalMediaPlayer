# -*- coding: utf-8 -*-
"""قص الصوت ودمجه (core/media_editor.py) على ملفات حقيقية مولَّدة."""

import ast
import os
import threading

import pytest

from core.time_input import format_time_precise, parse_time
from tests.media_samples import write_sample_media

av = pytest.importorskip("av")

from core import media_editor as editor  # noqa: E402

# (الامتداد، المرمّز) - الصيغ الشائعة التي يقصها المستخدمون
FORMATS = [(".mp3", "libmp3lame"), (".m4a", "aac"), (".wav", "pcm_s16le"),
           (".flac", "flac"), (".opus", "libopus")]


def _sample(tmp_path, name, seconds, ext, codec):
    path = str(tmp_path / f"{name}{ext}")
    rate = 48_000 if codec == "libopus" else 44_100
    write_sample_media(path, seconds=seconds, with_video=False, audio_codec=codec, rate=rate)
    return path


def _decoded_seconds(path):
    """الطول الفعلي بعد فك الترميز، لا ما يقوله رأس الملف."""
    with av.open(path) as container:
        stream = container.streams.audio[0]
        samples = sum(frame.samples for frame in container.decode(stream))
        return samples / stream.codec_context.sample_rate


@pytest.mark.parametrize("ext,codec", FORMATS)
def test_split_gives_two_parts_that_add_up(tmp_path, ext, codec):
    source = _sample(tmp_path, "a", 6, ext, codec)
    first, second = str(tmp_path / f"1{ext}"), str(tmp_path / f"2{ext}")
    editor.split_file(source, 2.5, first, second)
    assert _decoded_seconds(first) == pytest.approx(2.5, abs=0.1)
    assert _decoded_seconds(second) == pytest.approx(3.5, abs=0.12)


@pytest.mark.parametrize("ext,codec", FORMATS)
def test_segments_are_joined_in_order(tmp_path, ext, codec):
    source = _sample(tmp_path, "a", 6, ext, codec)
    output = str(tmp_path / f"out{ext}")
    editor.extract_segments(source, [(3.5, 5), (1, 2)], output)
    assert _decoded_seconds(output) == pytest.approx(2.5, abs=0.1)


@pytest.mark.parametrize("ext,codec", FORMATS)
def test_merge_keeps_format_and_total_length(tmp_path, ext, codec):
    a = _sample(tmp_path, "a", 3, ext, codec)
    b = _sample(tmp_path, "b", 2, ext, codec)
    output = str(tmp_path / f"out{ext}")
    editor.merge_files([a, b], output)
    assert _decoded_seconds(output) == pytest.approx(5, abs=0.1)
    # والمدة التي يقرؤها المشغّل من رأس الملف صحيحة أيضًا
    assert editor.get_duration(output) == pytest.approx(5, abs=0.1)


def test_flac_header_reports_the_new_length(tmp_path):
    # النسخ المباشر يأخذ رأس الأصل، وفيه طول الأصل كاملًا
    source = _sample(tmp_path, "a", 6, ".flac", "flac")
    first, second = str(tmp_path / "1.flac"), str(tmp_path / "2.flac")
    editor.split_file(source, 2, first, second)
    assert editor.get_duration(first) == pytest.approx(2, abs=0.1)
    assert editor.get_duration(second) == pytest.approx(4, abs=0.1)


def test_merging_different_formats_reencodes_to_the_first(tmp_path):
    mp3 = _sample(tmp_path, "a", 2, ".mp3", "libmp3lame")
    wav = _sample(tmp_path, "b", 2, ".wav", "pcm_s16le")
    output = str(tmp_path / "out.mp3")
    editor.merge_files([mp3, wav], output)
    with av.open(output) as container:
        assert container.streams.audio[0].codec_context.name.startswith("mp3")
    assert _decoded_seconds(output) == pytest.approx(4, abs=0.1)


def test_split_time_outside_the_file_is_refused(tmp_path):
    source = _sample(tmp_path, "a", 2, ".mp3", "libmp3lame")
    with pytest.raises(editor.EditError):
        editor.split_file(source, 5, str(tmp_path / "1.mp3"), str(tmp_path / "2.mp3"))
    assert not os.path.exists(tmp_path / "1.mp3")


def test_cancel_leaves_no_half_written_files(tmp_path):
    source = _sample(tmp_path, "a", 4, ".wav", "pcm_s16le")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(editor.ConversionCancelled):
        editor.split_file(source, 2, str(tmp_path / "1.wav"), str(tmp_path / "2.wav"), cancel)
    assert sorted(os.listdir(tmp_path)) == ["a.wav"]


def test_runner_reports_each_failure_and_continues(tmp_path):
    good = _sample(tmp_path, "good", 4, ".wav", "pcm_s16le")
    short = _sample(tmp_path, "short", 1, ".wav", "pcm_s16le")
    results, done = [], threading.Event()

    def job(path):
        return lambda cancel, progress: editor.split_file(
            path, 2, path + ".1.wav", path + ".2.wav", cancel, progress)

    runner = editor.EditJobRunner(
        on_job_done=lambda i, n, name, error: results.append((name, error is None)),
        on_all_done=lambda ok, bad, cancelled: (results.append((ok, bad, cancelled)), done.set()),
    )
    runner.start([("short", job(short)), ("good", job(good))])
    assert done.wait(30)
    assert results == [("short", False), ("good", True), (1, 1, False)]


def _video_sample(tmp_path, name, seconds, ext=".mp4", size=(160, 120)):
    # 10 إطارات في الثانية وإطار مفتاحي كل ثانيتين
    path = str(tmp_path / f"{name}{ext}")
    write_sample_media(path, seconds=seconds, keyframe_every=20, size=size)
    return path


def _video_frames(path):
    with av.open(path) as container:
        return sum(1 for _ in container.decode(container.streams.video[0]))


@pytest.mark.parametrize("ext", [".mp4", ".mkv", ".mov", ".ts"])
def test_fast_video_split_snaps_to_the_keyframe(tmp_path, ext):
    source = _video_sample(tmp_path, "a", 8, ext)
    first, second = str(tmp_path / f"1{ext}"), str(tmp_path / f"2{ext}")
    point = editor.split_file(source, 3.3, first, second)
    assert point == pytest.approx(2.0, abs=0.01)
    # لا إطار يضيع ولا يتكرر بين الجزأين
    assert (_video_frames(first), _video_frames(second)) == (20, 60)
    assert _decoded_seconds(first) == pytest.approx(2.0, abs=0.1)


@pytest.mark.parametrize("ext", [".mp4", ".mkv"])
def test_precise_video_split_cuts_at_the_exact_time(tmp_path, ext):
    source = _video_sample(tmp_path, "a", 8, ext)
    first, second = str(tmp_path / f"1{ext}"), str(tmp_path / f"2{ext}")
    point = editor.split_file(source, 3.3, first, second, precise=True)
    assert point == 3.3
    assert (_video_frames(first), _video_frames(second)) == (33, 47)
    assert _decoded_seconds(second) == pytest.approx(4.7, abs=0.1)


def test_video_segments_fast_and_precise(tmp_path):
    source = _video_sample(tmp_path, "a", 8)
    fast, precise = str(tmp_path / "fast.mp4"), str(tmp_path / "precise.mp4")
    segments = [(1, 2.5), (5.2, 7)]
    editor.extract_segments(source, segments, fast)
    editor.extract_segments(source, segments, precise, precise=True)
    # السريع يبدأ كل مقطع من الإطار المفتاحي السابق: 0 و4
    assert _video_frames(fast) == 55
    assert _video_frames(precise) == 33
    assert _decoded_seconds(precise) == pytest.approx(3.3, abs=0.1)


def test_matching_videos_merge_without_reencoding(tmp_path):
    a = _video_sample(tmp_path, "a", 4)
    b = _video_sample(tmp_path, "b", 2)
    output = str(tmp_path / "out.mp4")
    editor.merge_files([a, b], output)
    assert _video_frames(output) == 60
    assert editor.get_duration(output) == pytest.approx(6, abs=0.1)


def test_different_videos_are_refused_with_a_reason(tmp_path):
    a = _video_sample(tmp_path, "a", 2)
    b = _video_sample(tmp_path, "b", 2, size=(320, 240))
    with pytest.raises(editor.EditError):
        editor.merge_files([a, b], str(tmp_path / "out.mp4"))
    audio = _sample(tmp_path, "c", 2, ".m4a", "aac")
    with pytest.raises(editor.EditError):
        editor.merge_files([a, audio], str(tmp_path / "out2.mp4"))
    assert not os.path.exists(tmp_path / "out.mp4")


def test_editor_has_no_external_process():
    """
    القص والدمج داخل البرنامج فقط.

    محاولة سابقة استدعت ما هو خارج البرنامج فعملت على جهاز فيه بايثون
    وتوقفت على غيره. لا subprocess ولا os.system ولا sys.executable.
    """
    for module in ("core/media_editor.py", "gui/media_editor_dialog.py"):
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), module)
        with open(root, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        assert not names & {"subprocess", "multiprocessing", "system", "popen", "executable"}, module


def test_time_accepts_fractions_of_a_second():
    assert parse_time("1:30.5") == 90.5
    assert parse_time("0.25") == 0.25
    assert format_time_precise(90.46) == "1:30.5"
    assert format_time_precise(5) == "0:05"
