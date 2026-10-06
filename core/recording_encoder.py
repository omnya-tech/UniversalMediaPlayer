# -*- coding: utf-8 -*-
"""
ترميز التسجيل مباشرة أثناء الالتقاط (MP3 وM4A وغيرهما) بلا ملف WAV وسيط:
اختيار معدل يقبله المرمّز فعلًا، وفتح الحاوية، وترميز كل كتلة.

نُقلت كما هي من core/audio_recorder.py.
"""

import os

import numpy as np

from core.recording_common import RecorderError
from core.logging_setup import configure_logging

_logger = configure_logging()


class DirectEncoderMixin:
    """الترميز المباشر للتسجيل."""

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

        self._av_format = "s16" if self._bit_depth == 16 else "s32"  # 24 بت داخل s32
        self._av_layout = "mono" if self._channels == 1 else "stereo"

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
