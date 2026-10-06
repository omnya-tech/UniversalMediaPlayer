# -*- coding: utf-8 -*-
"""
قص ملفات الصوت والفيديو ودمجها (محرر الوسائط).

كل العمل هنا بـ PyAV داخل البرنامج نفسه، مثل المحوّل: لا ffmpeg خارجي ولا
عملية بايثون منفصلة. محاولة سابقة اعتمدت على ما هو خارج البرنامج فعملت
على جهاز فيه بايثون وتوقفت على غيره؛ هذه الوحدة لا تستورد subprocess
ولا تستدعي أي ملف تنفيذي، والاختبار test_editor_has_no_external_process
يحرس ذلك.

طريقتان:

- النسخ المباشر للحزم (الافتراضي): بلا فك ترميز، فالجودة كما هي والعمل
  سريع جدًا. الصوت يُقص على حدود حزمه (نحو 26 مللي ثانية في mp3) فلا
  يُسمع الفرق. أما الفيديو فلا يبدأ إلا من «إطار مفتاحي» (صورة كاملة كل
  بضع ثوانٍ، وما بعدها محفوظ كفرق عنها)، فبداية المقطع ترجع لأقرب إطار
  مفتاحي قبلها، والصوت يتبعها ليبقى متزامنًا.
- الدقيق (precise=True): يفك ترميز الفيديو ويعيده، فيقص عند الوقت بالظبط
  لكنه أبطأ والجودة تنقص قليلًا. للصوت وحده لا فرق: النسخ دقيق أصلًا.

الدمج نسخ مباشر دائمًا (لا أوقات قص فيه). ملفات الصوت المختلفة الخصائص
يُعاد ترميزها بصيغة الأول، أما الفيديوهات المختلفة فتُرفض برسالة تشرح
السبب: إعادة ترميز فيديو بمقاسات مختلفة عمل المحوّل لا المحرر.

من الملف يُؤخذ أول مسار فيديو وأول مسار صوت فقط؛ الترجمات والمسارات
الإضافية لا تُنسخ.
"""

import os
import threading
from fractions import Fraction

import av

from core.formats import (
    AUDIO_FORMATS,
    CRF_SUPPORTED_VCODECS,
    VIDEO_FORMATS,
    ConversionCancelled,
    ConversionError,
)
from core.logging_setup import configure_logging

_logger = configure_logging()

# الصور الثابتة المرفقة بملفات الصوت (غلاف الألبوم) تظهر كمسار فيديو
_ATTACHED_PIC = 0x0400


class EditError(ConversionError):
    """فشل قص أو دمج؛ رسالته جاهزة للعرض على المستخدم."""


def _t(tr, key, fallback, **kwargs):
    return tr.t(key, **kwargs) if tr else fallback.format(**kwargs)


def _open_input(path, tr=None):
    try:
        return av.open(path, mode="r")
    except Exception as exc:
        raise EditError(_t(tr, "editor_err_open", "تعذر فتح الملف: {error}", error=exc)) from exc


def _streams(container, path, tr=None):
    """(مسار الفيديو أو None، مسار الصوت أو None)، وخطأ لو لا هذا ولا ذاك."""
    video = next((s for s in container.streams.video
                  if not int(s.disposition) & _ATTACHED_PIC), None)
    audio = next(iter(container.streams.audio), None)
    if video is None and audio is None:
        raise EditError(_t(tr, "editor_err_no_media", "الملف لا يحتوي على صوت أو فيديو: {name}",
                           name=os.path.basename(path)))
    return video, audio


def has_video(path, tr=None) -> bool:
    container = _open_input(path, tr)
    try:
        return _streams(container, path, tr)[0] is not None
    finally:
        container.close()


def _output_format(path, input_container):
    """صيغة الحاوية الناتجة: من جداول الصيغ حسب الامتداد، وإلا صيغة الأصل."""
    ext = os.path.splitext(path)[1].lower()
    preset = VIDEO_FORMATS.get(ext) or AUDIO_FORMATS.get(ext)
    if preset:
        return preset["container"]
    name = input_container.format.name if input_container.format else None
    # بعض الصيغ تحمل أكثر من اسم (مثل "mov,mp4,m4a,3gp,3g2,mj2")
    return name.split(",")[0] if name else None


def get_duration(path, tr=None) -> float:
    """مدة الملف بالثواني."""
    container = _open_input(path, tr)
    try:
        video, audio = _streams(container, path, tr)
        main = video or audio
        if video is None and main.duration and main.time_base:
            return float(main.duration * main.time_base)
        if container.duration:
            return float(container.duration) / av.time_base
        if main.duration and main.time_base:
            return float(main.duration * main.time_base)
        # بعض الحاويات (مثل ADTS) لا تحفظ المدة: تُحسب من آخر حزمة
        end = 0.0
        for packet in container.demux(main):
            if packet.pts is not None and packet.time_base:
                end = max(end, float((packet.pts + (packet.duration or 0)) * packet.time_base))
        start = float(main.start_time * main.time_base) if main.start_time and main.time_base else 0.0
        return end - start
    finally:
        container.close()


def segment_length(path, start, end, tr=None) -> float:
    """طول المقطع بالثواني؛ النهاية None تعني آخر الملف."""
    if end is None:
        end = get_duration(path, tr)
    return max(0.0, end - start)


def _stream_start(stream):
    if stream is not None and stream.start_time is not None and stream.time_base:
        return float(stream.start_time * stream.time_base)
    return 0.0


# البحث في بعض الحاويات (مثل ts) يقع بعد الوقت المطلوب أحيانًا، فنبحث قبله
# بهامش ثم نتخطى ما قبل الوقت حزمةً حزمة
_SEEK_MARGIN = 3.0


def _seek_before(container, stream, origin, seconds, any_frame=False):
    """يضع القراءة قبل الوقت (من بداية الملف) بهامش؛ أول الملف بلا بحث."""
    target = seconds - _SEEK_MARGIN
    if target <= 0:
        return
    container.seek(int((origin + target) / stream.time_base), stream=stream,
                   backward=True, any_frame=any_frame)


def keyframe_before(path, seconds, tr=None) -> float:
    """
    وقت آخر إطار مفتاحي عند الوقت المعطى أو قبله (من بداية الملف).

    للصوت وحده يرجع الوقت كما هو. هذا هو المكان الذي يبدأ منه القص
    السريع فعلًا، فالواجهة تعلنه للمستخدم.
    """
    container = _open_input(path, tr)
    try:
        video, _audio = _streams(container, path, tr)
        if video is None or seconds <= 0:
            return max(0.0, seconds)
        origin = _stream_start(video)
        tb = video.time_base
        for attempt in (seconds, 0):
            if attempt:
                _seek_before(container, video, origin, attempt)
            else:
                container.seek(0)
            best = None
            for packet in container.demux(video):
                if packet.pts is None:
                    continue
                t = float(packet.pts * tb) - origin
                if t > seconds + 0.001:
                    break
                if packet.is_keyframe:
                    best = t
            if best is not None:
                return max(0.0, best)
        return 0.0
    finally:
        container.close()


def _signature(container, path, tr=None):
    """الخصائص التي يجب أن تتطابق لتُدمج الحزم بلا إعادة ترميز."""
    video, audio = _streams(container, path, tr)
    result = []
    for stream in (video, audio):
        if stream is None:
            result.append(None)
            continue
        cc = stream.codec_context
        if stream.type == "video":
            result.append((cc.name, cc.width, cc.height))
        else:
            layout = getattr(cc, "layout", None)
            result.append((cc.name, cc.sample_rate,
                           getattr(layout, "nb_channels", None) or getattr(cc, "channels", None)))
    return tuple(result)


def _cleanup(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


class _Progress:
    """يجمع تقدّم عدة مقاطع في كسر واحد من 0 إلى 1."""

    def __init__(self, callback, total_seconds):
        self.callback = callback
        self.total = max(total_seconds, 0.001)
        self.done = 0.0
        self.last = 0.0

    def report(self, seconds_in_segment):
        # الصوت والفيديو يتناوبان فيتقدم أحدهما على الآخر قليلًا؛ التقدم
        # المُعلن لا يرجع للخلف
        fraction = min(1.0, max(self.last, (self.done + seconds_in_segment) / self.total))
        self.last = fraction
        if self.callback:
            self.callback(fraction)

    def finish_segment(self, length):
        self.done += length


def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise ConversionCancelled()


# ---- النسخ المباشر ----

def _copy_segments(out_container, out_video, out_audio, sources, cancel_event, progress):
    """
    ينسخ حزم المقاطع المتتالية إلى الملف الناتج.

    sources: قائمة (مسار، بداية، نهاية) بالثواني من بداية الملف، والنهاية
    None تعني آخره. الطوابع الزمنية تُعاد كتابتها لتتصل المقاطع بلا فجوات،
    والفرق بين pts وdts في الفيديو يبقى كما هو.
    يرجع طول الناتج بالثواني.
    """
    next_start = 0.0
    for path, start, end in sources:
        container = av.open(path, mode="r")
        try:
            video, audio = _streams(container, path)
            video = video if out_video is not None else None
            audio = audio if out_audio is not None else None
            mapping = {s.index: o for s, o in ((video, out_video), (audio, out_audio)) if s is not None}
            main = video or audio
            origin = _stream_start(main)
            if video is not None:
                # الفيديو يبدأ من إطار مفتاحي، والصوت يتبعه ليبقى متزامنًا
                lower = keyframe_before(path, start) if start > 0 else 0.0
                _seek_before(container, video, origin, lower)
            else:
                lower = start
                _seek_before(container, audio, origin, start, any_frame=True)
            # mkv وwebm لا تحفظ dts، ومزج حزم بها وبدونها يرفضه الكاتب
            drop_dts = out_container.format.name in ("matroska", "webm")

            base = None  # وقت أول حزمة مأخوذة؛ منه تُحسب الطوابع الجديدة
            segment_end = next_start
            finished = set()
            for packet in container.demux([s for s in (video, audio) if s is not None]):
                _check_cancel(cancel_event)
                if packet.pts is None or packet.size == 0 or packet.stream.index not in mapping:
                    continue
                tb = packet.time_base
                t = float(packet.pts * tb) - origin
                dur = float((packet.duration or 0) * tb)
                if packet.stream.type == "video":
                    if t < lower - 0.001:
                        continue
                    if end is not None and t >= end:
                        # مع إطارات B قد تأتي بعدها حزم أقدم؛ نتوقف بعد هامش
                        if packet.dts is not None and float(packet.dts * tb) - origin >= end + 1:
                            finished.add("video")
                        continue
                else:
                    # حزمة الصوت تُؤخذ لو منتصفها داخل المقطع
                    middle = t + dur / 2
                    if middle < lower:
                        continue
                    if end is not None and middle >= end:
                        finished.add("audio")
                        if video is None or "video" in finished:
                            break
                        continue
                if base is None:
                    base = lower if video is not None else t
                shift = next_start - base
                packet.pts = int(round((t + shift) / tb))
                # حاويات مثل mkv لا تحفظ dts لكل حزمة؛ تبقى فارغة ويحسبها الكاتب
                if drop_dts and packet.stream.type == "video":
                    packet.dts = None
                elif packet.dts is not None:
                    packet.dts = int(round((float(packet.dts * tb) - origin + shift) / tb))
                packet.stream = mapping[packet.stream.index]
                packet.time_base = tb
                out_container.mux(packet)
                segment_end = max(segment_end, t + shift + dur)
                progress.report(t - lower)
                if len(finished) == len(mapping):
                    break
            next_start = segment_end
            progress.finish_segment(segment_length(path, start, end))
        finally:
            container.close()
    return next_start


def _fix_flac_header(path, seconds, sample_rate):
    """
    يصحّح عدد العينات في رأس FLAC بعد النسخ المباشر.

    النسخ يأخذ رأس الملف الأصلي كما هو، فيبقى فيه طول الأصل كاملًا،
    والمشغلات تعرض مدة خاطئة. الرأس (STREAMINFO) أول كتلة بعد "fLaC":
    عدد العينات 36 بتًّا في البايتات 13-17 منها، وبصمة MD5 بعدها تُصفَّر
    لأنها لم تعد تطابق (الصفر معناه «غير معروفة» في المواصفة).
    """
    total = int(round(seconds * sample_rate))
    with open(path, "r+b") as handle:
        head = bytearray(handle.read(42))
        if len(head) < 42 or head[:4] != b"fLaC" or (head[4] & 0x7F) != 0:
            return
        info = 8  # بداية STREAMINFO: "fLaC" ثم رأس الكتلة 4 بايتات
        head[info + 13] = (head[info + 13] & 0xF0) | ((total >> 32) & 0x0F)
        head[info + 14:info + 18] = (total & 0xFFFFFFFF).to_bytes(4, "big")
        handle.seek(0)
        handle.write(head)
        handle.seek(info + 18)
        handle.write(bytes(16))


# ---- إعادة الترميز ----

class _AudioEncoder:
    """
    يرمّز الصوت من مصادر مختلفة الصيغ في مسار ناتج واحد.

    لكل مصدر محوّل عينات خاص، والناتج يتجمع في طابور يُقرأ منه بحجم
    الإطار الذي يطلبه المرمّز (1152 عينة في mp3 مثلًا).
    """

    def __init__(self, out_container, out_stream):
        self.out_container = out_container
        self.out_stream = out_stream
        cc = out_stream.codec_context
        self.rate = cc.rate
        self.frame_size = cc.frame_size or 0
        self.fifo = av.AudioFifo()
        self.written = 0
        self.resampler = None

    def new_source(self):
        self.flush_resampler()
        cc = self.out_stream.codec_context
        self.resampler = av.AudioResampler(format=cc.format, layout=cc.layout, rate=self.rate)

    def _encode(self, frame):
        frame.pts = self.written
        frame.time_base = Fraction(1, self.rate)
        self.written += frame.samples
        for packet in self.out_stream.encode(frame):
            self.out_container.mux(packet)

    def _drain(self, final=False):
        if self.frame_size:
            while self.fifo.samples >= self.frame_size:
                self._encode(self.fifo.read(self.frame_size))
            if final and self.fifo.samples:
                self._encode(self.fifo.read())
        elif self.fifo.samples:
            self._encode(self.fifo.read())

    def add(self, frame, start, end):
        """يضيف إطارًا بعد قص ما يخرج منه عن [start، end) بدقة العينة."""
        t = frame.time
        frame_end = t + frame.samples / frame.sample_rate
        if frame_end <= start or (end is not None and t >= end):
            return
        first = max(0, int(round((start - t) * frame.sample_rate)))
        last = frame.samples
        if end is not None and frame_end > end:
            last = int(round((end - t) * frame.sample_rate))
        if first > 0 or last < frame.samples:
            array = frame.to_ndarray()
            if frame.format.is_planar:
                trimmed = array[..., first:last]
            else:
                channels = frame.layout.nb_channels
                trimmed = array[:, first * channels:last * channels]
            if trimmed.shape[-1] == 0:
                return
            new_frame = av.AudioFrame.from_ndarray(trimmed, format=frame.format.name,
                                                   layout=frame.layout.name)
            new_frame.sample_rate = frame.sample_rate
            frame = new_frame
        frame.pts = None
        for out_frame in self.resampler.resample(frame):
            out_frame.pts = None
            self.fifo.write(out_frame)
        self._drain()

    def flush_resampler(self):
        if self.resampler is not None:
            for out_frame in self.resampler.resample(None):
                out_frame.pts = None
                self.fifo.write(out_frame)
            self.resampler = None
        self._drain()

    def finish(self):
        self.flush_resampler()
        self._drain(final=True)
        for packet in self.out_stream.encode(None):
            self.out_container.mux(packet)


class _VideoEncoder:
    """
    يرمّز إطارات الفيديو بطوابع متصلة عبر المقاطع.

    الطابع رقم الإطار لا وقته: بعض الحاويات (مثل avi) تعطي أوقاتًا غير
    مرتبة بعد فك الترميز، والعدّ يبقي الإيقاع ثابتًا.
    """

    def __init__(self, out_container, out_stream, rate):
        self.out_container = out_container
        self.out_stream = out_stream
        self.rate = rate
        self.count = 0
        self.pix_fmt = out_stream.codec_context.pix_fmt
        self.width = out_stream.codec_context.width
        self.height = out_stream.codec_context.height

    def add(self, frame):
        pts = self.count
        self.count += 1
        if (frame.format.name != self.pix_fmt or frame.width != self.width
                or frame.height != self.height):
            frame = frame.reformat(width=self.width, height=self.height, format=self.pix_fmt)
        frame.pts = pts
        frame.time_base = Fraction(1, 1) / self.rate
        for packet in self.out_stream.encode(frame):
            self.out_container.mux(packet)

    def finish(self):
        for packet in self.out_stream.encode(None):
            self.out_container.mux(packet)


def _encode_segments(out_container, video_encoder, audio_encoder, sources, cancel_event, progress):
    """مثل _copy_segments لكن بفك الترميز وإعادته، فالقص بالضبط عند الوقت."""
    next_start = 0.0
    for path, start, end in sources:
        container = av.open(path, mode="r")
        try:
            video, audio = _streams(container, path)
            video = video if video_encoder is not None else None
            audio = audio if audio_encoder is not None else None
            wanted = [s for s in (video, audio) if s is not None]
            main = video or audio
            origin = _stream_start(main)
            # الرجوع لإطار مفتاحي قبل البداية ضروري لفك ترميز ما بعده
            _seek_before(container, main, origin, start)
            if audio_encoder is not None:
                audio_encoder.new_source()
            length = segment_length(path, start, end)
            done = set()
            for packet in container.demux(wanted):
                _check_cancel(cancel_event)
                kind = packet.stream.type
                if kind in done:
                    continue
                try:
                    frames = packet.decode()
                except av.error.InvalidDataError:
                    continue
                for frame in frames:
                    if frame.time is None:
                        continue
                    t = frame.time - origin
                    if end is not None and t >= end:
                        done.add(kind)
                        break
                    if kind == "video":
                        if t < start:
                            continue
                        video_encoder.add(frame)
                    else:
                        # وقت الإطار نسبةً لبداية الملف لا لطابعه الأصلي
                        _shift_audio_time(frame, origin)
                        audio_encoder.add(frame, start, end)
                    progress.report(t - start)
                if len(done) == len(wanted):
                    break
            next_start += length
            progress.finish_segment(length)
        finally:
            container.close()
    if video_encoder is not None:
        video_encoder.finish()
    if audio_encoder is not None:
        audio_encoder.finish()
    return next_start


def _shift_audio_time(frame, origin):
    """يجعل frame.time يُقرأ من بداية الملف (بعض الحاويات تبدأ من غير الصفر)."""
    if origin and frame.pts is not None and frame.time_base:
        frame.pts = frame.pts - int(round(origin / frame.time_base))


def _add_reencode_streams(out_container, output_path, video, audio):
    """مسارات ناتجة بمرمّزات صيغة الملف الناتج وخصائص الأصل."""
    ext = os.path.splitext(output_path)[1].lower()
    video_encoder = audio_encoder = None
    if video is not None:
        preset = VIDEO_FORMATS.get(ext) or {}
        vcodec = preset.get("vcodec") or video.codec_context.name
        rate = video.average_rate or video.guessed_rate or 25
        rate = Fraction(rate).limit_denominator(1001)
        out_video = out_container.add_stream(vcodec, rate=rate)
        out_video.width = video.codec_context.width
        out_video.height = video.codec_context.height
        out_video.pix_fmt = preset.get("pix_fmt", "yuv420p")
        options = dict(preset.get("codec_options") or {})
        if vcodec in ("libx264", "libx265"):
            # جودة قريبة من الأصل بسرعة معقولة على جهاز متوسط
            options.update({"preset": "veryfast", "crf": "18"})
        elif vcodec in CRF_SUPPORTED_VCODECS:
            options["crf"] = "30"
        elif video.codec_context.bit_rate:
            out_video.bit_rate = video.codec_context.bit_rate
        out_video.options = options
        video_encoder = _VideoEncoder(out_container, out_video, rate)
    if audio is not None:
        preset = VIDEO_FORMATS.get(ext) if video is not None else AUDIO_FORMATS.get(ext)
        preset = preset or {}
        acodec = (preset.get("acodec") if video is not None else preset.get("codec")) \
            or audio.codec_context.name
        sample_rate = preset.get("force_sample_rate") or audio.codec_context.sample_rate
        out_audio = out_container.add_stream(acodec, rate=sample_rate,
                                             options=preset.get("codec_options") or {})
        out_audio.layout = "stereo" if preset.get("force_channels") == 2 else audio.codec_context.layout.name
        bit_rate = audio.codec_context.bit_rate or preset.get("default_audio_bit_rate")
        if bit_rate:
            out_audio.bit_rate = bit_rate
        audio_encoder = _AudioEncoder(out_container, out_audio)
    return video_encoder, audio_encoder


def add_stream_copy(out_container, template):
    # PyAV 14 فأحدث نقل النسخ من قالب إلى add_stream_from_template، وصار
    # add_stream(template=...) يرفع خطأ
    if hasattr(out_container, "add_stream_from_template"):
        return out_container.add_stream_from_template(template)
    return out_container.add_stream(template=template)


def _write(sources, output_path, cancel_event=None, progress_callback=None, tr=None,
           precise=False, merging=False):
    """
    يكتب المقاطع المعطاة متتالية في ملف واحد بصيغة المقطع الأول.

    precise: يعيد ترميز الفيديو ليقص عند الوقت بالضبط.
    merging: ملفات مختلفة تُضم؛ الفيديوهات المختلفة الخصائص تُرفض.
    """
    if not sources:
        raise EditError(_t(tr, "editor_err_nothing", "لا يوجد ما يُحفظ"))

    signatures = {}
    for path in dict.fromkeys(s[0] for s in sources):
        container = _open_input(path, tr)
        try:
            signatures[path] = _signature(container, path, tr)
        finally:
            container.close()
    distinct = set(signatures.values())
    any_video = any(sig[0] is not None for sig in distinct)
    if len(distinct) > 1 and any_video:
        if not all(sig[0] is not None for sig in distinct):
            raise EditError(_t(tr, "editor_err_mixed_video_audio",
                               "لا يمكن دمج ملفات فيديو مع ملفات صوت فقط"))
        raise EditError(_t(tr, "editor_err_video_mismatch",
                           "الفيديوهات مختلفة في الصيغة أو المقاس، فلا تُدمج كما هي. "
                           "حوّلها أولًا بمحوّل الصيغ لنفس الصيغة والمقاس ثم ادمجها"))
    reencode = (precise and any_video and not merging) or len(distinct) > 1

    total = sum(segment_length(path, start, end, tr) for path, start, end in sources)
    progress = _Progress(progress_callback, total)

    first_path = sources[0][0]
    template_container = _open_input(first_path, tr)
    out_container = None
    finished = False
    try:
        video, audio = _streams(template_container, first_path, tr)
        try:
            out_container = av.open(output_path, mode="w",
                                    format=_output_format(output_path, template_container))
        except Exception as exc:
            raise EditError(_t(tr, "editor_err_create", "تعذر إنشاء الملف الناتج: {error}",
                               error=exc)) from exc

        if reencode:
            video_encoder, audio_encoder = _add_reencode_streams(out_container, output_path, video, audio)
            _encode_segments(out_container, video_encoder, audio_encoder, sources, cancel_event, progress)
        else:
            out_video = add_stream_copy(out_container, video) if video is not None else None
            out_audio = add_stream_copy(out_container, audio) if audio is not None else None
            copied = _copy_segments(out_container, out_video, out_audio, sources, cancel_event, progress)
            if video is None and audio.codec_context.name == "flac":
                out_container.close()
                out_container = None
                _fix_flac_header(output_path, copied, audio.codec_context.sample_rate)
        if out_container is not None:
            out_container.close()
            out_container = None
        finished = True
        if progress_callback:
            progress_callback(1.0)
    except (ConversionCancelled, EditError):
        raise
    except Exception as exc:
        _logger.exception("فشل حفظ المقاطع في: %s", output_path)
        raise EditError(_t(tr, "editor_err_unexpected", "حدث خطأ غير متوقع: {error}",
                           error=exc)) from exc
    finally:
        if out_container is not None:
            try:
                out_container.close()
            except Exception:
                pass
        template_container.close()
        if not finished:
            _cleanup(output_path)


def split_file(path, at_seconds, first_output, second_output,
               cancel_event=None, progress_callback=None, tr=None, precise=False):
    """
    يقسم الملف لجزأين عند الوقت المعطى.

    في القص السريع للفيديو يكون التقسيم عند الإطار المفتاحي السابق للوقت،
    فلا يتكرر شيء بين الجزأين ولا يضيع. يرجع وقت التقسيم الفعلي.
    """
    duration = get_duration(path, tr)
    if not 0 < at_seconds < duration:
        raise EditError(_t(tr, "editor_err_split_point", "وقت القص خارج مدة الملف"))
    point = at_seconds
    if not precise and has_video(path, tr):
        point = keyframe_before(path, at_seconds, tr)
        if point <= 0:
            raise EditError(_t(tr, "editor_err_no_keyframe",
                               "لا يوجد إطار مفتاحي قبل هذا الوقت؛ اختر وقتًا أبعد أو القص الدقيق"))

    def first_progress(fraction):
        if progress_callback:
            progress_callback(fraction * point / duration)

    def second_progress(fraction):
        if progress_callback:
            progress_callback((point + fraction * (duration - point)) / duration)

    _write([(path, 0.0, point)], first_output, cancel_event, first_progress, tr, precise)
    try:
        _write([(path, point, None)], second_output, cancel_event, second_progress, tr, precise)
    except BaseException:
        # جزء واحد بلا الآخر ليس تقسيمًا
        _cleanup(first_output)
        raise
    return point


def extract_segments(path, segments, output_path,
                     cancel_event=None, progress_callback=None, tr=None, precise=False):
    """
    يأخذ مقاطع متفرقة من ملف واحد ويضمها في ملف بالترتيب المعطى.

    segments: قائمة (بداية، نهاية) بالثواني.
    """
    duration = get_duration(path, tr)
    cleaned = []
    for start, end in segments:
        start = max(0.0, float(start))
        end = min(float(end), duration)
        if end <= start:
            raise EditError(_t(tr, "editor_err_segment", "نهاية المقطع يجب أن تكون بعد بدايته"))
        cleaned.append((path, start, end))
    _write(cleaned, output_path, cancel_event, progress_callback, tr, precise)


def merge_files(paths, output_path, cancel_event=None, progress_callback=None, tr=None):
    """يدمج الملفات بالترتيب المعطى في ملف واحد بصيغة الملف الأول."""
    if len(paths) < 2:
        raise EditError(_t(tr, "editor_err_merge_count", "الدمج يحتاج ملفين على الأقل"))
    _write([(p, 0.0, None) for p in paths], output_path, cancel_event, progress_callback, tr,
           merging=True)


class EditJobRunner:
    """
    ينفذ قائمة مهام قص أو دمج في خيط خلفي، فلا تتجمد النافذة.

    كل مهمة دالة تأخذ (cancel_event، progress_callback) ويُعرض اسمها
    للمستخدم. الدوال المرتدة تُستدعى من الخيط الخلفي؛ الواجهة تمررها
    إلى خيطها بـ wx.CallAfter.
    """

    def __init__(self, on_progress=None, on_job_done=None, on_all_done=None):
        self.on_progress = on_progress
        self.on_job_done = on_job_done
        self.on_all_done = on_all_done
        self._cancel_event = threading.Event()
        self._thread = None

    def start(self, jobs):
        """jobs: قائمة (اسم، دالة)."""
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, args=(jobs,), daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel_event.set()

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self, jobs):
        succeeded = failed = 0
        cancelled = False
        total = len(jobs)
        for index, (name, job) in enumerate(jobs, start=1):
            if self._cancel_event.is_set():
                cancelled = True
                break

            def progress(fraction, _index=index):
                if self.on_progress:
                    self.on_progress(_index, total, fraction)

            error = None
            try:
                job(self._cancel_event, progress)
                succeeded += 1
            except ConversionCancelled:
                cancelled = True
            except ConversionError as exc:
                error = str(exc)
                failed += 1
            except Exception as exc:
                _logger.exception("خطأ غير متوقع في مهمة القص أو الدمج: %s", name)
                error = str(exc)
                failed += 1
            if self.on_job_done and not cancelled:
                self.on_job_done(index, total, name, error)
            if cancelled:
                break
        if self.on_all_done:
            self.on_all_done(succeeded, failed, cancelled)
