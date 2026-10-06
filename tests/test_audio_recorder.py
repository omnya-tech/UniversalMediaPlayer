# -*- coding: utf-8 -*-
"""اختبارات core.audio_recorder.replace_with_retry - آلية مقاومة لفشل
مؤقت في نظام الملفات وقت نقل ملف التسجيل النهائي (أشهر سبب حقيقي على
ويندوز: برنامج مكافحة فيروسات بيفحص ملف الوسائط المُنشأ حديثًا في مجلد
Temp للحظات قليلة قبل ما يتاح بالكامل لبرامج تانية)."""

import os

import numpy as np
import pytest

from core.audio_recorder import AudioRecorder, replace_with_retry


def test_replace_with_retry_succeeds_after_transient_failures(tmp_path, monkeypatch):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello", encoding="utf-8")

    real_replace = os.replace
    call_count = {"n": 0}

    def flaky_replace(a, b):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise OSError("محاكاة: الملف مؤقتًا غير متاح")
        real_replace(a, b)

    monkeypatch.setattr("core.audio_recorder.os.replace", flaky_replace)
    monkeypatch.setattr("core.audio_recorder.time.sleep", lambda seconds: None)

    replace_with_retry(str(src), str(dst))

    assert dst.exists()
    assert call_count["n"] == 3


def test_replace_with_retry_raises_after_exhausting_attempts(tmp_path, monkeypatch):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello", encoding="utf-8")

    call_count = {"n": 0}

    def always_fail(a, b):
        call_count["n"] += 1
        raise OSError("فشل دائم")

    monkeypatch.setattr("core.audio_recorder.os.replace", always_fail)
    monkeypatch.setattr("core.audio_recorder.time.sleep", lambda seconds: None)

    with pytest.raises(OSError):
        replace_with_retry(str(src), str(dst), attempts=4)

    assert call_count["n"] == 4
    # الملف الأصلي لازم يفضل زي ما هو - محاولة فاشلة نهائيًا ما ينفعش
    # تسيب حاجة ناقصة أو تمسح المصدر
    assert src.exists()
    assert not dst.exists()


def test_replace_with_retry_succeeds_immediately_when_no_failure(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello", encoding="utf-8")

    replace_with_retry(str(src), str(dst))

    assert dst.exists()
    assert not src.exists()


def test_direct_encode_writes_valid_mp3_without_intermediate_wav(tmp_path):
    """التسجيل بصيغة غير WAV لازم يترمّز مباشرة أثناء التسجيل نفسه (بدون
    أي ملف WAV وسيط)، وينتج ملف MP3 سليم بمدة قريبة من المدة الحقيقية
    للصوت المُلتقط."""
    av = pytest.importorskip("av")

    output_path = str(tmp_path / "recording.mp3")
    recorder = AudioRecorder()

    sample_rate = 44100
    channels = 2
    recorder._sample_rate = sample_rate
    recorder._channels = channels
    recorder._bit_depth = 16
    recorder._dtype = "int16"

    recorder._open_direct_encoder(output_path, ".mp3", audio_bitrate=128_000)
    assert recorder._direct_encode is False  # لسه ما اتحددتش هنا، بتتحدد في start()
    recorder._direct_encode = True

    block_frames = 1024
    total_blocks = (sample_rate * 2) // block_frames  # ~ثانيتين
    for _ in range(total_blocks):
        tone = (np.sin(np.linspace(0, 2 * np.pi * 440, block_frames)) * 0.3 * 32767).astype(np.int16)
        chunk = np.column_stack([tone, tone])
        recorder._encode_chunk(chunk)

    # تفريغ وإغلاق زي ما stop() بتعمل بالظبط
    for packet in recorder._out_audio_stream.encode(None):
        recorder._out_container.mux(packet)
    recorder._out_container.close()

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0

    in_container = av.open(output_path)
    assert in_container.duration is not None
    duration_seconds = float(in_container.duration) / av.time_base
    assert 1.5 < duration_seconds < 2.5


def _run_dual_writer(tmp_path, secondary_block):
    """يشغّل كاتب التسجيل المدمج على نغمتين ثابتتين بلا كرت صوت."""
    import threading
    import time
    import wave

    from core.level_balance import TrackBalancer

    recorder = AudioRecorder()
    recorder._sample_rate, recorder._channels = 48000, 1
    recorder._dtype, recorder._max_abs, recorder._bit_depth = "int16", 32768.0, 16
    recorder._direct_encode = False
    path = str(tmp_path / "dual.wav")
    recorder._wave_file = wave.open(path, "wb")
    recorder._wave_file.setnchannels(1)
    recorder._wave_file.setsampwidth(2)
    recorder._wave_file.setframerate(48000)
    recorder._has_dual_input = True
    recorder._balance_pri, recorder._balance_sec = TrackBalancer(), TrackBalancer()
    recorder._reset_secondary_buffer(1)
    recorder._stop_flag.clear()
    writer = threading.Thread(target=recorder._writer_loop)
    writer.start()

    def tone(freq, start, count):
        t = np.arange(start, start + count) / 48000
        return (0.3 * 32767 * np.sin(2 * np.pi * freq * t)).astype("int16").reshape(-1, 1)

    primary = secondary = 0
    for _ in range(300):  # ثلاث ثوانٍ بكتل 10 مللي ثانية
        recorder._queue_pri.put(tone(440, primary, 480))
        primary += 480
        while secondary < primary:
            recorder._queue_sec.put(tone(1000, secondary, secondary_block))
            secondary += secondary_block
        time.sleep(0.001)
    recorder._stop_flag.set()
    writer.join()
    recorder._wave_file.close()

    with wave.open(path) as handle:
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype="int16") / 32768
    # مستوى المايك (440 هرتز) وحده في كل 10 مللي ثانية بعد أن تستقر الموازنة
    levels = []
    for start in range(48000, len(samples) - 480, 480):
        k = np.arange(start, start + 480) / 48000
        basis = np.stack([np.sin(2 * np.pi * 440 * k), np.cos(2 * np.pi * 440 * k),
                          np.sin(2 * np.pi * 1000 * k), np.cos(2 * np.pi * 1000 * k)], 1)
        coef = np.linalg.lstsq(basis, samples[start:start + 480], rcond=None)[0]
        levels.append(np.hypot(coef[0], coef[1]))
    return len(samples) / 48000, np.array(levels)


@pytest.mark.parametrize("secondary_block", [441, 1024])
def test_dual_recording_keeps_the_microphone_steady(tmp_path, secondary_block):
    """
    التسجيل المدمج لا يقطّع المايكروفون ولا يغيّر مستواه.

    الكود القديم كان يدمج كتلة بكتلة: صوت النظام بكتل 1024 عينة جعل
    التسجيل أطول بنصفه (المايكروفون مقطّع بصمت كل عشر مللي ثوانٍ) ومستوى
    المايكروفون يقفز بين الصفر والكامل في أغلب الكتل. هذا ما اشتكى منه
    مستخدمون كانقطاعات قصيرة وتشويه.
    """
    duration, levels = _run_dual_writer(tmp_path, secondary_block)
    assert duration == pytest.approx(3.0, abs=0.02)
    assert levels.min() > 0.8 * levels.mean()
    assert levels.max() < 1.2 * levels.mean()
