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
