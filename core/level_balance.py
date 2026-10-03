# -*- coding: utf-8 -*-
"""
موازنة مستوى المسارين في التسجيل المدمج.

المشكلة: المايكروفون وصوت النظام مستوياتهما مختلفة بطبيعتهما. القياس
على حالات واقعية أظهر فرقًا يوصل أربعة وعشرين ديسيبل - يعني صوت
المستخدم بيختفي تحت الموسيقى تمامًا. وجمعهما بمعامل واحد بيثبّت الفرق
ده بدل ما يعالجه.

الحل: كل مسار بياخد معامله الخاص، محسوبًا من مستواه الفعلي عشان
يوصّله لمستوى مستهدف مشترك.

وفيه ثلاث احتياطات لازمة، من غيرها العلاج بيبقى أسوأ من الداء:

  • بوابة صمت: المسار الساكت ما بيتضخّمش. من غيرها، سكوت المستخدم
    بين الجمل بيرفع ضوضاء المايك لمستوى الكلام - وهي أوضح ما تكون
    في التسجيل الهادي.

  • تنعيم بطيء: المعامل بيتحرك على مدى نصف ثانية تقريبًا لا فجأة.
    التغيّر المفاجئ بيسمع كأن الصوت بيتنفّس (pumping).

  • حدود: التضخيم ما بيعدّيش أربع أضعاف والخفض ما بينزلش عن الربع،
    فمسار ميت ما بيتحوّلش لضجيج.
"""

import math

# المستوى المستهدف لكل مسار بالديسيبل تحت الحد الأقصى: مستوى كلام مريح
# يترك هامشًا قبل التشبع عند جمع المسارين.
TARGET_DBFS = -18.0

# ما تحت هذا المستوى يُعَدّ صمتًا فلا يُضخَّم.
SILENCE_DBFS = -50.0

MIN_GAIN = 0.25
MAX_GAIN = 4.0

# الزمن الذي يقطع فيه المعامل معظم المسافة نحو قيمته المطلوبة.
# أقصر منه يُسمَع تنفّسًا، وأطول منه يتأخر عن تغيّر مستوى المتكلم.
# نصف ثانية توازن بين الاثنين.
SMOOTHING_SECONDS = 0.5


def rms_dbfs(samples, max_abs):
    """مستوى الكتلة بالديسيبل تحت الحد الأقصى، أو None لو فاضية."""
    if samples is None or len(samples) == 0:
        return None
    normalized = samples.astype("float64") / max_abs
    mean_square = float((normalized * normalized).mean())
    if mean_square <= 0:
        return None
    return 10.0 * math.log10(mean_square)


class TrackBalancer:
    """
    يحسب معامل مسار واحد ويحرّكه بهدوء.

    الحالة محفوظة بين الكتل عن قصد: المعامل بيتغيّر تدريجيًا، فكل
    كتلة بتبني على اللي قبلها.
    """

    def __init__(self, target_dbfs=TARGET_DBFS, silence_dbfs=SILENCE_DBFS,
                 min_gain=MIN_GAIN, max_gain=MAX_GAIN,
                 smoothing_seconds=SMOOTHING_SECONDS):
        self.target_dbfs = target_dbfs
        self.silence_dbfs = silence_dbfs
        self.min_gain = min_gain
        self.max_gain = max_gain
        self.smoothing_seconds = smoothing_seconds
        self.gain = 1.0

    def update(self, samples, max_abs, sample_rate):
        """يحدّث المعامل من كتلة جديدة ويرجّعه."""
        level = rms_dbfs(samples, max_abs)

        # بوابة الصمت: المعامل يبقى على حاله، فلا تُرفع الضوضاء
        # بين الجمل ولا ينقلب المعامل عند عودة الكلام.
        if level is None or level < self.silence_dbfs:
            return self.gain

        wanted = 10.0 ** ((self.target_dbfs - level) / 20.0)
        wanted = max(self.min_gain, min(self.max_gain, wanted))

        # تنعيم أسّي مستقل عن حجم الكتلة: الكتل الأطول تقطع مسافة أكبر،
        # فيبقى زمن الاستجابة ثابتًا مهما تغيّر حجم الكتلة.
        if sample_rate > 0 and self.smoothing_seconds > 0:
            block_seconds = len(samples) / float(sample_rate)
            step = 1.0 - math.exp(-block_seconds / self.smoothing_seconds)
        else:
            step = 1.0

        self.gain += (wanted - self.gain) * min(1.0, max(0.0, step))
        return self.gain
