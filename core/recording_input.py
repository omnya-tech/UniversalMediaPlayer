# -*- coding: utf-8 -*-
"""
فتح جهاز الإدخال للتسجيل: الوضع الحصري بمعدل الطلب ثم بمعدل الجهاز الأصلي،
ثم المحاولات المتدرّجة بالوضع المشترك، وانتظار أول كتلة، ورسائل الفشل
المفهومة.

نُقلت كما هي من core/audio_recorder.py.
"""

import time

import sounddevice as sd

from core.audio_devices import wasapi_exclusive_settings, wasapi_shared_settings
from core.recording_common import FIRST_BLOCK_TIMEOUT, RecorderError
from core.logging_setup import configure_logging

_logger = configure_logging()


class InputDeviceMixin:
    """فتح جهاز الإدخال ومحاولاته."""

    def _input_attempts(self, sample_rate, channels, native_rate=None):
        """
        الإعدادات اللي بنجرّبها بالترتيب، من الأقرب لطلب المستخدم للأبسط.

        فتح جهاز الصوت بيفشل لأسباب كتير مالهاش علاقة بالإعداد نفسه:
        الجهاز مشغول لحظتها، أو السواقة في حالة انتقالية (شائع مع
        البلوتوث)، أو ضغط ذاكرة. وبلاغ مستخدم وصل بـ:
            Insufficient memory [PaErrorCode -9992]
        وما قدرناش نعيد إنتاجه بأي تركيبة - يعني حالة عابرة.

        الاستسلام من أول محاولة بيحوّل حالة عابرة لعطل كامل. التنازل
        عن جودة الالتقاط أرخص بكتير من إن المستخدم ما يسجّلش خالص.
        """
        shared = wasapi_shared_settings()
        seen = set()
        # الوضع الحصري أولًا لو طُلب: البرنامج يكلّم كرت الصوت مباشرة بلا
        # محرك ويندوز في الوسط، فلا خلط ولا تحويل معدل ولا «تحسينات»
        # النظام. بالمعدل المطلوب، ثم بمعدل الجهاز الأصلي ويُحوَّل الصوت
        # للمطلوب داخل البرنامج: مايك USB على جهاز التطوير لا يقبل الحصري
        # إلا بـ192000، فكان يرجع للمشترك دائمًا. وإلا فالمشترك
        if self.exclusive_requested:
            exclusive = wasapi_exclusive_settings()
            if exclusive is not None:
                for rate in (sample_rate, native_rate):
                    for chans in (channels, 1):
                        key = (rate, chans, "exclusive")
                        if rate and key not in seen:
                            seen.add(key)
                            yield rate, chans, exclusive
        for rate in (sample_rate, 48000, 44100, 16000):
            for chans in (channels, 1):
                for extra in (None, shared):
                    key = (rate, chans, extra is not None)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield rate, chans, extra

    # مدة قياس الوضع الحصري وأقصى انحراف مقبول عن المعدل المعلن
    _EXCLUSIVE_PROBE_SECONDS = 0.6
    _EXCLUSIVE_RATE_TOLERANCE = 0.03

    def _exclusive_rate_ok(self, device_index, rate, chans, extra):
        """
        يقيس ما يرسله الجهاز فعلًا في الوضع الحصري قبل التسجيل.

        بعض التعريفات تقبل الحصري ثم ترسل بمعدل غير المعلن أو تكرر
        الكتل: مايك Realtek على جهاز التطوير أعلن 48000 وأرسل نحو 85000
        عينة في الثانية، فخرج التسجيل أطول من الحقيقة ومشوّهًا. الفحص نصف
        ثانية، والانحراف فوق 3% يعني الرجوع للوضع المشترك.
        """
        frames = [0]
        first = [None]

        def count(indata, frame_count, time_info, status):
            if first[0] is None:
                first[0] = time.perf_counter()
                return
            frames[0] += frame_count

        try:
            with sd.InputStream(device=device_index, samplerate=rate, channels=chans,
                                dtype=self._dtype, callback=count, extra_settings=extra):
                deadline = time.perf_counter() + FIRST_BLOCK_TIMEOUT
                while first[0] is None and time.perf_counter() < deadline:
                    time.sleep(0.01)
                if first[0] is None:
                    return False
                time.sleep(self._EXCLUSIVE_PROBE_SECONDS)
                elapsed = time.perf_counter() - first[0]
        except Exception as exc:
            _logger.info("الوضع الحصري رفض %d هرتز/%d قناة: %s", int(rate), chans, exc)
            return False
        measured = frames[0] / elapsed if elapsed > 0 else 0
        ok = abs(measured - rate) <= rate * self._EXCLUSIVE_RATE_TOLERANCE
        if not ok:
            _logger.warning("الوضع الحصري أرسل %d عينة/ث بدل %d، الرجوع للمشترك",
                            int(measured), int(rate))
        return ok

    def _open_input_with_fallbacks(self, device_index, sample_rate, channels):
        """بيرجّع (نجح؟، آخر خطأ)."""
        last_error = None
        wanted = (sample_rate, channels)
        try:
            native_rate = int(sd.query_devices(device_index).get("default_samplerate") or 0)
        except Exception:
            native_rate = 0

        for rate, chans, extra in self._input_attempts(sample_rate, channels, native_rate):
            if getattr(extra, "_exclusive", False) and not self._exclusive_rate_ok(
                    device_index, rate, chans, extra):
                continue
            try:
                self._stream = sd.InputStream(
                    device=device_index,
                    samplerate=rate,
                    channels=chans,
                    dtype=self._dtype,
                    callback=self._audio_callback_pri,
                    extra_settings=extra,
                )
                self._stream.start()
                if not self._wait_for_first_block() and getattr(extra, "_exclusive", False):
                    # جهاز قبل الحصري ولم يرسل شيئًا: نجرّب المشترك
                    raise RecorderError("exclusive stream sent no audio")
            except Exception as exc:
                last_error = exc
                if self._stream is not None:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                self._stream = None
                continue

            self.used_exclusive = bool(getattr(extra, "_exclusive", False))
            if self.exclusive_requested and not self.used_exclusive:
                _logger.warning("كرت الصوت رفض الوضع الحصري بكل المعدلات، التسجيل بالمشترك")

            # الحصري بمعدل الجهاز ليس تنازلًا: الصوت يتحوّل للمطلوب بعد الالتقاط
            if (rate, chans) != wanted and not (self.used_exclusive and chans == channels):
                _logger.warning(
                    "تعذّر فتح الجهاز بـ%d هرتز/%d قناة، اتفتح بـ%d/%d بدلها",
                    sample_rate, channels, rate, chans,
                )
            return True, None

        return False, last_error

    def _describe_open_failure(self, error):
        """
        رسالة يفهمها المستخدم، مش نص PortAudio الخام.

        "Insufficient memory" مضلّلة: على ويندوز بتطلع والجهاز مشغول أو
        سواقته لسه بتصحى، مش لأن الذاكرة خلصت فعلًا. والمستخدم اللي
        بيقراها بيدوّر في المكان الغلط.
        """
        text = str(error or "")
        if "-9992" in text or "Insufficient memory" in text:
            key, fallback = ("rec_err_device_busy",
                             "الجهاز مشغول أو لسه بيجهّز. اقفل أي برنامج تاني بيستعمل "
                             "المايكروفون وحاول تاني، أو اختر جهازًا آخر من القائمة.")
            # (الرسالة دي بتطلع لما برنامج تاني ماسك الجهاز حصريًا)
        elif ("-9996" in text or "Invalid device" in text
              or "querying device" in text):
            key, fallback = ("rec_err_device_gone",
                             "الجهاز ده مش متاح دلوقتي. لو فصلته، وصّله تاني أو اختر "
                             "جهازًا آخر ثم أعد فتح النافذة.")
            # (جهاز اتفصل بعد ما القائمة اتملت)
        elif "Invalid number of channels" in text:
            key, fallback = ("rec_err_device_channels",
                             "الجهاز ده ما بيدعمش عدد القنوات المختار. جرّب أحادي (Mono).")
            # (بيحصل لما المحاولات كلها اتجرّبت وفضل الخطأ ده الأخير)
            # (المحاولات بتنزل لقناة واحدة، فده نادر)
        else:
            return (self.tr.t("rec_err_open_primary", error=error) if self.tr
                    else f"تعذر فتح جهاز الإدخال الرئيسي: {error}")
        return self.tr.t(key) if self.tr else fallback

    def _wait_for_first_block(self):
        """
        يستنى الجهاز يبدأ يرسل فعلًا قبل ما نقول للمستخدم إن التسجيل بدأ.

        أغلب الأجهزة بترسل في أقل من عشر مللي ثانية. البلوتوث بياخد
        أكتر من ثانية ونص، ومن غير الانتظار ده كلام المستخدم في الفترة
        دي بيضيع وهو مش عارف.

        بيرجّع True لو الجهاز بدأ، وFalse لو المهلة خلصت - والحالة
        التانية معناها إن الجهاز مش بيرسل أصلًا.
        """
        started = time.time()
        arrived = self._first_block.wait(FIRST_BLOCK_TIMEOUT)
        self.warmup_seconds = time.time() - started
        if not arrived:
            _logger.warning(
                "الجهاز ما بعتش أي صوت خلال %.1f ثانية من فتح المجرى",
                FIRST_BLOCK_TIMEOUT)
        elif self.warmup_seconds > 0.25:
            _logger.info("الجهاز استغرق %.2f ثانية علشان يبدأ الإرسال",
                         self.warmup_seconds)
        return arrived
