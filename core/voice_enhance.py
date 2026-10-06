# -*- coding: utf-8 -*-
"""
تحسين صوت المايكروفون أثناء التسجيل.

الترشيح بفلاتر FFmpeg الموجودة أصلًا داخل PyAV، وتقليل الضوضاء بـnumpy
(لا مكتبة إضافية ولا برنامج خارجي، فيعمل في النسخة المبنية بلا بايثون).
ثانية الصوت تُعالج في نحو 50 مللي ثانية على جهاز التطوير.

المستويات:

    off      بلا أي معالجة: الصوت كما خرج من كرت الصوت.
    clean    تنقية: يزيل الطنين المنخفض تحت 80 هرتز (اهتزاز المكتب،
             مروحة الجهاز، صوت المسك باليد) وإزاحة التيار المستمر، ويمنع
             التشبّع بمحدد ناعم بدل أن تُقص قمم الموجة. لا يمس الكلام نفسه:
             أخفض صوت رجالي فوق 85 هرتز تقريبًا.
    denoise  التنقية ومعها تقليل الضوضاء الثابتة (وشيش المايكروفون،
             التكييف، المروحة، طنين الكهرباء) نحو 11 ديسيبل في سكتات الكلام.
             أقوى من ذلك يجعل الصوت معدنيًا.

يُطبَّق على المايكروفون وحده: صوت النظام (الموسيقى مثلًا) فيه جهير حقيقي
تحت 80 هرتز لا يجوز حذفه.
"""

import numpy as np

from core.audio_filters import FilterChain

ENHANCE_LEVELS = ("off", "clean", "denoise")
DEFAULT_ENHANCE_LEVEL = "clean"

# حد القطع للطنين المنخفض بالهرتز
_HIGHPASS_HZ = 80
# سقف المحدد: نحو 0.4 ديسيبل تحت أقصى قيمة، فلا تصل الموجة للقص
_LIMIT = 0.95


def _highpass_filters():
    # مرشحان متتاليان (أربع درجات): واحد وحده يترك ربع الطنين عند 40 هرتز
    return [("highpass", f"f={_HIGHPASS_HZ}:poles=2")] * 2


def _limiter_filters():
    # level=false: المحدد لا يرفع الصوت الهادئ، فقط يمسك القمم
    return [("alimiter", f"limit={_LIMIT}:level=false:attack=5:release=50")]


class NoiseReducer:
    """
    تقليل الضوضاء الثابتة بمرشح Wiener في مجال التردد.

    الكود القديم كان يستعمل afftdn من FFmpeg بأرضية ضوضاء ثابتة عند -50
    ديسيبل. مايك USB على جهاز التطوير ضوضاؤه عند -38، فاعتبرها afftdn
    كلامًا ولم يخفض منها شيئًا (القياس: صفر ديسيبل). وتتبّعه التلقائي
    للضوضاء (tn) لا يتحرك مع الكتل الصغيرة أثناء التسجيل.

    هنا الضوضاء تُقاس من الصوت نفسه باستمرار لكل تردد: أدنى طاقة خلال
    آخر 2.4 ثانية (طريقة «الإحصاء الأدنى»)، لأن الكلام فيه سكتات قصيرة
    والضوضاء الثابتة لا تسكت. فيتكيف مع أي مايك وأي غرفة بلا ضبط.

    القياس على كلام مع ضوضاء المايك الحقيقية: الضوضاء في السكتات تنخفض
    نحو 11 ديسيبل، وتشويه الكلام -23 ديسيبل مع ضوضاء عالية و-40 (غير
    مسموع) مع ضوضاء هادئة.
    """

    # أقصى خفض للصوت في أي تردد: أكثر منه يترك «نغمات» متقطعة في السكتات
    REDUCTION_DB = 15.0
    # مدة الإطار بالثواني (تُقرّب لقوة 2): 21 مللي تفصل طنين 50 عن 100 هرتز
    _FRAME_SECONDS = 0.021
    # الإحصاء الأدنى: ثماني نوافذ فرعية كل منها 0.3 ثانية. نافذة 1.6 ثانية
    # كانت تحسب نهاية الجمل الطويلة بلا سكتة ضوضاءً فتخفضها
    _SUB_WINDOW_SECONDS = 0.3
    _SUB_WINDOWS = 8
    # الأدنى أقل من متوسط الضوضاء، فيُرفع بهذا المعامل
    _BIAS = 2.0
    # أقصى سرعة لارتفاع تقدير الضوضاء (ديسيبل في الثانية): كلام متصل بلا
    # سكتة لا يُحسب ضوضاء، وضوضاء جديدة حقيقية (مروحة اشتغلت) تُلحق خلال ثوانٍ
    _RISE_DB_PER_SECOND = 6.0
    # تنعيم الطيف قبل البحث عن الأدنى، ونسبة «القرار الموجّه» لنسبة
    # الإشارة للضوضاء (تمنع النغمات المتقطعة)
    _POWER_SMOOTHING = 0.8
    _DECISION_DIRECTED = 0.98

    def __init__(self, sample_rate, channels):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        n = 1 << int(round(np.log2(self.sample_rate * self._FRAME_SECONDS)))
        self._n = n
        self._hop = n // 2
        # جذر نافذة Hann الدورية: تحليلًا وتركيبًا، ومجموعها مع تداخل النصف واحد
        self._window = np.sqrt(np.hanning(n + 1)[:n]).astype(np.float32)[:, None]
        self._gain_floor = 10 ** (-self.REDUCTION_DB / 20)
        frames_per_second = self.sample_rate / self._hop
        self._sub_length = max(1, int(round(self._SUB_WINDOW_SECONDS * frames_per_second)))
        self._max_rise = 10 ** (self._RISE_DB_PER_SECOND / 10 / frames_per_second)

        self._pending = np.zeros((0, self.channels), np.float32)
        self._overlap = np.zeros((n, self.channels), np.float32)
        self._samples_in = 0
        self._samples_out = 0
        self._power = None
        self._noise = None
        self._current_min = None
        self._sub_minima = []
        self._sub_count = 0
        self._previous_snr = None

    def _gains(self, power):
        """كسب كل تردد في الإطار، من طاقته وتقدير الضوضاء."""
        if self._power is None:
            self._power = power.copy()
            self._current_min = power.copy()
            self._noise = np.maximum(power * self._BIAS, 1e-20)
            self._previous_snr = np.ones_like(power)

        a = self._POWER_SMOOTHING
        self._power = a * self._power + (1 - a) * power
        self._current_min = np.minimum(self._current_min, self._power)
        self._sub_count += 1
        if self._sub_count >= self._sub_length:
            self._sub_minima = (self._sub_minima + [self._current_min])[-self._SUB_WINDOWS:]
            self._current_min = self._power.copy()
            self._sub_count = 0
        tracked = self._current_min
        if self._sub_minima:
            tracked = np.minimum(np.min(self._sub_minima, axis=0), tracked)
        self._noise = np.maximum(
            np.minimum(tracked * self._BIAS, self._noise * self._max_rise), 1e-20)

        snr_now = power / self._noise
        d = self._DECISION_DIRECTED
        prior = d * self._previous_snr + (1 - d) * np.maximum(snr_now - 1, 0)
        gain = np.maximum(prior / (1 + prior), self._gain_floor)
        self._previous_snr = gain ** 2 * snr_now
        return gain

    def _frame(self, block):
        spectrum = np.fft.rfft(block * self._window, axis=0)
        # كسب واحد لكل القنوات: صورة الستيريو لا تتحرك
        power = np.mean(np.abs(spectrum) ** 2, axis=1)
        gain = self._gains(power)[:, None]
        return np.fft.irfft(spectrum * gain, n=self._n, axis=0).astype(np.float32) * self._window

    def process(self, chunk):
        """chunk: مصفوفة float32 (عينات، قنوات). الخرج قد يتأخر عن الدخل إطارًا."""
        self._samples_in += len(chunk)
        self._pending = np.concatenate([self._pending, chunk.astype(np.float32, copy=False)])
        out = []
        while len(self._pending) >= self._n:
            self._overlap += self._frame(self._pending[:self._n])
            out.append(self._overlap[:self._hop].copy())
            self._overlap = np.concatenate(
                [self._overlap[self._hop:], np.zeros((self._hop, self.channels), np.float32)])
            self._pending = self._pending[self._hop:]
        if not out:
            return np.zeros((0, self.channels), np.float32)
        result = np.concatenate(out)
        self._samples_out += len(result)
        return result

    def flush(self):
        """الباقي بعد آخر كتلة، فيساوي مجموع الخرج مجموع الدخل بالضبط."""
        remaining = self._samples_in - self._samples_out
        if remaining <= 0:
            return np.zeros((0, self.channels), np.float32)
        tail = self.process(np.zeros((self._n, self.channels), np.float32))
        self._samples_in -= self._n
        return tail[:remaining]


class VoiceEnhancer:
    """
    يمرر كتل الصوت الصحيحة (int16 أو int32) عبر التنقية وتقليل الضوضاء.

    المراحل قد تحتجز بعض العينات (تقليل الضوضاء يعمل على إطارات)، فما
    يخرج من process قد يكون أقل مما دخل أو أكثر؛ وflush في آخر التسجيل
    يُخرج الباقي. المجموع يساوي ما دخل.
    """

    def __init__(self, sample_rate, channels, level=DEFAULT_ENHANCE_LEVEL):
        self.level = level
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self._dtype = None
        self._max_abs = None
        self._highpass = FilterChain(self.sample_rate, self.channels, "float32", _highpass_filters())
        self._denoiser = NoiseReducer(self.sample_rate, self.channels) if level == "denoise" else None
        self._limiter = FilterChain(self.sample_rate, self.channels, "float32", _limiter_filters())

    @staticmethod
    def is_active(level):
        return level in ENHANCE_LEVELS and level != "off"

    def process(self, chunk, max_abs):
        """chunk: مصفوفة (عينات، قنوات) صحيحة. يرجع مصفوفة بنفس النوع."""
        self._dtype = chunk.dtype
        self._max_abs = max_abs
        if not len(chunk):
            return chunk
        data = self._highpass.push(chunk.astype(np.float32) / max_abs)
        if self._denoiser is not None:
            data = self._denoiser.process(data)
        return self._to_int(self._limiter.push(data))

    def flush(self):
        """ما بقي محتجزًا في المراحل بعد آخر كتلة."""
        if self._dtype is None:
            return None
        data = self._highpass.flush()
        if self._denoiser is not None:
            data = np.concatenate([self._denoiser.process(data), self._denoiser.flush()])
        data = np.concatenate([self._limiter.push(data), self._limiter.flush()])
        return self._to_int(data)

    def _to_int(self, data):
        # بـfloat64: في float32 يُقرَّب سقف int32 لـ2^31 فيفيض للسالب
        data = data.astype(np.float64) * self._max_abs
        np.clip(data, -self._max_abs, self._max_abs - 1.0, out=data)
        return data.astype(self._dtype)
