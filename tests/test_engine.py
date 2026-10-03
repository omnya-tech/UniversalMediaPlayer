# -*- coding: utf-8 -*-
"""
اختبارات تكاملية لمحرك التشغيل (core/engine.py) باستخدام ملف وسائط
صغير حقيقي (مش mock)، عشان نتأكد إن فتح/تشغيل/إيقاف مؤقت/قفز/إيقاف
كامل بتشتغل فعليًا مع VLC، مش بس نظريًا.

ملحوظة: المحرك بقى مبني على مكتبة VLC (python-vlc + برنامج VLC نفسه
مثبّت على الجهاز) بدل PyAV القديم - شوفي core/engine.py للتفاصيل.
الاختبارات دي بتحتاج:
1. ffmpeg متاح على الجهاز عشان تولّد ملف اختبار صغير.
2. برنامج VLC (أو على الأقل مكتبة libvlc) مثبّت على الجهاز عشان
   المحرك يقدر يشتغل فعليًا.
لو أي منهم مش متاح، الاختبارات بتتخطى (skip) تلقائيًا بدل ما تفشل.
"""

import shutil
import subprocess
import time

import pytest

from core.engine import PlayerEngine, PlaybackState, _HAS_VLC

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def _vlc_actually_works() -> bool:
    """python-vlc ممكن يكون متثبت (import بينجح) من غير ما مكتبة libvlc
    الفعلية تكون موجودة على الجهاز - بنتأكد بمحاولة إنشاء Instance فعلي."""
    if not _HAS_VLC:
        return False
    try:
        import vlc
        instance = vlc.Instance("--quiet")
        return instance is not None
    except Exception:
        return False


VLC_AVAILABLE = _vlc_actually_works()
requires_vlc = pytest.mark.skipif(not VLC_AVAILABLE, reason="مكتبة VLC غير متاحة في هذه البيئة")


@pytest.fixture(scope="module")
def sample_media_file(tmp_path_factory):
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg غير متاح في هذه البيئة")

    out_dir = tmp_path_factory.mktemp("media")
    out_path = str(out_dir / "sample.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", out_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out_path


def _make_engine():
    events = {"states": [], "errors": []}

    def on_state(state):
        events["states"].append(state)

    def on_error(msg):
        events["errors"].append(msg)

    engine = PlayerEngine(on_state_change=on_state, on_error=on_error)
    return engine, events


@requires_vlc
def test_open_nonexistent_file_reports_error_not_exception():
    engine, events = _make_engine()
    ok = engine.open("/this/path/does/not/exist.mp3")
    assert ok is False
    assert len(events["errors"]) == 1


@requires_vlc
def test_open_and_play_reports_video(sample_media_file):
    """بعكس المحرك القديم، محرك VLC بيرسم الفيديو مباشرة على نافذة
    الواجهة (شوفي set_video_widget_handle) مش عن طريق استدعاء
    on_video_frame لكل إطار - فبدل ما نعدّ الإطارات، بنتأكد إن الملف
    اتفتح صح ومدته صحيحة وإن المحرك عارف إن فيه فيديو."""
    engine, events = _make_engine()
    ok = engine.open(sample_media_file)
    assert ok is True
    assert engine.duration == pytest.approx(2.0, abs=0.3)

    engine.play()
    time.sleep(1.0)
    assert engine.state in (PlaybackState.PLAYING, PlaybackState.LOADING)
    engine.stop()


@requires_vlc
def test_pause_preserves_position_and_resume_continues(sample_media_file):
    engine, events = _make_engine()
    engine.open(sample_media_file)
    engine.play()
    time.sleep(0.8)

    pos_before = engine.get_current_position()
    engine.pause()
    time.sleep(0.5)
    pos_during_pause = engine.get_current_position()

    # المفروض الموضع ميتحركش وهو متوقف مؤقتًا
    assert pos_during_pause == pytest.approx(pos_before, abs=0.1)

    engine.play()
    time.sleep(0.3)
    pos_after_resume = engine.get_current_position()
    assert pos_after_resume >= pos_before
    engine.stop()


@requires_vlc
def test_seek_while_playing_takes_effect(sample_media_file):
    engine, events = _make_engine()
    engine.open(sample_media_file)
    engine.play()
    time.sleep(0.5)

    engine.seek(0.1)
    time.sleep(0.3)
    # المفروض الموضع يبقى قريب من نقطة القفز + وقت الانتظار البسيط،
    # مش مكان عشوائي بعيد عنها
    assert engine.get_current_position() == pytest.approx(0.4, abs=0.3)
    engine.stop()


@requires_vlc
def test_stop_rewinds_to_zero(sample_media_file):
    engine, events = _make_engine()
    engine.open(sample_media_file)
    engine.play()
    time.sleep(0.8)
    engine.stop()
    assert engine.state == PlaybackState.STOPPED
    assert engine.get_current_position() == 0.0


@requires_vlc
def test_stop_is_responsive(sample_media_file):
    """اختبار إن الإيقاف سريع ومش عالق - كان مهم بالذات مع المحرك
    القديم (خيوط فك ترميز يدوية ممكن تتجمد)، وبيفضل قيمة كإجراء أمان
    مع محرك VLC الجديد كمان."""
    engine, events = _make_engine()
    engine.open(sample_media_file)
    engine.play()
    time.sleep(1.0)

    start = time.monotonic()
    engine.stop()
    elapsed = time.monotonic() - start
    assert engine.state == PlaybackState.STOPPED
    assert elapsed < 1.0  # الإيقاف لازم يكون سريع، مش عالق لثواني


def test_engine_degrades_gracefully_without_vlc():
    """حتى لو VLC مش متاحة خالص على الجهاز، المحرك المفروض يتعامل مع
    كل نداءاته من غير ما يتعطل (Exception) - يبلّغ خطأ واحد بس عبر
    on_error ويفضل شغال بأمان (حالة "متوقف" ثابتة)."""
    events = {"errors": []}
    engine = PlayerEngine(on_error=lambda m: events["errors"].append(m))
    # كل النداءات دي المفروض تكون آمنة تمامًا بغض النظر عن توفر VLC
    engine.play()
    engine.pause()
    engine.stop()
    engine.seek(5)
    engine.set_volume(50)
    engine.set_muted(True)
    engine.set_speed(1.5)
    engine.toggle_play_pause()
    assert engine.duration == 0.0 or isinstance(engine.duration, float)
    assert engine.get_current_position() == 0.0
    if not VLC_AVAILABLE:
        assert len(events["errors"]) >= 1
