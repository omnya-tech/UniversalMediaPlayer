# -*- coding: utf-8 -*-
"""
مسجل صوت من المايكروفون (أو أي جهاز إدخال صوتي متاح على الجهاز)، بتسجيل
مباشر لملف WAV على القرص مع دعم معدلات عينة مرنة، معالجة قنوات ذكية،
ودعم دمج جهازين إدخال معاً (مثل المايكروفون والستيريو ميكس) مع موازنة الصوت لمنع التشويه.
"""

import os
import queue
import threading
import time
import wave

import numpy as np
import sounddevice as sd

from core.audio_devices import wasapi_shared_settings
from core.level_balance import TrackBalancer
from core.logging_setup import configure_logging

_logger = configure_logging()

_BIT_DEPTH_CONFIG = {
    16: {"dtype": "int16", "sample_width": 2, "max_abs": 32768.0},
    32: {"dtype": "int32", "sample_width": 4, "max_abs": 2147483648.0},
}
_DEFAULT_BIT_DEPTH = 16

SUPPORTED_SAMPLE_RATES = (44100, 48000, 96000)

# أقصى انتظار لأول كتلة صوت من الجهاز بالثواني. جهاز اتفتح "بنجاح" بس
# مش بيبعت أي بيانات (سواقة معلّقة، أو مايك USB اتفصل وهو مفتوح) كان
# بيسيب التسجيل شغّال بصمت لحد ما المستخدم يوقفه ويلاقي الملف فاضي.
# ست ثواني كفاية لأبطأ جهاز Bluetooth.
FIRST_BLOCK_TIMEOUT = 6.0

# العيّنة عند النسبة دي من الحد الأقصى أو فوقها تُعَدّ متشبّعة
# (32000 من 32768 في الستة عشر بت).
# نفس القيمة في core/mic_check.py.
_CLIP_RATIO = 0.976

# عدد أحداث التشبّع اللي بعدها بننبّه المستخدم: حدث أو اتنين ممكن
# يبقوا كحّة أو خبطة، لكن التلاتة نمط.
CLIP_EVENTS_THRESHOLD = 3

# حدثين تشبّع بينهم أقل من كده بيتحسبوا حدث واحد: صرخة واحدة بتدّي
# مئات العيّنات المتشبّعة في كتل متتالية، وعدّها كلها كان بيخلي
# الرقم مالوش معنى.
# (بالثواني)
# 50 مللي ثانية = أقصر فاصل بين مقطعين في الكلام العادي.
_CLIP_EVENT_GAP_SEC = 0.05

# أقل عدد عيّنات متتالية عند السقف عشان نعتبرها تشبّع: عيّنة واحدة
# عالية ممكن تبقى قمة حادة طبيعية، لكن تلاتة متتالية معناها إن
# الموجة اتفلطحت فعلًا.
# (من غيرها، أي حرف "ب" أو "ت" قوي كان بيتحسب تشبّع)
_MIN_CLIP_RUN = 3


class RecorderError(Exception):
    pass


def list_input_devices(tr=None):
    """جلب قائمة بأجهزة الإدخال النشطة والجاهزة للتسجيل فقط واستبعاد المفصولة والمعطلة"""
    devices = []
    try:
        hostapis = sd.query_hostapis()
        all_devices = sd.query_devices()
        
        for index, device in enumerate(all_devices):
            max_channels = device.get("max_input_channels", 0)
            if max_channels <= 0:
                continue

            is_active = False
            for test_rate in (44100, 48000, 16000, 22050, 32000, 8000):
                try:
                    sd.check_input_settings(device=index, samplerate=test_rate, channels=1)
                    is_active = True
                    break
                except Exception:
                    continue

            if not is_active:
                continue

            name = device.get("name", f"Device {index}")
            hostapi_index = device.get("hostapi")
            hostapi_name = ""
            if hostapi_index is not None and 0 <= hostapi_index < len(hostapis):
                hostapi_name = hostapis[hostapi_index].get("name", "")
            
            label = f"{name} ({hostapi_name})" if hostapi_name else name
            devices.append((index, label))
            
    except Exception as exc:
        msg = tr.t("rec_err_list_devices", error=exc) if tr else f"تعذر قراءة قائمة أجهزة الإدخال: {exc}"
        raise RecorderError(msg) from exc
    return devices


def get_device_max_input_channels(device_index) -> int:
    try:
        info = sd.query_devices(device_index)
        return int(info.get("max_input_channels", 1))
    except Exception:
        return 1


def get_supported_sample_rates(device_index, channels: int = 1):
    working = []
    for rate in SUPPORTED_SAMPLE_RATES:
        try:
            sd.check_input_settings(device=device_index, samplerate=rate, channels=channels)
            working.append(rate)
        except Exception:
            continue
    return tuple(working) if working else SUPPORTED_SAMPLE_RATES


def get_device_native_sample_rate(device_index):
    """
    معدل العينة اللي الجهاز شغّال عليه أصلًا.

    مهم للجودة: أغلب مايكات ويندوز شغّالة على 48000، وطلب 44100 بيجبر
    محرك الصوت في ويندوز على إعادة تشكيل الإشارة - نظيف على سواقة كويسة،
    وبيطلّع تشويهًا مسموعًا على غيرها. التسجيل بمعدل الجهاز نفسه بيشيل
    الخطوة دي من الطريق تمامًا.

    يرجّع None لو تعذّرت القراءة، فينط المستدعي للافتراضي القديم.
    """
    try:
        info = sd.query_devices(device_index)
        rate = int(round(float(info.get("default_samplerate", 0))))
        return rate if rate > 0 else None
    except Exception:
        return None


def get_default_input_device():
    """
    رقم جهاز الإدخال الافتراضي.

    ملحوظة: sd.default.device نوعها _InputOutputPair لا list ولا tuple،
    فالفحص بـ isinstance كان بيفشل والدالة كانت بترجّع الزوج كله
    ([إدخال، إخراج]) بدل رقم واحد - وأي مستدعي بيمرّره لـ query_devices
    كان بيفشل بصمت.
    """
    try:
        default = sd.default.device
        if isinstance(default, (list, tuple)) or hasattr(default, "__getitem__"):
            return default[0]
        return default
    except Exception:
        return None


class AudioRecorder:
    def __init__(self, on_level=None, on_error=None, tr=None):
        self.on_level = on_level
        self.on_error = on_error
        self.tr = tr

        self._stream = None
        self._stream_sec = None
        self._wave_file = None
        self._queue_pri = queue.Queue(maxsize=200)
        self._queue_sec = queue.Queue(maxsize=200)
        self._writer_thread = None
        self._stop_flag = threading.Event()
        self._first_block = threading.Event()
        # زمن وصول أول كتلة من الجهاز، للسجل وتشخيص الأجهزة البطيئة
        self.warmup_seconds = 0.0
        self._pause_flag = threading.Event()
        self._lock = threading.Lock()

        self._wav_path = None
        self._sample_rate = 44100
        self._channels = 1
        self._stream_channels = 1
        self._bit_depth = _DEFAULT_BIT_DEPTH
        self._dtype = _BIT_DEPTH_CONFIG[_DEFAULT_BIT_DEPTH]["dtype"]
        self._max_abs = _BIT_DEPTH_CONFIG[_DEFAULT_BIT_DEPTH]["max_abs"]
        self._frames_written = 0
        self._is_recording = False
        self._start_time = None
        self._last_recording_had_no_audio = False
        self._has_dual_input = False

        # موازنة مستوى المسارين في التسجيل المدمج: كل مسار بمعامله
        # (شوف core/level_balance.py)
        self._balance_enabled = True
        self._balance_pri = TrackBalancer()
        self._balance_sec = TrackBalancer()

        # رصد التشبّع: عدد العيّنات المتشبّعة وعدد الأحداث، وموضع آخر
        # حدث وطول السلسلة الحالية عشان الحدث اللي بيمتد على أكتر من
        # كتلة يتحسب مرة واحدة.
        # (شوف _track_clipping)
        self._clipped_samples = 0
        self._clip_events = 0
        self._samples_seen = 0
        self._clip_last_sample = -10**9
        self._clip_run = 0

        self._direct_encode = False
        self._out_container = None
        self._out_audio_stream = None
        self._resampler = None
        self._av_format = None
        self._av_layout = None

    @property
    def bit_depth(self) -> int:
        return self._bit_depth

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_paused(self) -> bool:
        return self._pause_flag.is_set()

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def last_recording_had_no_audio(self) -> bool:
        return self._last_recording_had_no_audio

    @property
    def clip_events(self) -> int:
        """عدد المرات اللي دخل فيها الصوت في التشبّع أثناء آخر تسجيل."""
        return self._clip_events

    @property
    def had_clipping(self) -> bool:
        """هل آخر تسجيل فيه تشبّع يستاهل تنبيه المستخدم؟"""
        return self._clip_events >= CLIP_EVENTS_THRESHOLD

    def _track_clipping(self, chunk):
        """
        يعدّ عيّنات التشبّع وأحداثه في بلوك.

        ملحوظة: بنقارن بالحدين موجباً وسالباً بدل np.abs عن قصد - abs
        على int16 بتفيض عند -32768 وترجّع -32768 نفسها، فالمقارنة
        بعدها بتفشل صامتة.
        """
        threshold = self._max_abs * _CLIP_RATIO
        hot = (chunk >= threshold) | (chunk <= -threshold)
        if hot.ndim > 1:
            hot = hot.any(axis=1)

        block_start = self._samples_seen
        self._samples_seen += len(hot)

        count = int(np.count_nonzero(hot))
        if count == 0:
            self._clip_run = 0
            return
        self._clipped_samples += count

        # الحدث بيتحسب عند اكتمال سلسلة متتالية بطول _MIN_CLIP_RUN،
        # والأحداث القريبة من بعض بتندمج في حدث واحد.
        # السلسلة بتكمّل عبر حدود الكتل لأن _clip_run متخزّن في الكائن.
        # (اللفّة دي بتشتغل بس على الكتل اللي فيها تشبّع، فتكلفتها مهملة)
        gap = max(1, int(self._sample_rate * _CLIP_EVENT_GAP_SEC))
        for index, is_hot in enumerate(hot):
            if not is_hot:
                self._clip_run = 0
                continue
            self._clip_run += 1
            if self._clip_run != _MIN_CLIP_RUN:
                continue
            position = block_start + index
            if position - self._clip_last_sample > gap:
                self._clip_events += 1
            self._clip_last_sample = position

    def get_elapsed_seconds(self) -> float:
        if self._sample_rate <= 0:
            return 0.0
        return self._frames_written / float(self._sample_rate)

    def start(
        self,
        device_index,
        sample_rate: int,
        channels: int,
        wav_path: str,
        bit_depth: int = _DEFAULT_BIT_DEPTH,
        target_ext: str = ".wav",
        audio_bitrate: int = 0,
        secondary_device_index=None,
    ):
        if self._is_recording:
            msg = self.tr.t("rec_err_already_recording") if self.tr else "يوجد تسجيل قائم بالفعل"
            raise RecorderError(msg)

        target_ext = (target_ext or ".wav").lower()
        self._direct_encode = target_ext != ".wav"

        bit_depth_config = _BIT_DEPTH_CONFIG.get(bit_depth, _BIT_DEPTH_CONFIG[_DEFAULT_BIT_DEPTH])

        try:
            device_info = sd.query_devices(device_index)
            max_input_channels = int(device_info.get("max_input_channels", 1))
        except Exception:
            max_input_channels = 1

        stream_channels = 1 if max_input_channels <= 1 else min(channels, max_input_channels)

        self._wav_path = wav_path
        self._sample_rate = sample_rate
        self._channels = channels
        self._stream_channels = stream_channels
        self._bit_depth = bit_depth if bit_depth in _BIT_DEPTH_CONFIG else _DEFAULT_BIT_DEPTH
        self._dtype = bit_depth_config["dtype"]
        self._max_abs = bit_depth_config["max_abs"]
        self._frames_written = 0
        self._clipped_samples = 0
        self._clip_events = 0
        self._samples_seen = 0
        self._clip_last_sample = -10**9
        self._clip_run = 0
        # موازنة جديدة لكل تسجيل: معامل التسجيل اللي فات كان على
        # مستوى صوت مختلف، والبدء بيه بيخلي أول ثانية نشاز.
        # (المعامل بيتحرك بهدوء، فالبداية من 1 أسلم)
        # شوف TrackBalancer.
        self._balance_pri = TrackBalancer()
        self._balance_sec = TrackBalancer()

        self._stop_flag.clear()
        self._first_block.clear()
        self.warmup_seconds = 0.0
        self._pause_flag.clear()

        while not self._queue_pri.empty(): self._queue_pri.get_nowait()
        while not self._queue_sec.empty(): self._queue_sec.get_nowait()

        try:
            os.makedirs(os.path.dirname(wav_path) or ".", exist_ok=True)
            if self._direct_encode:
                self._open_direct_encoder(wav_path, target_ext, audio_bitrate)
            else:
                self._wave_file = wave.open(wav_path, "wb")
                self._wave_file.setnchannels(channels)
                self._wave_file.setsampwidth(bit_depth_config["sample_width"])
                self._wave_file.setframerate(sample_rate)
        except RecorderError:
            raise
        except Exception as exc:
            msg = self.tr.t("rec_err_create_file", error=exc) if self.tr else f"تعذر إنشاء ملف التسجيل: {exc}"
            raise RecorderError(msg) from exc

        # 1. فتح جهاز الإدخال الرئيسي (المايك)
        #
        # بمحاولات متدرّجة: المعدل المطلوب أولًا، ثم بإعدادات WASAPI
        # المشتركة، ثم بمعدل الجهاز الأصلي، ثم بقناة واحدة. جهاز بيرفض
        # المعدل اللي اختاره المستخدم كان بيفشل التسجيل كله برسالة
        # فنية، مع إن الجهاز نفسه شغّال تمام بمعدل تاني.
        #
        # (شوف _input_attempts للترتيب، و _describe_open_failure للرسالة)
        opened, last_error = self._open_input_with_fallbacks(
            device_index, sample_rate, stream_channels)

        if not opened:
            self._close_output_on_failure()
            msg = self._describe_open_failure(last_error)
            raise RecorderError(msg) from last_error

        self._sample_rate = self._stream.samplerate
        self._channels = min(self._channels, self._stream.channels)

        # 2. فتح جهاز الإدخال الثانوي (الستيريو ميكس) إن تم اختياره
        self._has_dual_input = False
        self.secondary_error = None
        if secondary_device_index is not None and secondary_device_index != device_index:
            # بنفس معدل الأساسي الفعلي: لو المسارين بمعدلين مختلفين الدمج
            # بيطلّع صوت متسارع أو بطيء.
            # (الأساسي ممكن يكون نزل لمعدل تاني في محاولاته، فالمعدل
            # بيتقرأ من الدفق مش من الطلب)
            sec_error = None
            try:
                sec_info = sd.query_devices(secondary_device_index)
                sec_max_ch = int(sec_info.get("max_input_channels", 1))
                sec_stream_ch = 1 if sec_max_ch <= 1 else min(channels, sec_max_ch)
            except Exception as exc:
                sec_info, sec_stream_ch, sec_error = None, 1, exc

            if sec_info is not None:
                for extra in (None, wasapi_shared_settings()):
                    try:
                        self._stream_sec = sd.InputStream(
                            device=secondary_device_index,
                            samplerate=self._sample_rate,
                            channels=sec_stream_ch,
                            dtype=self._dtype,
                            callback=self._audio_callback_sec,
                            extra_settings=extra,
                        )
                        self._stream_sec.start()
                        self._has_dual_input = True
                        sec_error = None
                        break
                    except Exception as exc:
                        sec_error = exc
                        self._stream_sec = None

            if sec_error is not None:
                # الثانوي اختياري: التسجيل بيكمّل من الأساسي وحده، بس
                # المستخدم لازم يعرف - كان بيفتكر إنه بيسجّل الاتنين
                # ويكتشف بعد ما يخلّص إن صوت النظام مش موجود.
                _logger.warning("تعذّر فتح الجهاز الثانوي للدمج: %s", sec_error)
                self.secondary_error = self._describe_open_failure(sec_error)
                if self.on_error:
                    message = (
                        self.tr.t("rec_err_dual_failed", error=self.secondary_error) if self.tr
                        else f"تعذّر ضم الجهاز الثاني، والتسجيل هيكمّل من الأساسي وحده: {self.secondary_error}"
                    )
                    self.on_error(message)

        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
        self._is_recording = True
        self._start_time = time.time()
        self._last_recording_had_no_audio = False

    # نتيجة فحص كل (مرمّز، حاوية، معدل، معدل بت) - الفحص بيرمّز فعلًا
    # فبياخد وقت، ونتيجته ثابتة طول عمر البرنامج
    _ENCODER_RATE_CACHE = {}

    @staticmethod
    def _encoder_accepts(codec_name, container, rate, options, bitrate=None):
        """
        بيجرّب يرمّز إطارًا صامتًا فعلًا.

        السؤال ده ما ينفعش نسأله للمرمّز: wmav2 بيقول إنه بياخد أي معدل
        وبعدين يرفض 192000 عند أول إطار. الطريقة الوحيدة الموثوقة إننا
        نجرّب.

        التجربة لازم تبقى مطابقة للتسجيل الحقيقي في كل حاجة تخصّ الفتح -
        ومنها معدل البِت: wmav2 بيرفض الفتح خالص لو معدل البِت متساب
        للافتراضي، فتجربة من غيره بتفشل عند كل المعدلات وترجّع نتيجة غلط.
        """
        import shutil
        import tempfile

        import av
        import numpy as np

        # في مجلد مؤقت خاص لا في مجلد المستخدم: الحاوية بتكتب ملفًا
        # حقيقيًا، والمجلد بيتمسح كله في الآخر مهما حصل.
        # (اسم الملف بلا امتداد عن قصد: الصيغة محددة بـ format، والامتداد
        # الغلط كان بيلخبط بعض الحاويات)
        probe_dir = tempfile.mkdtemp(prefix="ump_probe_")
        probe = os.path.join(probe_dir, "probe")
        try:
            with av.open(probe, mode="w", format=container) as container_obj:
                stream = container_obj.add_stream(codec_name, rate=rate,
                                                  options=options or {})
                if bitrate:
                    stream.bit_rate = bitrate
                frame = av.AudioFrame.from_ndarray(
                    np.zeros((1, 1024), dtype="int16"), format="s16", layout="mono"
                )
                frame.sample_rate = rate
                resampler = av.AudioResampler(
                    format=stream.codec_context.format,
                    layout=stream.codec_context.layout,
                    rate=stream.codec_context.rate,
                )
                for resampled in resampler.resample(frame):
                    for packet in stream.encode(resampled):
                        container_obj.mux(packet)
            return True
        except Exception:
            return False
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)

    @classmethod
    def encoder_sample_rate(cls, codec_name: str, wanted_rate: int,
                            container=None, options=None, bitrate=None) -> int:
        """
        أعلى معدل الصيغة تقدر عليه فعلًا، ولا يتعدّى معدل الجهاز.

        كل مرمِّز له حدوده: libmp3lame أقصاه 48000، وopus بياخد خمس قيم
        بس. ومايك 192 كيلوهرتز (شائع في مايكات USB) كان معدله بيروح
        للمرمّز كما هو فيرفضه:
            avcodec_open2("libmp3lame", {}) returned 22

        بنلتقط بمعدل الجهاز (بلا إعادة تشكيل من ويندوز) وبنحوّل مرة
        واحدة هنا لأعلى معدل الصيغة قادرة عليه.

        القائمة المعلَنة مش كفاية: في مرمّزات بتقول "أي معدل" وبعدين
        ترفض. فلما ما يكونش فيه قائمة، بنجرّب فعلًا.
        """
        cache_key = (codec_name, container, wanted_rate, bitrate)
        if cache_key in cls._ENCODER_RATE_CACHE:
            return cls._ENCODER_RATE_CACHE[cache_key]

        # الاستيراد هنا: av تقيلة، والدالة دي بتتنادى من نافذة المسجّل
        try:
            import av
            # قبل أي تسجيل
            declared = av.codec.Codec(codec_name, "w").audio_rates
        except Exception:
            declared = None

        if declared:
            usable = sorted(r for r in declared if r <= wanted_rate)
            result = usable[-1] if usable else sorted(declared)[0]
        elif container is None:
            result = wanted_rate
        else:
            # بلا قائمة معلنة: نجرّب من معدل الجهاز نزولًا، وأول معدل
            # بيقبله المرمّز فعلًا هو المختار
            candidates = [wanted_rate] + [r for r in (96000, 48000, 44100, 22050, 16000)
                                          if r < wanted_rate]
            result = candidates[-1]
            for candidate in candidates:
                if cls._encoder_accepts(codec_name, container, candidate,
                                        options, bitrate):
                    result = candidate
                    break

        cls._ENCODER_RATE_CACHE[cache_key] = result
        return result

    def _open_direct_encoder(self, output_path: str, target_ext: str, audio_bitrate: int):
        import av
        from core.formats import AUDIO_FORMATS, resolve_audio_bitrate

        target_ext = target_ext.lower()
        preset = AUDIO_FORMATS.get(target_ext)
        if preset is None:
            if target_ext == ".ts":
                preset = {"codec": "aac", "container": "mpegts"}
            else:
                msg = self.tr.t("rec_err_unsupported_format", ext=target_ext) if self.tr else f"صيغة تسجيل غير مدعومة: {target_ext}"
                raise RecorderError(msg)

        # «أعلى جودة» تُحسم حسب الصيغة وعدد القنوات الفعلي، ورقم فوق سقف
        # المرمّز ينزل إليه بدل أن يفشل الترميز.
        # (لازم قبل اختيار المعدل: wmav2 بيرفض الفتح بلا معدل بت)
        audio_bitrate = resolve_audio_bitrate(
            preset["codec"], audio_bitrate,
            preset.get("force_channels") or self._channels,
        )

        effective_sample_rate = preset.get("force_sample_rate") or self.encoder_sample_rate(
            preset["codec"], self._sample_rate,
            container=preset.get("container"),
            options=preset.get("codec_options"),
            bitrate=audio_bitrate,
        )
        effective_channels = preset.get("force_channels") or self._channels
        if effective_sample_rate != self._sample_rate:
            _logger.info(
                "معدل الالتقاط %d غير مدعوم في %s، بيتحوّل لـ%d",
                self._sample_rate, preset["codec"], effective_sample_rate,
            )

        try:
            self._out_container = av.open(output_path, mode="w", format=preset.get("container"))
            # خيارات المرمّز تُمرَّر عند الإنشاء: Vorbis يرفض العمل بلا
            # strict=-2، وضبطها بعد الفتح لا يصل إليه.
            # (نفس السبب في core/converter.py)
            self._out_audio_stream = self._out_container.add_stream(
                preset["codec"], rate=effective_sample_rate,
                options=preset.get("codec_options") or {},
            )
            if audio_bitrate:
                self._out_audio_stream.bit_rate = audio_bitrate
            self._out_audio_stream.layout = "mono" if effective_channels == 1 else "stereo"
            self._resampler = av.AudioResampler(
                format=self._out_audio_stream.codec_context.format,
                layout=self._out_audio_stream.codec_context.layout,
                rate=self._out_audio_stream.codec_context.rate,
            )
        except Exception as exc:
            self._close_output_on_failure()
            msg = self.tr.t("rec_err_direct_encode", ext=target_ext, error=exc) if self.tr else f"تعذر تجهيز ترميز التسجيل المباشر ({target_ext}): {exc}"
            raise RecorderError(msg) from exc

        self._av_format = "s16" if self._bit_depth == 16 else "s32"
        self._av_layout = "mono" if self._channels == 1 else "stereo"

    def _input_attempts(self, sample_rate, channels):
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
        for rate in (sample_rate, 48000, 44100, 16000):
            for chans in (channels, 1):
                for extra in (None, shared):
                    key = (rate, chans, extra is not None)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield rate, chans, extra

    def _open_input_with_fallbacks(self, device_index, sample_rate, channels):
        """بيرجّع (نجح؟، آخر خطأ)."""
        last_error = None
        wanted = (sample_rate, channels)

        for rate, chans, extra in self._input_attempts(sample_rate, channels):
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
                self._wait_for_first_block()
            except Exception as exc:
                last_error = exc
                self._stream = None
                continue

            if (rate, chans) != wanted:
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

    def _close_output_on_failure(self):
        if self._wave_file is not None:
            try: self._wave_file.close()
            except Exception: pass
            self._wave_file = None
        if self._out_container is not None:
            try: self._out_container.close()
            except Exception: pass
        self._out_container = None
        self._out_audio_stream = None
        self._resampler = None

    def _encode_chunk(self, chunk: np.ndarray):
        import av

        packed = np.ascontiguousarray(chunk).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(packed, format=self._av_format, layout=self._av_layout)
        frame.sample_rate = self._sample_rate
        frame.pts = None

        resampled_frames = self._resampler.resample(frame)
        if not isinstance(resampled_frames, (list, tuple)):
            resampled_frames = [resampled_frames] if resampled_frames else []
        for resampled_frame in resampled_frames:
            for packet in self._out_audio_stream.encode(resampled_frame):
                self._out_container.mux(packet)

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

    def _audio_callback_pri(self, indata, frames, time_info, status):
        self._first_block.set()
        if self._pause_flag.is_set(): return
        data = self._format_channels(indata.copy())
        try: self._queue_pri.put_nowait(data)
        except queue.Full: pass

    def _audio_callback_sec(self, indata, frames, time_info, status):
        if self._pause_flag.is_set(): return
        data = self._format_channels(indata.copy())
        try: self._queue_sec.put_nowait(data)
        except queue.Full: pass

    def _format_channels(self, data):
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if data.shape[1] == 1 and self._channels == 2:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] == 2 and self._channels == 1:
            data = np.mean(data, axis=1, keepdims=True)
        return data

    # بعد الموازنة كل مسار عند المستوى المستهدف، فالنص بيخلّي المجموع
    # تحت السقف
    _MIX_GAIN = 0.5

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

    def _writer_loop(self):
        while not self._stop_flag.is_set() or not self._queue_pri.empty():
            try:
                chunk_pri = self._queue_pri.get(timeout=0.2)
            except queue.Empty:
                continue

            chunk = chunk_pri

            if self._has_dual_input:
                try:
                    chunk_sec = self._queue_sec.get_nowait()
                    chunk = self._mix_audio_chunks(chunk_pri, chunk_sec)
                except queue.Empty:
                    pass

            try:
                self._track_clipping(chunk)

                if self._direct_encode:
                    self._encode_chunk(chunk)
                else:
                    self._wave_file.writeframes(chunk.tobytes())
                self._frames_written += len(chunk)

                if self.on_level:
                    normalized = chunk.astype(np.float32) / self._max_abs
                    if normalized.size:
                        rms = float(np.sqrt(np.mean(np.square(normalized))))
                        peak = float(np.max(np.abs(normalized)))
                    else:
                        rms = peak = 0.0
                    self.on_level(min(1.0, rms * 4), min(1.0, peak))

            except Exception as exc:
                _logger.exception("Error writing recording to disk")
                if self.on_error:
                    self.on_error(str(exc))
                self._stop_flag.set()
                return

    def pause(self):
        self._pause_flag.set()

    def resume(self):
        self._pause_flag.clear()

    def stop(self):
        if not self._is_recording:
            return self._wav_path, 0.0

        self._stop_flag.set()

        for st in (self._stream, self._stream_sec):
            if st is not None:
                try:
                    st.stop()
                    st.close()
                except Exception:
                    # كان بيتبلع بصمت: لو الإغلاق فشل الجهاز بيفضل محجوز،
                    # والتسجيل اللي بعده بيفشل بلا سبب ظاهر
                    _logger.exception("فشل إغلاق مجرى الإدخال الصوتي")

        self._stream = None
        self._stream_sec = None

        if self._writer_thread is not None:
            self._writer_thread.join(timeout=5)
        self._writer_thread = None

        duration = self.get_elapsed_seconds()
        wall_elapsed = (time.time() - self._start_time) if self._start_time else 0.0
        self._last_recording_had_no_audio = self._frames_written == 0 and wall_elapsed > 1.5

        # سطر واحد يلخّص التسجيل في السجل: شكاوى "الصوت مش نقي" كانت بتوصل
        # بلا أي معلومة، والسطر ده بيحسمها - المعدل والقنوات والتشبّع.
        # بلا أسماء ملفات ولا مسارات: السجل بيتبعت في التقرير التشخيصي.
        # (شوف core/diagnostics.py)
        _logger.info(
            "REC_SUMMARY sr=%s ch=%s bits=%s fmt=%s dual=%s written=%.2fs wall=%.2fs "
            "clipped_samples=%d clip_events=%d",
            self._sample_rate, self._channels, self._bit_depth,
            ".wav" if not self._direct_encode else "encoded",
            self._has_dual_input, duration, wall_elapsed,
            self._clipped_samples, self._clip_events,
        )

        if self._wave_file is not None:
            try:
                self._wave_file.close()
            except Exception:
                # ملف WAV بلا إغلاق ترويسته ناقصة: الطول المكتوب فيها
                # صفر، فبعض المشغّلات بتشوفه فاضي
                _logger.exception("فشل إغلاق ملف WAV - التسجيل ممكن يكون ناقص")
        self._wave_file = None

        if self._direct_encode and self._out_container is not None:
            try:
                if self._out_audio_stream is not None:
                    # تفريغ المرمّز: الإطارات اللي لسه جوّه بتتكتب.
                    # بلا ده آخر جزء من الثانية بيضيع، وفي MP3 أحيانًا
                    # الملف كله بيبقى مش صالح.
                    # (encode(None) معناها "خلّصت، طلّع الباقي")
                    for packet in self._out_audio_stream.encode(None):
                        self._out_container.mux(packet)
            except Exception:
                _logger.exception("فشل إغلاق المُرمِّز - آخر التسجيل ممكن يكون ناقص")
            finally:
                try:
                    self._out_container.close()
                except Exception:
                    _logger.exception("فشل إغلاق حاوية التسجيل")
                self._out_container = None
                self._out_audio_stream = None
                self._resampler = None

        self._is_recording = False
        return self._wav_path, duration


def replace_with_retry(src: str, dst: str, attempts: int = 10, delay_seconds: float = 0.3):
    try:
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    except OSError: pass

    last_error = None
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except OSError as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(min(2.0, delay_seconds * (attempt + 1)))
    raise last_error


def convert_recording(wav_path: str, target_ext: str, audio_bitrate: int, delete_original: bool = True):
    from core.converter import convert_file

    if target_ext == ".wav":
        return wav_path

    output_path = os.path.splitext(wav_path)[0] + target_ext
    convert_file(
        wav_path,
        output_path,
        target_ext,
        is_video=False,
        audio_bitrate=audio_bitrate,
    )
    if delete_original:
        try:
            os.remove(wav_path)
        except OSError:
            pass
    return output_path