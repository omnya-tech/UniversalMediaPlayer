# -*- coding: utf-8 -*-
"""
دمج جهازين في تسجيل واحد (المايكروفون وصوت النظام مثلًا): أخذ عيّنات الجهاز
الثاني بالعدد المطلوب بالضبط من مخزن، وموازنة المسارين ودمجهما.

نُقلت كما هي من core/audio_recorder.py.
"""

import queue
import threading
import time

import numpy as np


class DualInputMixin:
    """دمج الجهاز الثاني مع الأول."""

    # بعد الموازنة كل مسار عند المستوى المستهدف، فالنص بيخلّي المجموع
    # تحت السقف
    _MIX_GAIN = 0.5

    # أقصى انتظار لصوت الجهاز الثاني قبل الكتابة بدونه (بالثواني)، وأقصى
    # ما يتراكم منه قبل أن يُقصّ الزائد: الجهازان بساعتين مختلفتين، فأحدهما
    # يسبق الآخر ببطء
    _SECONDARY_WAIT = 0.1
    _SECONDARY_MAX_BACKLOG = 0.3
    _SECONDARY_KEEP_BACKLOG = 0.1

    def _reset_alignment(self):
        # ما وصل من الأول وما أخذه الكاتب منه (بمعدل الالتقاط)، وهل بدأ الثاني،
        # وكم كتب الكاتب صمتًا مكانه قبل أن يبدأ (بعيّنات الملف)
        self._pri_frames_in = 0
        self._pri_frames_taken = 0
        self._sec_started = False
        self._sec_prefilled = 0
        self._align_lock = threading.Lock()

    def _secondary_lead(self, frames):
        """
        صمت يسبق أول كتلة من الثاني: ما سجّله الأول قبلها، ناقص ما كتبه
        الكاتب صمتًا مكانه قبل أن يبدأ (وإلا حُسبت الفترة نفسها مرتين).
        """
        with self._align_lock:
            self._sec_started = True
            return self._primary_frames_in_file_rate() - frames - self._sec_prefilled

    def _capture_to_file_ratio(self):
        capture = getattr(self, "_capture_rate", None) or self._sample_rate or 48000
        return (self._sample_rate or capture) / capture

    def _primary_frames_in_file_rate(self):
        """ما وصل من الأول منذ بدء التسجيل، بعيّنات الملف (والثاني بمعدل الملف)."""
        return int(round(self._pri_frames_in * self._capture_to_file_ratio()))

    def _primary_pending_frames(self):
        """ما وصل من الأول ولم يأخذه الكاتب بعد، بعيّنات الملف."""
        pending = max(0, self._pri_frames_in - self._pri_frames_taken)
        return int(round(pending * self._capture_to_file_ratio()))

    def _take_secondary(self, count):
        """
        بالضبط count عينة من الجهاز الثاني، لتُدمج مع مثلها من الأول.

        الجهازان يرسلان كتلًا بأحجام وإيقاعات مختلفة. الكود القديم كان
        يدمج كتلة بكتلة: لو لم تكن كتلة الثاني جاهزة في اللحظة نفسها كُتب
        الأول وحده بمستوى كامل، والمدموج يُكتب بنصف المستوى، فكان صوت
        المايكروفون يرتفع وينخفض كل عشر مللي ثوانٍ تقريبًا. هذا ما وصفه
        مستخدمون بانقطاعات قصيرة وتشويه. والكتل المختلفة الأطوال كانت
        تُكمَّل بصمت في وسط التسجيل.

        الآن عينات الثاني تتجمع في مخزن، ويؤخذ منه العدد المطلوب بالضبط.
        لو نقص ينتظر قليلًا، ولو بقي ناقصًا (جهاز توقف) يكمّل بصمت ويُحسب
        ذلك في السجل. ولو تراكم أكثر من اللازم (ساعة الثاني أسرع) يُقصّ
        الزائد مرة واحدة بدل أن يتأخر صوته عن الأول باستمرار.
        """
        with self._align_lock:
            if not self._sec_started:
                # الثاني لم يبدأ بعد: صمت مكانه بلا انتظار، ويُخصم من صمت بدايته
                self._sec_prefilled += count
                return np.zeros((count, self._sec_buffer.shape[1]), dtype=self._sec_buffer.dtype)

        buffer = self._sec_buffer
        deadline = time.monotonic() + self._SECONDARY_WAIT
        while True:
            parts = [buffer]
            while True:
                try:
                    parts.append(self._queue_sec.get_nowait())
                except queue.Empty:
                    break
            if len(parts) > 1:
                buffer = np.concatenate(parts)
            if len(buffer) >= count or time.monotonic() >= deadline or self._stop_flag.is_set():
                break
            time.sleep(0.005)

        # الثاني سابق للأول فقط بما يزيد على ما لم يُكتب بعد من الأول: مخزن
        # كبير وقت يتأخر الكاتب (أول التسجيل مثلًا) ليس سبقًا، وقصّه كان
        # سيُفسد المحاذاة (شوف _audio_callback_sec)
        rate = self._sample_rate or 48000
        ahead = len(buffer) - count - self._primary_pending_frames()
        if ahead > rate * self._SECONDARY_MAX_BACKLOG:
            excess = ahead - int(rate * self._SECONDARY_KEEP_BACKLOG)
            buffer = buffer[excess:]
            self._sec_overruns += 1

        taken = buffer[:count]
        self._sec_buffer = buffer[count:]
        if len(taken) < count:
            # بعد الإيقاف أُغلق الجهازان، وما بقي من الأول بلا مقابل متوقَّع
            if not self._stop_flag.is_set():
                self._sec_underruns += 1
            padding = np.zeros((count - len(taken), buffer.shape[1]), dtype=buffer.dtype)
            taken = np.concatenate([taken, padding])
        return taken

    def _mix_audio_chunks(self, c1, c2):
        """
        يدمج المسارين متوازنين، بلا قصّ وبلا فقدان عيّنات.

        الكتلتان بيوصلوا بأطوال مختلفة: الجهازان مستقلان وكل واحد بيدّي
        كتله بإيقاعه. الكود القديم كان بياخد الأقصر منهما، فأي زيادة في
        المسار الأساسي كانت **بتترمي** - يعني قطع من صوت المستخدم نفسه
        بتضيع. دلوقتي بنمدّ الأقصر بصمت بدل ما نقصّ الأطول.

        والتوازن: كل مسار بياخد معامله من مستواه الفعلي، فالمايك ما
        يضيعش تحت الموسيقى ولا العكس. القياس على حالات واقعية أظهر
        فرقًا يوصل أربعة وعشرين ديسيبل بين المصدرين.
        """
        len1, len2 = len(c1), len(c2)
        length = max(len1, len2)

        f1 = np.zeros((length, c1.shape[1]), dtype=np.float32)
        f1[:len1] = c1
        f2 = np.zeros((length, c1.shape[1]), dtype=np.float32)
        # الثانوي ممكن يجي بقنوات أكتر من الأساسي
        usable = min(c2.shape[1], c1.shape[1])
        f2[:len2, :usable] = c2[:, :usable]

        if self._balance_enabled:
            rate = self._sample_rate or 48000
            if len1:
                f1 *= self._balance_pri.update(c1, self._max_abs, rate)
            if len2:
                f2 *= self._balance_sec.update(c2, self._max_abs, rate)

        mixed = (f1 + f2) * self._MIX_GAIN
        np.clip(mixed, -self._max_abs, self._max_abs - 1.0, out=mixed)
        return mixed.astype(self._dtype)
