# -*- coding: utf-8 -*-
"""
توليد ملفات وسائط صغيرة حقيقية للاختبارات بـ PyAV (من مكتبات المشروع
أصلًا)، بدل الاعتماد على ffmpeg خارجي مش موجود على أغلب الأجهزة.
"""

import numpy as np
import pytest


def _mux(container, stream, frame):
    for packet in stream.encode(frame):
        container.mux(packet)


def write_sample_media(out_path, seconds=2, with_video=True, audio_codec="aac",
                       audio_bit_rate=None, video_bit_rate=None, rate=44_100):
    """
    ملف بنغمة 440 هرتز، ومعاه (اختياريًا) فيديو 160x120 بـ 10 إطارات/ث.
    الحاوية بتتحدد من امتداد out_path.
    """
    av = pytest.importorskip("av")
    with av.open(out_path, "w") as container:
        if with_video:
            video = container.add_stream("libx264", rate=10)
            video.width, video.height, video.pix_fmt = 160, 120, "yuv420p"
            if video_bit_rate:
                video.bit_rate = video_bit_rate
        audio = container.add_stream(audio_codec, rate=rate)
        audio.layout = "mono"
        if audio_bit_rate:
            audio.bit_rate = audio_bit_rate

        if with_video:
            for i in range(seconds * 10):
                img = np.full((120, 160, 3), (i * 12) % 256, dtype=np.uint8)
                _mux(container, video, av.VideoFrame.from_ndarray(img, format="rgb24"))
            _mux(container, video, None)

        # الـ resampler بيقطّع العينات لحجم الإطار اللي المرمّز محتاجه
        # (aac عايز 1024 بالظبط، وmp3 عايز 1152)
        resampler = av.AudioResampler(format=audio.format.name, layout="mono", rate=rate,
                                      frame_size=audio.frame_size or None)
        t = np.arange(seconds * rate) / rate
        samples = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32).reshape(1, -1)
        source = av.AudioFrame.from_ndarray(samples, format="flt", layout="mono")
        source.sample_rate = rate
        for frame in resampler.resample(source) + resampler.resample(None):
            _mux(container, audio, frame)
        _mux(container, audio, None)
