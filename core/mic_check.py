# -*- coding: utf-8 -*-
"""
تشخيص جودة المايكروفون من تسجيل قصير.

ليه موجود: مؤشر مستوى الصوت بصري، فالمستخدم الكفيف ماعندوش أي طريقة
يعرف بيها إن مستوى مايكه عالي أو واطي **قبل** ما يخلّص تسجيل كامل. حصلت
فعلًا: مستخدم سجّل ثلاث دقائق، والمستوى كان عالي فالموجة اصطدمت بسقف
الـ 16 بت واتفلطحت، واكتشف بعد ما خلّص إن الصوت "مش نقي".

الوحدة دي بتاخد العيّنات الخام وترجّع حكمًا نصيًا جاهزًا للنطق وللنسخ -
سطر واحد المستخدم يقدر يلزقه في رسالة دعم من غير ما يفهم أي رقم فيه.

مفصولة عن الواجهة عن قصد: المنطق ده يتختبر بلا فتح نوافذ ولا أجهزة صوت.
"""

import numpy as np

# العيّنة عند هذه النسبة من الحد الأقصى أو فوقها تُعَدّ متشبّعة
# (32000 من 32768 في الستة عشر بت).
CLIP_RATIO = 0.976

# متوسط مستوى تحته يُعَدّ الصوت واطيًا.
LOW_RMS_RATIO = 0.02

# نطاق الذروة المريح: فوق الحد الأدنى مسموع، وتحت الأقصى هامش أمان.
GOOD_PEAK_MIN = 0.35
GOOD_PEAK_MAX = 0.92

# نسبة العيّنات المتشبّعة (بالمئة) التي يبدأ عندها التحذير.
CLIP_PERCENT_WARN = 0.01


class MicVerdict:
    """نتيجة الفحص: رمز + رسالة جاهزة للنطق + سطر تقني للنسخ."""

    OK = "ok"
    CLIPPING = "clipping"
    TOO_LOW = "too_low"
    SILENT = "silent"

    def __init__(self, code, peak_ratio, rms_ratio, clip_events, clip_percent):
        self.code = code
        self.peak_ratio = peak_ratio
        self.rms_ratio = rms_ratio
        self.clip_events = clip_events
        self.clip_percent = clip_percent

    @property
    def peak_percent(self) -> int:
        return int(round(self.peak_ratio * 100))

    @property
    def rms_percent(self) -> int:
        return int(round(self.rms_ratio * 100))


def analyse(samples, max_abs: float, clip_events: int = 0) -> MicVerdict:
    """
    يفحص عيّنات تسجيل الاختبار.

    `samples`  مصفوفة numpy (أحادية أو ثنائية القنوات)
    `max_abs`  أقصى قيمة لعمق البت (32768 لستة عشر بت)
    `clip_events` عدد أحداث التشبّع اللي رصدها المسجّل أثناء التسجيل
    """
    if samples is None or len(samples) == 0:
        return MicVerdict(MicVerdict.SILENT, 0.0, 0.0, 0, 0.0)

    data = np.asarray(samples, dtype=np.float64)
    if data.ndim > 1:
        data = data.reshape(-1)

    peak_ratio = float(np.max(np.abs(data))) / max_abs
    rms_ratio = float(np.sqrt(np.mean(np.square(data)))) / max_abs

    threshold = max_abs * CLIP_RATIO
    clipped = int(np.count_nonzero(np.abs(data) >= threshold))
    clip_percent = clipped / len(data) * 100.0

    if rms_ratio < 0.002:
        code = MicVerdict.SILENT
    elif clip_events > 0 and clip_percent >= CLIP_PERCENT_WARN:
        code = MicVerdict.CLIPPING
    elif rms_ratio < LOW_RMS_RATIO or peak_ratio < GOOD_PEAK_MIN:
        code = MicVerdict.TOO_LOW
    else:
        code = MicVerdict.OK

    return MicVerdict(code, peak_ratio, rms_ratio, clip_events, clip_percent)


def verdict_message(verdict: MicVerdict, tr) -> str:
    """رسالة الحكم بلغة المستخدم - دي اللي بتتنطق وبتتعرض."""
    key = {
        MicVerdict.OK: "mic_check_result_ok",
        MicVerdict.CLIPPING: "mic_check_result_clipping",
        MicVerdict.TOO_LOW: "mic_check_result_low",
        MicVerdict.SILENT: "mic_check_result_silent",
    }[verdict.code]
    from i18n.plural import count_phrase

    return tr.t(key, peak=verdict.peak_percent, level=verdict.rms_percent,
                spots=count_phrase(tr, "count_spots", verdict.clip_events))


def technical_line(verdict: MicVerdict, device_name: str, sample_rate: int,
                   channels: int, bit_depth: int, app_version: str) -> str:
    """
    سطر واحد للنسخ في رسالة دعم.

    بلا اسم جهاز الكمبيوتر ولا اسم المستخدم ولا مسارات: السطر ده الغالب
    إنه هيتنشر في مجموعة عامة، فما يحملش أي شيء يعرّف صاحبه.
    """
    return (
        f"Omnya {app_version} | mic={device_name} | "
        f"{sample_rate}Hz/{channels}ch/{bit_depth}bit | "
        f"peak={verdict.peak_percent}% rms={verdict.rms_percent}% | "
        f"clip_events={verdict.clip_events} clip={verdict.clip_percent:.3f}% | "
        f"verdict={verdict.code}"
    )
