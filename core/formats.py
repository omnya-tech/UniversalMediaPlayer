# -*- coding: utf-8 -*-
"""
جداول صيغ الصوت والفيديو والدوال النقية اللي بتقرأ منها.

الوحدة دي **مالهاش أي استيراد** عن قصد - ولا حتى av.

السبب: الجداول دي مجرد قواميس نصوص، لكنها كانت ساكنة جوه
core/converter.py اللي أول سطر فيه "import av". فأي وحدة عايزة اسم
صيغة كانت بتجرّ مكتبات FFmpeg كاملة معاها - وده وحده كان بياخد 2.45
ثانية عند كل فتح للبرنامج، قبل ما النافذة تظهر أصلاً.

core/converter.py بيعيد تصدير كل الأسماء دي، فأي كود بيستورد منه
لسه شغال زي ما هو بلا تعديل.
"""

AUDIO_FORMATS = {
    ".mp3":  {"codec": "libmp3lame", "container": "mp3"},
    ".m4r":   {"codec": "aac", "container": "ipod"},
    ".wav":  {"codec": "pcm_s16le", "container": "wav"},
    ".wma":   {"codec": "wmav2", "container": "asf", "default_audio_bit_rate": 128000},
    ".xwma":  {"codec": "wmav2", "container": "asf", "default_audio_bit_rate": 128000},
    ".flac": {"codec": "flac", "container": "flac"},
    ".aac":  {"codec": "aac", "container": "adts"},
    ".m4a":  {"codec": "aac", "container": "ipod"},
    ".m4b":  {"codec": "aac", "container": "ipod"},
    ".m4p":  {"codec": "aac", "container": "ipod"},
    ".ogg":   {"codec": "vorbis", "container": "ogg", "codec_options": {"strict": "-2"}, "force_channels": 2},
    ".oga":   {"codec": "vorbis", "container": "ogg", "codec_options": {"strict": "-2"}, "force_channels": 2},
    ".opus":  {"codec": "libopus", "container": "opus", "force_sample_rate": 48000},
    ".aiff": {"codec": "pcm_s16be", "container": "aiff"},
    ".aif":  {"codec": "pcm_s16be", "container": "aiff"},
    ".au":   {"codec": "pcm_s16be", "container": "au"},
    ".ac3":  {"codec": "ac3", "container": "ac3"},
    ".eac3": {"codec": "eac3", "container": "eac3"},
    ".alac": {"codec": "alac", "container": "ipod"},
    ".tta":  {"codec": "tta", "container": "tta"},
    ".wv":   {"codec": "wavpack", "container": "wv"},
    ".voc":  {"codec": "pcm_u8", "container": "voc"},
    ".weba":  {"codec": "libopus", "container": "webm", "force_sample_rate": 48000},
    ".caf":  {"codec": "pcm_s16le", "container": "caf"},
    ".mp2":  {"codec": "mp2", "container": "mp2"},
    ".mpa":  {"codec": "mp2", "container": "mp2"},
    ".ts":   {"codec": "aac", "container": "mpegts"},
    ".tsa":  {"codec": "aac", "container": "mpegts"},
    ".mus":  {"codec": "aac", "container": "mp4"},
    ".ra":    {"codec": "real_144", "container": "rm", "force_sample_rate": 8000, "force_channels": 1},
    ".ram":   {"codec": "real_144", "container": "rm", "force_sample_rate": 8000, "force_channels": 1},
    ".snd":  {"codec": "pcm_s16be", "container": "au"},
    ".w64":  {"codec": "pcm_s16le", "container": "w64"},
    ".amr":   {"codec": "libopencore_amrnb", "container": "amr", "force_sample_rate": 8000, "force_channels": 1},
}

VIDEO_FORMATS = {
    ".mp4":  {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".mkv":  {"vcodec": "libx264", "acodec": "aac", "container": "matroska"},
    ".webm":  {"vcodec": "libvpx-vp9", "acodec": "libopus", "container": "webm", "force_sample_rate": 48000},
    ".gif":   {"vcodec": "gif", "acodec": None, "container": "gif", "pix_fmt": "rgb8"},
    ".apng":  {"vcodec": "apng", "acodec": None, "container": "apng", "pix_fmt": "rgba"},
    ".webp":  {"vcodec": "libwebp_anim", "acodec": None, "container": "webp", "pix_fmt": "yuv420p"},
    ".avi":  {"vcodec": "mpeg4", "acodec": "libmp3lame", "container": "avi"},
    ".mov":  {"vcodec": "libx264", "acodec": "aac", "container": "mov"},
    ".flv":  {"vcodec": "flv", "acodec": "libmp3lame", "container": "flv"},
    ".wmv":   {"vcodec": "wmv2", "acodec": "wmav2", "container": "asf", "default_audio_bit_rate": 128000},
    ".3gp":  {"vcodec": "mpeg4", "acodec": "aac", "container": "3gp"},
    ".3g2":  {"vcodec": "mpeg4", "acodec": "aac", "container": "3gp"},
    ".3gpp": {"vcodec": "mpeg4", "acodec": "aac", "container": "3gp"},
    ".3gp2": {"vcodec": "mpeg4", "acodec": "aac", "container": "3gp"},
    ".ts":   {"vcodec": "libx264", "acodec": "aac", "container": "mpegts"},
    ".mts":  {"vcodec": "libx264", "acodec": "aac", "container": "mpegts"},
    ".m2ts": {"vcodec": "libx264", "acodec": "aac", "container": "mpegts"},
    ".m2t":  {"vcodec": "libx264", "acodec": "aac", "container": "mpegts"},
    ".m4v":  {"vcodec": "libx264", "acodec": "aac", "container": "ipod"},
    ".mp4v": {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".mpg":  {"vcodec": "mpeg2video", "acodec": "mp2", "container": "mpeg"},
    ".mpeg": {"vcodec": "mpeg2video", "acodec": "mp2", "container": "mpeg"},
    ".mpe":  {"vcodec": "mpeg2video", "acodec": "mp2", "container": "mpeg"},
    ".m1v":  {"vcodec": "mpeg1video", "acodec": "mp2", "container": "mpeg"},
    ".m2v":  {"vcodec": "mpeg2video", "acodec": "mp2", "container": "mpeg"},
    ".vob":  {"vcodec": "mpeg2video", "acodec": "ac3", "container": "vob"},
    ".asf":   {"vcodec": "wmv2", "acodec": "wmav2", "container": "asf", "default_audio_bit_rate": 128000},
    ".divx": {"vcodec": "mpeg4", "acodec": "libmp3lame", "container": "avi"},
    ".f4v":  {"vcodec": "libx264", "acodec": "aac", "container": "flv"},
    ".mxf":   {"vcodec": "mpeg2video", "acodec": "pcm_s16le", "container": "mxf", "force_sample_rate": 48000},
    ".qt":   {"vcodec": "libx264", "acodec": "aac", "container": "mov"},
    ".wtv":  {"vcodec": "mpeg2video", "acodec": "ac3", "container": "wtv"},
    ".y4m":  {"vcodec": "rawvideo", "acodec": None, "container": "yuv4mpegpipe"},
    ".nut":  {"vcodec": "libx264", "acodec": "aac", "container": "nut"},
    ".mas":  {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".npa":  {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".swf":  {"vcodec": "flv", "acodec": "mp3", "container": "swf"},
    ".h264": {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".h265": {"vcodec": "libx265", "acodec": "aac", "container": "mp4"},
    ".hevc": {"vcodec": "libx265", "acodec": "aac", "container": "mp4"},
    ".vp9":   {"vcodec": "libvpx-vp9", "acodec": "libopus", "container": "webm", "force_sample_rate": 48000},
    ".av1":   {"vcodec": "libsvtav1", "acodec": "libopus", "container": "webm", "force_sample_rate": 48000},
    ".csf":  {"vcodec": "libx264", "acodec": "aac", "container": "mp4"},
    ".dav":  {"vcodec": "mpeg4", "acodec": "libmp3lame", "container": "avi"},
    ".drc":   {"vcodec": "libx264", "acodec": "aac", "container": "matroska"},
    ".ifo":  {"vcodec": "mpeg2video", "acodec": "ac3", "container": "vob"},
    ".svi":  {"vcodec": "mpeg4", "acodec": "mp3", "container": "avi"},
    ".xvid": {"vcodec": "mpeg4", "acodec": "libmp3lame", "container": "avi"},
    ".dat":  {"vcodec": "mpeg1video", "acodec": "mp2", "container": "mpeg"},
    ".rec":  {"vcodec": "mpeg2video", "acodec": "mp2", "container": "mpegts"},
    ".xesc": {"vcodec": "mpeg4", "acodec": "mp3", "container": "asf"},
    ".ivf":  {"vcodec": "libvpx-vp9", "acodec": None, "container": "ivf"},
}

CRF_SUPPORTED_VCODECS = {"libx264", "libx265", "libvpx-vp9", "libsvtav1"}

AUDIO_BITRATE_OPTIONS = {
    "libmp3lame": (
        32_000, 40_000, 48_000, 56_000, 64_000, 80_000, 96_000, 112_000,
        128_000, 160_000, 192_000, 224_000, 256_000, 320_000,
    ),
    "mp2": (
        32_000, 48_000, 56_000, 64_000, 80_000, 96_000, 112_000, 128_000,
        160_000, 192_000, 224_000, 256_000, 320_000, 384_000,
    ),
    "ac3": (
        32_000, 40_000, 48_000, 56_000, 64_000, 80_000, 96_000, 112_000,
        128_000, 160_000, 192_000, 224_000, 256_000, 320_000, 384_000,
        448_000, 512_000, 576_000, 640_000,
    ),
    "eac3": (
        32_000, 40_000, 48_000, 56_000, 64_000, 80_000, 96_000, 112_000,
        128_000, 160_000, 192_000, 224_000, 256_000, 320_000, 384_000,
        448_000, 512_000, 576_000, 640_000,
    ),
    "aac": (
        32_000, 48_000, 64_000, 96_000, 128_000, 160_000, 192_000,
        224_000, 256_000, 320_000,
    ),
    "libopus": (
        16_000, 32_000, 64_000, 96_000, 128_000, 160_000, 192_000,
        256_000, 320_000, 510_000,
    ),
    "libvorbis": (
        45_000, 64_000, 96_000, 128_000, 160_000, 192_000, 224_000,
        256_000, 320_000, 500_000,
    ),
    "wmav2": (32_000, 48_000, 64_000, 96_000, 128_000, 160_000, 192_000, 256_000, 320_000),
    "amr_nb": (4_750, 5_150, 5_900, 6_700, 7_400, 7_950, 10_200, 12_200),
}

AUDIO_SAMPLE_RATE_OPTIONS = {
    "amr_nb": (8_000,),
    "libmp3lame": (8_000, 11_025, 12_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000),
    "mp2": (16_000, 22_050, 24_000, 32_000, 44_100, 48_000),
    "ac3": (32_000, 44_100, 48_000),
    "eac3": (32_000, 44_100, 48_000),
    "libopus": (8_000, 12_000, 16_000, 24_000, 48_000),
    "aac": (8_000, 11_025, 12_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000, 96_000),
    "libvorbis": (8_000, 11_025, 16_000, 22_050, 32_000, 44_100, 48_000, 96_000),
    "wmav2": (8_000, 11_025, 16_000, 22_050, 32_000, 44_100, 48_000),
}


# قيمة محفوظة خاصة معناها «أعلى معدل تدعمه الصيغة الحالية»، أيًّا كانت.
# صفر لأنه ليس معدل بت حقيقيًا لأي مرمّز، فلا يلتبس بقيمة اختارها المستخدم.
HIGHEST_AUDIO_BITRATE = 0


def get_audio_bitrate_options(codec_name: str = None):
    if codec_name is None:
        return AUDIO_BITRATE_OPTIONS.get("aac")
    return AUDIO_BITRATE_OPTIONS.get(codec_name)


# مرمّزات سقفها لكل قناة لا للملف كله: Opus يرفض ما فوق 256 ألفًا للقناة
# الواحدة، فالأحادي سقفه 256 ألفًا لا 510.
_PER_CHANNEL_BITRATE_CEILING = {
    "libopus": 256_000,
}


def highest_audio_bitrate(codec_name: str, channels: int = 1):
    """أعلى معدل بت المرمّز ده بيدعمه فعلًا، أو None لو مفيش معدل بت ينطبق."""
    options = get_audio_bitrate_options(codec_name)
    if not options:
        return None

    ceiling = options[-1]
    per_channel = _PER_CHANNEL_BITRATE_CEILING.get(codec_name)
    if per_channel:
        ceiling = min(ceiling, per_channel * max(1, int(channels or 1)))

    usable = [value for value in options if value <= ceiling]
    return usable[-1] if usable else options[0]


def resolve_audio_bitrate(codec_name: str, stored_bitrate: int, channels: int = 1):
    """
    المعدل الفعلي للترميز من القيمة المحفوظة.

    القيمة المحفوظة ممكن تبقى HIGHEST_AUDIO_BITRATE، وساعتها بنطلع
    سقف الصيغة الحالية. أي رقم غيره بيتاخد كما هو، إلا لو كان فوق سقف
    المرمّز - ساعتها بينزل للسقف بدل ما الترميز يفشل من أصله.
    """
    ceiling = highest_audio_bitrate(codec_name, channels)
    if not stored_bitrate:
        return ceiling
    if ceiling and stored_bitrate > ceiling:
        return ceiling
    return stored_bitrate


def is_lossless_audio_codec(codec_name: str) -> bool:
    return codec_name not in AUDIO_BITRATE_OPTIONS


def get_audio_sample_rate_options(codec_name: str):
    return AUDIO_SAMPLE_RATE_OPTIONS.get(codec_name)


def get_audio_codec_for_extension(target_ext: str, is_video: bool = False):
    """
    مرمّز الصوت للامتداد ده، أو None لو مش معروف.

    None لا "aac": الافتراضي الصامت كان بيخلي الواجهة تعرض معدلات بت AAC
    لصيغة مش موجودة أصلًا. والسيناريو ده حقيقي - إعداد محفوظ لصيغة
    اتشالت من الجداول (بعد تدقيق الصيغ المكسورة) بيوصل هنا. المستدعيين
    بيخفوا حقل معدل البت لما يرجع None، وده الصح.
    """
    if not target_ext:
        return None
    preset = (VIDEO_FORMATS if is_video else AUDIO_FORMATS).get(target_ext.lower())
    if not preset:
        return None
    return preset.get("acodec") if is_video else preset.get("codec")


def pick_closest_audio_bitrate(options_or_desired, desired_bitrate: int = None) -> int:
    if desired_bitrate is None:
        desired = options_or_desired
        opts = AUDIO_BITRATE_OPTIONS.get("aac", (192_000,))
    else:
        opts = options_or_desired
        desired = desired_bitrate

    if not opts:
        return desired or 192_000
    if not desired or desired <= 0:
        # بلا قيمة مطلوبة: الأعلى، وهو الافتراضي الجديد لمعدل البت
        return opts[-1]
    return min(opts, key=lambda value: abs(value - desired))


def target_supports_audio(target_ext: str, is_video: bool = False) -> bool:
    if not is_video:
        return True
    preset = VIDEO_FORMATS.get(target_ext.lower())
    return bool(preset) and preset.get("acodec") is not None


class ConversionError(Exception):
    """خطأ يحدث أثناء عملية التحويل أو التقسيم."""


class ConversionCancelled(Exception):
    """إلغاء العملية بطلب من المستخدم."""


def get_supported_target_extensions(is_video: bool = False):
    return sorted(VIDEO_FORMATS.keys()) if is_video else sorted(AUDIO_FORMATS.keys())

