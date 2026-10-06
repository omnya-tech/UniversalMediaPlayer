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

from core.audio_devices import looks_like_system_audio, wasapi_shared_settings
from core.audio_filters import rate_converter
from core.level_balance import TrackBalancer
from core.logging_setup import configure_logging
from core.voice_enhance import DEFAULT_ENHANCE_LEVEL, VoiceEnhancer
from core.recording_encoder import DirectEncoderMixin
from core.recording_input import InputDeviceMixin
from core.recording_mix import DualInputMixin
from core.recording_common import RecorderError

_logger = configure_logging()

# 24 بت تُلتقط كـ int32 (أعلى 24 بتًا منها هي الصوت) وتُكتب في WAV بثلاثة
# بايتات للعينة. هامشها أوسع من 16 بت بكثير: الصوت الهادئ لا يخسر تفاصيله،
# وحجمها أقل من 32 بت بالربع.
_BIT_DEPTH_CONFIG = {
    16: {"dtype": "int16", "sample_width": 2, "max_abs": 32768.0},
    24: {"dtype": "int32", "sample_width": 3, "max_abs": 2147483648.0},
    32: {"dtype": "int32", "sample_width": 4, "max_abs": 2147483648.0},
}
SUPPORTED_BIT_DEPTHS = (16, 24, 32)
_DEFAULT_BIT_DEPTH = 16

SUPPORTED_SAMPLE_RATES = (44100, 48000, 96000)

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


class AudioRecorder(DualInputMixin, InputDeviceMixin, DirectEncoderMixin):
    def __init__(self, on_level=None, on_error=None, tr=None):
        self.on_level = on_level
        self.on_error = on_error
        self.tr = tr

        self._stream = None
        self._stream_sec = None
        self._wave_file = None
        # بلا حد: الطابور المحدود كان يرمي كتل الصوت بصمت لو تأخر الكاتب
        # (ترميز MP3 مباشر على جهاز بطيء مثلًا)، فتظهر قطوع في التسجيل.
        # الكتل تتراكم في الذاكرة لحظات ثم يلحق بها الكاتب
        self._queue_pri = queue.Queue()
        self._queue_sec = queue.Queue()
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
        self._reset_secondary_buffer(1)

        # رصد التشبّع: عدد العيّنات المتشبّعة وعدد الأحداث، وموضع آخر
        # حدث وطول السلسلة الحالية عشان الحدث اللي بيمتد على أكتر من
        # كتلة يتحسب مرة واحدة.
        # (شوف _track_clipping)
        self._clipped_samples = 0
        self._clip_events = 0
        self._samples_seen = 0
        self._clip_last_sample = -10**9
        self._clip_run = 0
        self._input_overflows = 0

        # تحسين صوت المايكروفون (core/voice_enhance.py) والوضع الحصري
        self._enhancer = None
        self.enhance_level = "off"
        self.exclusive_requested = False
        self.used_exclusive = False
        # معدل الجهاز الفعلي ومحوّله لمعدل الملف: بعض المايكات لا تقبل
        # الحصري إلا بمعدلها الأصلي (شوف _input_attempts)
        self._capture_rate = None
        self._rate_converter = None

        self._direct_encode = False
        self._out_container = None
        self._out_audio_stream = None
        self._resampler = None
        self._av_format = None
        self._av_layout = None

    def _reset_secondary_buffer(self, channels=None):
        channels = channels or self._channels or 1
        self._sec_buffer = np.zeros((0, channels), dtype=self._dtype)
        self._sec_underruns = 0
        self._sec_overruns = 0

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
        rate = self._capture_rate or self._sample_rate
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
        gap = max(1, int(rate * _CLIP_EVENT_GAP_SEC))
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
        enhance_level: str = "off",
        exclusive: bool = False,
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
        self._input_overflows = 0
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
        self._reset_secondary_buffer()

        self.enhance_level = enhance_level
        self.exclusive_requested = bool(exclusive)
        self.used_exclusive = False
        self._enhancer = None
        self._capture_rate = None
        self._rate_converter = None

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

        self._capture_rate = int(self._stream.samplerate)
        self._channels = min(self._channels, self._stream.channels)
        self._sample_rate = self._capture_rate
        if self.used_exclusive and self._capture_rate != sample_rate:
            # الحصري فُتح بمعدل الجهاز الأصلي: الملف يبقى بالمعدل المطلوب
            try:
                self._rate_converter = rate_converter(
                    self._capture_rate, sample_rate, self._channels, self._dtype)
                self._sample_rate = sample_rate
                _logger.info("الوضع الحصري بمعدل الجهاز %d، والملف يتحوّل لـ%d",
                             self._capture_rate, sample_rate)
            except Exception:
                # بلا تحويل الملف يُكتب بمعدل الجهاز: أكبر لكنه سليم
                _logger.exception("تعذّر تجهيز تحويل المعدل، الملف بمعدل الجهاز")
        if self._direct_encode:
            # الجهاز قد يُفتح بقناة واحدة والمرمّز جُهّز لاثنتين: الإطار
            # يتبع ما يصل فعلًا، والمرمّز يحوّل لما جُهّز له. بغير ذلك
            # كتلة 441 عينة أحادية تُقرأ ستيريو فيتوقف التسجيل بخطأ
            # "got 1764 bytes; need 1760 bytes"
            self._av_layout = "mono" if self._channels == 1 else "stereo"
        self._reset_secondary_buffer(self._channels)
        if self._wave_file is not None:
            # الجهاز قد يُفتح بمعدل أو قنوات غير المطلوبة (المحاولات
            # المتدرجة)؛ ترويسة WAV تتبع ما فُتح فعلًا وإلا خرج الصوت
            # أسرع أو أبطأ. لم يُكتب شيء بعد، فالتغيير مسموح
            self._wave_file.setframerate(self._sample_rate)
            self._wave_file.setnchannels(self._channels)

        # التحسين للمايكروفون وحده: جهير صوت النظام حقيقي لا طنين
        try:
            device_name = sd.query_devices(device_index).get("name", "")
        except Exception:
            device_name = ""
        if VoiceEnhancer.is_active(enhance_level) and not looks_like_system_audio(device_name):
            try:
                self._enhancer = VoiceEnhancer(self._sample_rate, self._channels, enhance_level)
            except Exception:
                # بلا تحسين أفضل من بلا تسجيل
                _logger.exception("تعذّر تجهيز تحسين الصوت، التسجيل يكمّل بدونه")
                self._enhancer = None

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

    def _audio_callback_pri(self, indata, frames, time_info, status):
        self._first_block.set()
        # كتلة ضاعت قبل أن نستلمها (البرنامج تأخر عن كرت الصوت): لا تُسمع
        # إلا قطعًا قصيرًا، فتُعدّ ليظهر سببها في التقرير التشخيصي
        if status.input_overflow:
            self._input_overflows += 1
        if self._pause_flag.is_set(): return
        data = self._format_channels(indata.copy())
        try: self._queue_pri.put_nowait(data)
        except queue.Full: pass

    def _audio_callback_sec(self, indata, frames, time_info, status):
        if status.input_overflow:
            self._input_overflows += 1
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
            # المتوسط يخرج أعدادًا عشرية؛ الملف يُكتب بنوع العينة الأصلي
            data = np.mean(data, axis=1, keepdims=True).astype(data.dtype)
        return data

    def _writer_loop(self):
        while not self._stop_flag.is_set() or not self._queue_pri.empty():
            try:
                chunk_pri = self._queue_pri.get(timeout=0.2)
            except queue.Empty:
                continue

            # التشبّع يُرصد على ما خرج من كرت الصوت قبل أي معالجة: المحدد
            # يمنع القص في الملف، لكن المايك المرتفع يستحق التنبيه
            self._track_clipping(chunk_pri)
            if self._rate_converter is not None:
                try:
                    chunk_pri = self._rate_converter.push(chunk_pri)
                except Exception as exc:
                    # الملف ترويسته بالمعدل المطلوب، فلا يُكمل بمعدل الجهاز
                    _logger.exception("تحويل معدل الالتقاط فشل أثناء التسجيل")
                    if self.on_error:
                        self.on_error(str(exc))
                    self._stop_flag.set()
                    return
                if not len(chunk_pri):
                    continue
            if self._enhancer is not None:
                try:
                    chunk_pri = self._enhancer.process(chunk_pri, self._max_abs)
                except Exception:
                    _logger.exception("تحسين الصوت فشل أثناء التسجيل، يُكمل بدونه")
                    self._enhancer = None
                if not len(chunk_pri):
                    continue

            chunk = chunk_pri

            if self._has_dual_input:
                chunk = self._mix_audio_chunks(chunk_pri, self._take_secondary(len(chunk_pri)))

            try:
                self._write_chunk(chunk)

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

        # ما احتجزه تحويل المعدل وتحسين الصوت في آخر التسجيل
        try:
            tails = []
            if self._rate_converter is not None:
                tails.append(self._rate_converter.flush())
            if self._enhancer is not None:
                tails = [self._enhancer.process(tail, self._max_abs) for tail in tails if len(tail)]
                tails.append(self._enhancer.flush())
            for tail in tails:
                if tail is not None and len(tail):
                    self._write_chunk(tail)
        except Exception:
            _logger.exception("تعذّر تفريغ آخر التسجيل من التحويل أو التحسين")

    def _write_chunk(self, chunk):
        if self._direct_encode:
            self._encode_chunk(chunk)
        elif self._bit_depth == 24:
            # أعلى ثلاثة بايتات من كل عينة int32 (ترتيب little-endian)
            raw = np.ascontiguousarray(chunk, dtype="<i4").view(np.uint8).reshape(-1, 4)[:, 1:]
            self._wave_file.writeframes(raw.tobytes())
        else:
            self._wave_file.writeframes(chunk.tobytes())
        self._frames_written += len(chunk)

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
            "REC_SUMMARY sr=%s capture_sr=%s ch=%s bits=%s fmt=%s dual=%s exclusive=%s enhance=%s "
            "written=%.2fs wall=%.2fs clipped_samples=%d clip_events=%d "
            "input_overflows=%d sec_underruns=%d sec_overruns=%d",
            self._sample_rate, self._capture_rate, self._channels, self._bit_depth,
            ".wav" if not self._direct_encode else "encoded",
            self._has_dual_input, self.used_exclusive,
            self.enhance_level if self._enhancer is not None else "off",
            duration, wall_elapsed,
            self._clipped_samples, self._clip_events,
            self._input_overflows, self._sec_underruns, self._sec_overruns,
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