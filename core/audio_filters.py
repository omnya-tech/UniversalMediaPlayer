# -*- coding: utf-8 -*-
"""
تمرير كتل الصوت أثناء التسجيل عبر فلاتر FFmpeg الموجودة داخل PyAV.

يستعمله تحسين الصوت (core/voice_enhance.py) وتحويل معدل الالتقاط في
الوضع الحصري (core/audio_recorder.py): الكتل تدخل مصفوفات numpy وتخرج
مصفوفات بالصيغة نفسها، والفلاتر قد تحتجز بعض العينات فيُخرجها flush.
"""

from fractions import Fraction

import numpy as np

# صيغة FFmpeg المتشابكة المقابلة لنوع عينات numpy
_AV_FORMATS = {"int16": "s16", "int32": "s32", "float32": "flt"}


class FilterChain:
    """
    سلسلة فلاتر صوت: (اسم، معاملات) بالترتيب.

    out_rate يغيّر المعدل في آخر السلسلة (aresample داخلها مسؤول عن
    التحويل). الخرج دائمًا بنوع الدخل وعدد قنواته.
    """

    def __init__(self, sample_rate, channels, dtype, filters, out_rate=None):
        import av
        from av.filter import Graph

        self._av = av
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.dtype = np.dtype(dtype)
        self.out_rate = int(out_rate or sample_rate)
        fmt = _AV_FORMATS[self.dtype.name]
        self._fmt = fmt
        self._layout = "mono" if self.channels == 1 else "stereo"
        self._pts = 0
        self._flushed = False

        graph = Graph()
        previous = graph.add_abuffer(format=fmt, sample_rate=self.sample_rate, layout=self._layout)
        for name, args in filters:
            node = graph.add(name, args)
            previous.link_to(node)
            previous = node
        # الخرج متشابك بنوع الدخل، فيرجع مصفوفة (عينات، قنوات) مباشرة
        out_format = graph.add(
            "aformat",
            f"sample_fmts={fmt}:channel_layouts={self._layout}:sample_rates={self.out_rate}",
        )
        previous.link_to(out_format)
        sink = graph.add("abuffersink")
        out_format.link_to(sink)
        graph.configure()
        self._graph = graph

    def push(self, chunk):
        """chunk: مصفوفة (عينات، قنوات) بنوع السلسلة."""
        if not len(chunk):
            return self._empty()
        frame = self._av.AudioFrame.from_ndarray(
            np.ascontiguousarray(chunk, dtype=self.dtype).reshape(1, -1),
            format=self._fmt, layout=self._layout,
        )
        frame.sample_rate = self.sample_rate
        frame.pts = self._pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._pts += len(chunk)
        self._graph.push(frame)
        return self._pull()

    def flush(self):
        """ما بقي محتجزًا في الفلاتر بعد آخر كتلة."""
        if self._flushed:
            return self._empty()
        self._flushed = True
        try:
            self._graph.push(None)
        except Exception:
            return self._empty()
        return self._pull()

    def _empty(self):
        return np.zeros((0, self.channels), dtype=self.dtype)

    def _pull(self):
        av = self._av
        parts = []
        while True:
            try:
                frame = self._graph.pull()
            except (av.error.BlockingIOError, av.error.EOFError):
                break
            parts.append(frame.to_ndarray().reshape(-1, self.channels))
        if not parts:
            return self._empty()
        return np.concatenate(parts).astype(self.dtype, copy=False)


def rate_converter(capture_rate, target_rate, channels, dtype):
    """
    محوّل من معدل الالتقاط لمعدل الملف.

    بعض المايكات لا تقبل الوضع الحصري إلا بمعدلها الأصلي (مايك USB على
    جهاز التطوير: 192000 فقط). فنلتقط به ونحوّل هنا مرة واحدة. مرشح
    بطول 64 يكتم ما فوق نصف المعدل الجديد بأكثر من 100 ديسيبل، فلا
    يرتد الصوت العالي التردد داخل المسموع.
    """
    return FilterChain(
        capture_rate, channels, dtype,
        [("aresample", f"{int(target_rate)}:filter_size=64")],
        out_rate=target_rate,
    )
