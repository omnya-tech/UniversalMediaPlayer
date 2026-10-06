# -*- coding: utf-8 -*-
"""اختبارات تحسين صوت المايكروفون وتحويل معدل الالتقاط في الوضع الحصري."""

import numpy as np
import pytest

pytest.importorskip("av")

from core.audio_filters import rate_converter
from core.audio_recorder import AudioRecorder
from core.voice_enhance import NoiseReducer, VoiceEnhancer

RATE = 48000


def _db(signal):
    return 10 * np.log10(np.mean(np.square(signal)) + 1e-20)


def _run(enhancer, samples, max_abs=32768.0, block=480):
    out = [enhancer.process(samples[i:i + block], max_abs) for i in range(0, len(samples), block)]
    out.append(enhancer.flush())
    return np.concatenate(out)


@pytest.mark.parametrize("level", ["clean", "denoise"])
@pytest.mark.parametrize("channels", [1, 2])
def test_enhancer_returns_every_sample(level, channels):
    """كتل بأطوال غير منتظمة: الخارج بعد flush بطول الداخل بالضبط."""
    rng = np.random.default_rng(1)
    samples = (rng.standard_normal((RATE * 2 + 37, channels)) * 3000).astype("int16")
    enhancer = VoiceEnhancer(RATE, channels, level)
    out = [enhancer.process(samples[i:i + 441], 32768.0) for i in range(0, len(samples), 441)]
    out.append(enhancer.flush())
    assert sum(len(part) for part in out) == len(samples)


def _speech_like_with_noise(noise_db):
    """نغمة تتقطع كالكلام (نصف ثانية صوت ونصف سكتة) فوق ضوضاء ثابتة."""
    rng = np.random.default_rng(2)
    seconds = 6
    t = np.arange(RATE * seconds) / RATE
    voice = 0.1 * np.sin(2 * np.pi * 300 * t) * ((t % 1.0) < 0.5)
    noise = rng.standard_normal(len(t)) * 10 ** (noise_db / 20)
    return voice, noise


def test_denoise_lowers_steady_noise_that_old_filter_left_alone():
    """
    ضوضاء عند -38 ديسيبل (مايك USB حقيقي): afftdn بأرضيته الثابتة عند -50
    لم يخفض منها شيئًا. المطلوب الآن خفض واضح في السكتات بلا مساس بالصوت.
    """
    voice, noise = _speech_like_with_noise(-38)
    mixed = ((voice + noise) * 32767).astype("int16").reshape(-1, 1)
    t = np.arange(len(voice)) / RATE
    # السكتات بعد أن يستقر تقدير الضوضاء، بعيدًا عن حواف النغمة
    pauses = (t > 2.5) & ((t % 1.0) > 0.6) & ((t % 1.0) < 0.95)
    tones = (t > 2.5) & ((t % 1.0) > 0.1) & ((t % 1.0) < 0.4)

    clean = _run(VoiceEnhancer(RATE, 1, "clean"), mixed)[:, 0] / 32768
    denoised = _run(VoiceEnhancer(RATE, 1, "denoise"), mixed)[:, 0] / 32768

    assert _db(clean[pauses]) - _db(denoised[pauses]) > 8
    assert abs(_db(clean[tones]) - _db(denoised[tones])) < 1


def test_noise_reducer_leaves_quiet_recordings_untouched():
    """مايك هادئ: النغمة تخرج كما دخلت تقريبًا."""
    voice, noise = _speech_like_with_noise(-75)
    data = (voice + noise).astype(np.float32).reshape(-1, 1)
    reducer = NoiseReducer(RATE, 1)
    out = np.concatenate([reducer.process(data[i:i + 480]) for i in range(0, len(data), 480)]
                         + [reducer.flush()])[:, 0]
    t = np.arange(len(voice)) / RATE
    tones = (t > 2.5) & ((t % 1.0) > 0.1) & ((t % 1.0) < 0.4)
    assert _db(out[tones] - voice[tones]) - _db(voice[tones]) < -30


def test_rate_converter_keeps_duration_and_drops_ultrasound():
    """192000 → 48000: الطول بالضبط، والنغمة المسموعة تبقى وما فوق 24 كيلو يختفي."""
    capture = 192000
    t = np.arange(capture) / capture
    audible = (0.5 * 2**31 * np.sin(2 * np.pi * 1000 * t)).astype("int32").reshape(-1, 1)
    ultrasound = (0.5 * 2**31 * np.sin(2 * np.pi * 30000 * t)).astype("int32").reshape(-1, 1)
    for source, expected_db in ((audible, -3.0), (ultrasound, None)):
        converter = rate_converter(capture, RATE, 1, "int32")
        out = [converter.push(source[i:i + 1920]) for i in range(0, len(source), 1920)]
        out.append(converter.flush())
        result = np.concatenate(out)[:, 0] / 2**31
        assert len(result) == RATE
        if expected_db is None:
            assert _db(result[1000:-1000]) < -80
        else:
            assert _db(result[1000:-1000]) == pytest.approx(10 * np.log10(0.125), abs=0.2)


def test_exclusive_tries_device_native_rate_before_shared():
    """مايك لا يقبل الحصري إلا بمعدله الأصلي: يُجرَّب قبل الرجوع للمشترك."""
    recorder = AudioRecorder()
    recorder.exclusive_requested = True
    attempts = list(recorder._input_attempts(48000, 2, native_rate=192000))
    exclusive = [(rate, chans) for rate, chans, extra in attempts
                 if getattr(extra, "_exclusive", False)]
    if not exclusive:
        pytest.skip("WASAPI غير متاح")
    assert exclusive == [(48000, 2), (48000, 1), (192000, 2), (192000, 1)]
    first_shared = next(i for i, (_, _, extra) in enumerate(attempts)
                        if not getattr(extra, "_exclusive", False))
    assert first_shared == len(exclusive)
