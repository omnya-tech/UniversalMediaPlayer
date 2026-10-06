# -*- coding: utf-8 -*-
"""
محول صيغ الصوت والفيديو ومعالج الوسائط.
محدث بالتحويل الذكي الفوري (Smart Remuxing)، ضبط مزامنة الصوت والصورة لملفات .ts والتشفير بأقصى سرعة (Ultrafast Preset).
"""

import os
import threading
from fractions import Fraction

import av

from core.logging_setup import configure_logging

_logger = configure_logging()


def _safe_av_open(path, mode="r", format=None):
    if isinstance(path, str):
        try:
            if mode == "r":
                file_obj = open(path, "rb")
                return av.open(file_obj, mode="r", format=format)
            elif mode == "w":
                file_obj = open(path, "wb")
                return av.open(file_obj, mode="w", format=format)
        except Exception:
            pass
    return av.open(path, mode=mode, format=format)


# الجداول والدوال النقية انتقلت إلى core/formats.py (بلا استيراد av)؛
# إعادة تصديرها هنا تُبقي كل من يستورد من هذه الوحدة يعمل كما هو
from core.formats import (
    AUDIO_FORMATS,
    VIDEO_FORMATS,
    CRF_SUPPORTED_VCODECS,
    AUDIO_BITRATE_OPTIONS,
    AUDIO_SAMPLE_RATE_OPTIONS,
    ConversionError,
    ConversionCancelled,
    get_audio_bitrate_options,
    get_audio_sample_rate_options,
    get_audio_codec_for_extension,
    get_supported_target_extensions,
    is_lossless_audio_codec,
    pick_closest_audio_bitrate,
    resolve_audio_bitrate,
    smart_audio_bitrate,
    supported_sample_rate,
    target_supports_audio,
)


def probe_media_info(path: str, tr=None) -> dict:
    container = None
    try:
        container = _safe_av_open(path)
    except Exception as exc:
        msg = tr.t("conv_err_analyze", error=exc) if tr else f"تعذر تحليل الملف: {exc}"
        raise ConversionError(msg) from exc

    try:
        info = {
            "duration": None,
            "file_size": None,
            "container_format": None,
            "overall_bit_rate": None,
            "video": None,
            "audio": None,
        }

        if container.duration:
            info["duration"] = float(container.duration) / av.time_base

        if not info["duration"] or info["duration"] <= 0:
            max_stream_dur = 0.0
            for stream in container.streams:
                if stream.duration and stream.time_base:
                    try:
                        s_dur = float(stream.duration * stream.time_base)
                        if s_dur > max_stream_dur:
                            max_stream_dur = s_dur
                    except (TypeError, ZeroDivisionError):
                        pass
            if max_stream_dur > 0:
                info["duration"] = max_stream_dur

        if container.bit_rate:
            info["overall_bit_rate"] = int(container.bit_rate)
        if container.format is not None:
            info["container_format"] = container.format.long_name or container.format.name

        try:
            info["file_size"] = os.path.getsize(path)
        except OSError:
            pass

        video_stream = next((s for s in container.streams if s.type == "video"), None)
        if video_stream is not None:
            cc = video_stream.codec_context
            frame_rate = None
            if video_stream.average_rate:
                try:
                    frame_rate = float(video_stream.average_rate)
                except (TypeError, ZeroDivisionError):
                    frame_rate = None
            info["video"] = {
                "codec": cc.name if cc is not None else None,
                "width": getattr(cc, "width", None) or None,
                "height": getattr(cc, "height", None) or None,
                "frame_rate": frame_rate,
                "bit_rate": (getattr(cc, "bit_rate", None) or None),
            }

        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is not None:
            cc = audio_stream.codec_context
            channels = None
            try:
                channels = cc.channels
            except AttributeError:
                layout = getattr(cc, "layout", None)
                channels = getattr(layout, "channels", None) if layout is not None else None
            info["audio"] = {
                "codec": cc.name if cc is not None else None,
                "sample_rate": getattr(cc, "sample_rate", None) or None,
                "channels": channels or None,
                "bit_rate": (getattr(cc, "bit_rate", None) or None),
            }

        if info["video"] is None and info["audio"] is None:
            msg = tr.t("conv_err_no_valid_track_probe") if tr else "الملف لا يحتوي على مسار صوت أو فيديو صالح للتحليل"
            raise ConversionError(msg)

        return info
    finally:
        if container is not None:
            try:
                container.close()
            except Exception:
                pass


def convert_file(
    input_path: str,
    output_path: str,
    target_ext: str,
    is_video: bool,
    audio_bitrate: int,
    video_bitrate: int = None,
    progress_callback=None,
    cancel_event: threading.Event = None,
    sample_rate: int = None,
    channels: int = None,
    width: int = None,
    height: int = None,
    frame_rate: float = None,
    crf: int = None,
    tr=None,
):
    target_ext = target_ext.lower()
    if is_video:
        if target_ext not in VIDEO_FORMATS:
            msg = tr.t("conv_err_unsupported_video", ext=target_ext) if tr else f"صيغة الفيديو غير مدعومة: {target_ext}"
            raise ConversionError(msg)
        preset = VIDEO_FORMATS[target_ext]
    else:
        if target_ext not in AUDIO_FORMATS:
            msg = tr.t("conv_err_unsupported_audio", ext=target_ext) if tr else f"صيغة الصوت غير مدعومة: {target_ext}"
            raise ConversionError(msg)
        preset = AUDIO_FORMATS[target_ext]

    if preset.get("force_sample_rate"):
        sample_rate = preset["force_sample_rate"]
    if preset.get("force_channels"):
        channels = preset["force_channels"]

    no_transformations_requested = (
        width is None and height is None and frame_rate is None and
        sample_rate is None and channels is None
    )

    remux_successful = False
    if no_transformations_requested:
        in_container = None
        out_container = None
        try:
            in_container = _safe_av_open(input_path, mode="r")
            out_container = _safe_av_open(output_path, mode="w", format=preset.get("container"))

            stream_map = {}
            can_remux = True
            target_supports_audio_track = (not is_video) or preset.get("acodec") is not None

            for stream in in_container.streams:
                if stream.type == "video" and is_video:
                    try:
                        out_s = out_container.add_stream(template=stream)
                        stream_map[stream.index] = out_s
                    except Exception:
                        can_remux = False
                        break
                elif stream.type == "audio" and target_supports_audio_track:
                    try:
                        out_s = out_container.add_stream(template=stream)
                        stream_map[stream.index] = out_s
                    except Exception:
                        can_remux = False
                        break

            if can_remux and stream_map:
                total_duration = float(in_container.duration / av.time_base) if in_container.duration else 0.0

                first_pts = {}
                last_dts = {}

                for packet in in_container.demux(list(stream_map.keys())):
                    if cancel_event is not None and cancel_event.is_set():
                        raise ConversionCancelled()

                    if packet is None or packet.stream.index not in stream_map:
                        continue

                    out_stream = stream_map[packet.stream.index]
                    s_idx = packet.stream.index

                    if s_idx not in first_pts and packet.pts is not None:
                        first_pts[s_idx] = packet.pts

                    if s_idx in first_pts and packet.pts is not None:
                        packet.pts -= first_pts[s_idx]
                        if packet.dts is not None:
                            packet.dts -= first_pts[s_idx]

                    if s_idx in last_dts and packet.dts is not None and packet.dts <= last_dts[s_idx]:
                        packet.dts = last_dts[s_idx] + 1
                        if packet.pts is not None and packet.pts < packet.dts:
                            packet.pts = packet.dts

                    if packet.dts is not None:
                        last_dts[s_idx] = packet.dts

                    packet.stream = out_stream

                    try:
                        out_container.mux(packet)
                    except Exception:
                        continue

                    if progress_callback and total_duration > 0 and packet.pts is not None and packet.time_base:
                        current_time = float(packet.pts * packet.time_base)
                        progress_callback(min(1.0, max(0.0, current_time / total_duration)))

                in_container.close()
                out_container.close()
                remux_successful = True
                if progress_callback:
                    progress_callback(1.0)
                return
        except ConversionCancelled:
            raise
        except Exception:
            remux_successful = False
        finally:
            if in_container:
                try: in_container.close()
                except Exception: pass
            if out_container:
                try: out_container.close()
                except Exception: pass
            if not remux_successful and os.path.exists(output_path):
                try: os.remove(output_path)
                except OSError: pass

    in_container = None
    out_container = None
    try:
        try:
            in_container = _safe_av_open(input_path, mode="r")
        except Exception as exc:
            msg = tr.t("conv_err_open_source", error=exc) if tr else f"تعذر فتح الملف المصدر: {exc}"
            raise ConversionError(msg) from exc

        in_video_stream = next((s for s in in_container.streams if s.type == "video"), None)
        in_audio_stream = next((s for s in in_container.streams if s.type == "audio"), None)

        if in_audio_stream is None and (not is_video or in_video_stream is None):
            msg = tr.t("conv_err_no_valid_track_convert") if tr else "الملف المصدر لا يحتوي على مسار صوت أو فيديو صالح"
            raise ConversionError(msg)

        try:
            out_container = _safe_av_open(output_path, mode="w", format=preset.get("container"))
        except Exception as exc:
            msg = tr.t("conv_err_create_output", error=exc) if tr else f"تعذر إنشاء الملف الناتج: {exc}"
            raise ConversionError(msg) from exc

        out_video_stream = None
        if is_video and in_video_stream is not None:
            effective_frame_rate = frame_rate or in_video_stream.average_rate or 25
            vcodec_name = preset["vcodec"]
            out_video_stream = out_container.add_stream(vcodec_name, rate=effective_frame_rate)
            out_video_stream.width = width or in_video_stream.codec_context.width
            out_video_stream.height = height or in_video_stream.codec_context.height
            # الصيغ المتحركة (GIF وAPNG وWebP) لها تنسيق بكسل خاص بها
            out_video_stream.pix_fmt = preset.get("pix_fmt", "yuv420p")

            encoder_options = {"preset": "ultrafast", "tune": "zerolatency"}
            encoder_options.update(preset.get("codec_options") or {})
            if crf is not None and vcodec_name in CRF_SUPPORTED_VCODECS:
                encoder_options["crf"] = str(crf)
            elif video_bitrate:
                out_video_stream.bit_rate = video_bitrate
            
            out_video_stream.options = encoder_options

        target_supports_audio_track = (not is_video) or preset.get("acodec") is not None

        out_audio_stream = None
        resampler = None
        if in_audio_stream is not None and target_supports_audio_track:
            audio_codec_name = preset["acodec"] if is_video else preset["codec"]
            effective_sample_rate = sample_rate or in_audio_stream.codec_context.sample_rate or 44100
            # معدل لا يقبله المرمّز ينزل لأقرب معدل يقبله بدل فشل التحويل
            effective_sample_rate = supported_sample_rate(audio_codec_name, effective_sample_rate)
            # خيارات المرمّز تُمرَّر عند الإنشاء: Vorbis يرفض العمل بلا
            # strict=-2، وضبطها بعد الفتح لا يصل إليه
            out_audio_stream = out_container.add_stream(
                audio_codec_name,
                rate=effective_sample_rate,
                options=preset.get("codec_options") or {},
            )
            # «أعلى جودة» تُحسم هنا حسب الصيغة وعدد القنوات الفعلي، ورقم
            # فوق سقف المرمّز ينزل إليه بدل أن يفشل الترميز.
            # وبلا رقم أصلًا (صيغة بلا قائمة معدلات) يُؤخذ الافتراضي من
            # جدول الصيغة إن وُجد.
            # و«أعلى جودة» من أصل مضغوط بفقد لا تتجاوز ما يحفظ جودته
            # (شوف smart_audio_bitrate)
            effective_bitrate = smart_audio_bitrate(
                audio_codec_name, audio_bitrate,
                channels or in_audio_stream.codec_context.channels or 1,
                source_codec=in_audio_stream.codec_context.name,
                source_bitrate=in_audio_stream.codec_context.bit_rate or None,
            )
            if effective_bitrate:
                out_audio_stream.bit_rate = effective_bitrate
            elif preset.get("default_audio_bit_rate"):
                out_audio_stream.bit_rate = preset["default_audio_bit_rate"]
            if channels:
                out_audio_stream.layout = "mono" if channels == 1 else "stereo"
            resampler = av.AudioResampler(
                format=out_audio_stream.codec_context.format,
                layout=out_audio_stream.codec_context.layout,
                rate=out_audio_stream.codec_context.rate,
            )

        total_duration = None
        if in_container.duration:
            total_duration = float(in_container.duration) / av.time_base

        if not total_duration or total_duration <= 0:
            max_dur = 0.0
            for stream in in_container.streams:
                if stream.duration and stream.time_base:
                    try:
                        d = float(stream.duration * stream.time_base)
                        if d > max_dur:
                            max_dur = d
                    except (TypeError, ZeroDivisionError):
                        pass
            if max_dur > 0:
                total_duration = max_dur

        video_resample_interval = None
        next_video_output_time = 0.0
        if is_video and out_video_stream is not None and frame_rate:
            video_resample_interval = 1.0 / float(frame_rate)

        VIDEO_RESAMPLE_TIME_BASE = Fraction(1, 90000)
        video_resample_pts_step = None
        next_video_output_index = 0
        if video_resample_interval is not None:
            video_resample_pts_step = round(90000 / float(frame_rate))

        streams_to_demux = [s for s in (in_video_stream, in_audio_stream) if s is not None]
        if not is_video:
            streams_to_demux = [s for s in streams_to_demux if s.type != "video"]
        if not target_supports_audio_track:
            streams_to_demux = [s for s in streams_to_demux if s.type != "audio"]

        first_video_time = None
        first_audio_time = None

        for packet in in_container.demux(streams_to_demux):
            if cancel_event is not None and cancel_event.is_set():
                raise ConversionCancelled()

            if packet is None:
                continue

            if packet.stream.type == "video" and out_video_stream is not None:
                try:
                    for frame in packet.decode():
                        if first_video_time is None and frame.time is not None:
                            first_video_time = frame.time

                        raw_time = frame.time
                        norm_time = (raw_time - first_video_time) if (raw_time is not None and first_video_time is not None) else raw_time

                        frame.pts = None

                        if video_resample_interval is not None:
                            if norm_time is None:
                                continue
                            while norm_time >= next_video_output_time:
                                resampling_frame = frame
                                resampling_frame.pts = next_video_output_index * video_resample_pts_step
                                resampling_frame.time_base = VIDEO_RESAMPLE_TIME_BASE
                                for out_packet in out_video_stream.encode(resampling_frame):
                                    out_container.mux(out_packet)
                                next_video_output_index += 1
                                next_video_output_time += video_resample_interval
                        else:
                            for out_packet in out_video_stream.encode(frame):
                                out_container.mux(out_packet)

                        if progress_callback and total_duration and norm_time is not None:
                            progress_callback(min(1.0, max(0.0, float(norm_time) / total_duration)))
                except Exception:
                    continue

            elif packet.stream.type == "audio" and out_audio_stream is not None:
                try:
                    for frame in packet.decode():
                        if first_audio_time is None and frame.time is not None:
                            first_audio_time = frame.time

                        raw_time = frame.time
                        norm_time = (raw_time - first_audio_time) if (raw_time is not None and first_audio_time is not None) else raw_time

                        frame.pts = None

                        resampled_frames = resampler.resample(frame)
                        if not isinstance(resampled_frames, (list, tuple)):
                            resampled_frames = [resampled_frames] if resampled_frames else []

                        for resampled_frame in resampled_frames:
                            resampled_frame.pts = None
                            for out_packet in out_audio_stream.encode(resampled_frame):
                                out_container.mux(out_packet)

                        if (
                            progress_callback
                            and total_duration
                            and out_video_stream is None
                            and norm_time is not None
                        ):
                            progress_callback(min(1.0, max(0.0, float(norm_time) / total_duration)))
                except Exception:
                    continue

        if out_video_stream is not None:
            for out_packet in out_video_stream.encode(None):
                out_container.mux(out_packet)
        if out_audio_stream is not None:
            for out_packet in out_audio_stream.encode(None):
                out_container.mux(out_packet)

        if progress_callback:
            progress_callback(1.0)

    except ConversionCancelled:
        _logger.info("تم إلغاء تحويل الملف: %s", input_path)
        raise
    except ConversionError:
        raise
    except Exception as exc:
        _logger.exception("خطأ غير متوقع أثناء تحويل الملف: %s", input_path)
        msg = tr.t("conv_err_unexpected", error=exc) if tr else f"حدث خطأ غير متوقع أثناء التحويل: {exc}"
        raise ConversionError(msg) from exc
    finally:
        if out_container is not None:
            try:
                out_container.close()
            except Exception:
                pass
        if in_container is not None:
            try:
                in_container.close()
            except Exception:
                pass

        cancelled_or_failed = cancel_event is not None and cancel_event.is_set()
        if cancelled_or_failed and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


class BatchConverter:
    def __init__(self, on_file_progress=None, on_file_done=None, on_batch_done=None, tr=None):
        self.on_file_progress = on_file_progress
        self.on_file_done = on_file_done
        self.on_batch_done = on_batch_done
        self.tr = tr
        self._cancel_event = threading.Event()
        self._thread = None

    def start(self, jobs):
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, args=(jobs,), daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel_event.set()

    def _run(self, jobs):
        total = len(jobs)
        succeeded = 0
        failed = 0
        cancelled = False

        for index, job in enumerate(jobs, start=1):
            if self._cancel_event.is_set():
                cancelled = True
                break

            filename = os.path.basename(job["input_path"])

            def _progress(fraction, _index=index, _total=total, _filename=filename):
                if self.on_file_progress:
                    self.on_file_progress(_index, _total, _filename, fraction)

            error_message = None
            success = False
            try:
                convert_file(
                    job["input_path"],
                    job["output_path"],
                    job["target_ext"],
                    job["is_video"],
                    job["audio_bitrate"],
                    job.get("video_bitrate"),
                    progress_callback=_progress,
                    cancel_event=self._cancel_event,
                    sample_rate=job.get("sample_rate"),
                    channels=job.get("channels"),
                    width=job.get("width"),
                    height=job.get("height"),
                    frame_rate=job.get("frame_rate"),
                    crf=job.get("crf"),
                    tr=self.tr,
                )
                success = True
                succeeded += 1
            except ConversionCancelled:
                cancelled = True
            except ConversionError as exc:
                error_message = str(exc)
                failed += 1
            except Exception as exc:
                _logger.exception("خطأ غير متوقع في BatchConverter لملف: %s", filename)
                error_message = str(exc)
                failed += 1

            if self.on_file_done:
                self.on_file_done(index, total, filename, success, error_message)

            if cancelled:
                break

        if self.on_batch_done:
            self.on_batch_done(succeeded, failed, cancelled)