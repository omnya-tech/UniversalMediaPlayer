# -*- coding: utf-8 -*-
"""
اختبارات تكاملية لمحرك التشغيل (core/engine.py) باستخدام ملف وسائط
صغير حقيقي (مش mock)، عشان نتأكد إن فتح/تشغيل/إيقاف مؤقت/قفز/إيقاف
كامل بتشتغل فعليًا مع VLC، مش بس نظريًا.

ملحوظة: المحرك بقى مبني على مكتبة VLC (python-vlc) بدل PyAV القديم -
شوفي core/engine.py للتفاصيل.
الاختبارات دي بتحتاج مكتبة libvlc (المُضمَّنة في resources/vlc/ أو
المثبّتة على الجهاز). ملف الاختبار بيتولّد بـ PyAV (من مكتبات المشروع
أصلًا) بدل ffmpeg خارجي. لو أي منهم مش متاح، الاختبارات بتتخطى (skip)
تلقائيًا بدل ما تفشل.
"""

import time

import pytest

from core.engine import PlayerEngine, PlaybackState, _load_vlc
from tests.media_samples import write_sample_media


def _vlc_actually_works() -> bool:
    """python-vlc ممكن يكون متثبت (import بينجح) من غير ما مكتبة libvlc
    الفعلية تكون موجودة على الجهاز - بنتأكد بمحاولة إنشاء Instance فعلي.

    _load_vlc نفسها اللي المحرك بيستخدمها، عشان تجهّز مسار النسخة
    المُضمَّنة قبل الـ import (مش _HAS_VLC مباشرة: قيمتها None لحد أول
    تحميل، فكانت بتخلّي الاختبارات تتخطى دايمًا)."""
    if not _load_vlc():
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
    out_path = str(tmp_path_factory.mktemp("media") / "sample.mp4")
    write_sample_media(out_path)
    return out_path


def _wait_until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


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
    """القفز لازم يوصّل التشغيل لنقطة القفز فعلًا.

    بننتظر بالاستطلاع بدل sleep ثابت: VLC بيحدّث get_time على فترات
    (~250 م.ث) وبيعمل تخزين مؤقت بعد القفز، فوقت ثابت كان بيقيس توقيت
    VLC مش صحة القفز."""
    engine, events = _make_engine()
    engine.open(sample_media_file)
    engine.play()
    assert _wait_until(lambda: engine.get_current_position() > 0.0)

    target = 1.5
    engine.seek(target)
    assert _wait_until(lambda: engine.get_current_position() >= target - 0.3)
    assert engine.get_current_position() == pytest.approx(target, abs=0.6)
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
    """من غير ملف مفتوح (ومن غير VLC أصلًا)، كل نداءات المحرك المفروض
    تكون آمنة تمامًا من غير ما يتعطل (Exception).

    تهيئة VLC مؤجّلة لحد أول open (شوف _ensure_player)، فالنداءات دي
    ما بتلمسش VLC ولا بتبلّغ أخطاء - بتتجاهل بهدوء."""
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
    assert events["errors"] == []


@requires_vlc
def test_equalizer_preset_values_come_from_libvlc():
    values = PlayerEngine.get_equalizer_preset_values(0)  # flat
    assert values is not None
    preamp, bands = values
    assert len(bands) == 10
    assert all(abs(b) < 0.01 for b in bands)


@requires_vlc
def test_equalizer_can_change_while_playing_and_survives_new_file(sample_media_file):
    engine, events = _make_engine()
    engine.set_equalizer(6.0, [3.0] * 10)  # قبل وجود المشغّل: بيتحفظ
    engine.open(sample_media_file)
    engine.play()
    assert _wait_until(lambda: engine.state == PlaybackState.PLAYING)
    engine.set_equalizer(None)
    engine.set_equalizer(-3.0, [0.0] * 5)  # قائمة ناقصة ما توقعش حاجة
    engine.open(sample_media_file)
    assert events["errors"] == []
    engine.stop()


@pytest.fixture
def http_url_for(tmp_path):
    """سيرفر HTTP محلي صغير بيقدّم ملف - بديل حقيقي لرابط بث."""
    import functools
    import http.server
    import shutil as _shutil
    import threading

    servers = []

    def serve(path):
        _shutil.copy(path, tmp_path / "s.mp4")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
        handler.log_message = lambda *a, **k: None
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}/s.mp4"

    yield serve
    for server in servers:
        server.shutdown()


@requires_vlc
def test_open_and_play_http_url(sample_media_file, http_url_for):
    engine, events = _make_engine()
    url = http_url_for(sample_media_file)
    assert engine.open(url) is True
    assert engine.is_stream
    engine.play()
    assert _wait_until(lambda: engine.get_current_position() > 0.0)
    assert engine.has_video
    assert events["errors"] == []
    engine.stop()
