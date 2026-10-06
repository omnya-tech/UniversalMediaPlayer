# -*- coding: utf-8 -*-
"""
تحسين صوت المايكروفون أثناء التسجيل.

بفلاتر FFmpeg الموجودة أصلًا داخل PyAV (لا مكتبة إضافية ولا برنامج خارجي،
فيعمل في النسخة المبنية بلا بايثون). سريعة جدًا: ثانية صوت في أقل من 10
مللي ثانية على جهاز التطوير.

المستويات:

    off      بلا أي معالجة: الصوت كما خرج من كرت الصوت.
    clean    تنقية: يزيل الطنين المنخفض تحت 80 هرتز (اهتزاز المكتب،
             مروحة الجهاز، صوت المسك باليد) وإزاحة التيار المستمر، ويمنع
             التشبّع بمحدد ناعم بدل أن تُقص قمم الموجة. لا يمس الكلام نفسه:
             أخفض صوت رجالي فوق 85 هرتز تقريبًا.
    denoise  التنقية ومعها تقليل الضوضاء الثابتة (وشيش المايكروفون،
             التكييف) بقدر معتدل. أقوى من ذلك يجعل الصوت معدنيًا.

يُطبَّق على المايكروفون وحده: صوت النظام (الموسيقى مثلًا) فيه جهير حقيقي
تحت 80 هرتز لا يجوز حذفه.
"""

from fractions import Fraction

import numpy as np

ENHANCE_LEVELS = ("off", "clean", "denoise")
DEFAULT_ENHANCE_LEVEL = "clean"

# حد القطع للطنين المنخفض بالهرتز
_HIGHPASS_HZ = 80
# سقف المحدد: نحو 0.4 ديسيبل تحت أقصى قيمة، فلا تصل الموجة للقص
_LIMIT = 0.95
# تقليل الضوضاء بالديسيبل، وأرضيتها المتوقعة
_NOISE_REDUCTION_DB = 12
_NOISE_FLOOR_DB = -50


def _filters_for(level):
    # مرشحان متتاليان (أربع درجات): واحد وحده يترك ربع الطنين عند 40 هرتز
    chain = [("highpass", f"f={_HIGHPASS_HZ}:poles=2"), ("highpass", f"f={_HIGHPASS_HZ}:poles=2")]
    if level == "denoise":
        chain.append(("afftdn", f"nr={_NOISE_REDUCTION_DB}:nf={_NOISE_FLOOR_DB}"))
    # level=false: المحدد لا يرفع الصوت الهادئ، فقط يمسك القمم
    chain.append(("alimiter", f"limit={_LIMIT}:level=false:attack=5:release=50"))
    return chain


class VoiceEnhancer:
    """
    يمرر كتل الصوت الصحيحة (int16 أو int32) عبر سلسلة الفلاتر.

    الفلاتر قد تحتجز بعض العينات (تقليل الضوضاء يعمل على نوافذ)، فما
    يخرج من process قد يكون أقل مما دخل أو أكثر؛ وflush في آخر التسجيل
    يُخرج الباقي. المجموع يساوي ما دخل.
    """

    def __init__(self, sample_rate, channels, level=DEFAULT_ENHANCE_LEVEL):
        import av
        from av.filter import Graph

        self._av = av
        self.level = level
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self._layout = "mono" if self.channels == 1 else "stereo"
        self._pts = 0
        self._dtype = None
        self._max_abs = None

        graph = Graph()
        source = graph.add_abuffer(format="flt", sample_rate=self.sample_rate, layout=self._layout)
        previous = source
        for name, args in _filters_for(level):
            node = graph.add(name, args)
            previous.link_to(node)
            previous = node
        # الخرج بنفس الصيغة المتشابكة، فيرجع مصفوفة (عينات، قنوات) مباشرة
        out_format = graph.add("aformat", f"sample_fmts=flt:channel_layouts={self._layout}")
        previous.link_to(out_format)
        sink = graph.add("abuffersink")
        out_format.link_to(sink)
        graph.configure()
        self._graph = graph

    @staticmethod
    def is_active(level):
        return level in ENHANCE_LEVELS and level != "off"

    def process(self, chunk, max_abs):
        """chunk: مصفوفة (عينات، قنوات) صحيحة. يرجع مصفوفة بنفس النوع."""
        self._dtype = chunk.dtype
        self._max_abs = max_abs
        if not len(chunk):
            return chunk
        samples = (chunk.astype(np.float32) / max_abs).reshape(1, -1)
        frame = self._av.AudioFrame.from_ndarray(samples, format="flt", layout=self._layout)
        frame.sample_rate = self.sample_rate
        frame.pts = self._pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._pts += len(chunk)
        self._graph.push(frame)
        return self._pull()

    def flush(self):
        """ما بقي محتجزًا في الفلاتر بعد آخر كتلة."""
        if self._dtype is None:
            return None
        try:
            self._graph.push(None)
        except Exception:
            return None
        return self._pull()

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
            return np.zeros((0, self.channels), dtype=self._dtype)
        data = np.concatenate(parts) * self._max_abs
        np.clip(data, -self._max_abs, self._max_abs - 1.0, out=data)
        return data.astype(self._dtype)
