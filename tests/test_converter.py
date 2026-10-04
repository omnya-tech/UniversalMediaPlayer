# -*- coding: utf-8 -*-
"""
اختبارات تكاملية لـ core.converter.probe_media_info() باستخدام ملف
وسائط صغير حقيقي (مولَّد بـ PyAV، مش mock) - عشان نتأكد إن التحليل
بيرجّع خصائص حقيقية فعلًا (مش أرقام تخمينية أو ثابتة)، وإن أي خاصية
غير معلنة في الملف بترجع None صراحةً بدل قيمة افتراضية.

الاختبارات دي بتحتاج مكتبة PyAV (av) متاحة في البيئة (للتوليد
وللتحليل). لو مش متاحة، الاختبارات بتتخطى (skip) تلقائيًا.
"""

import pytest

try:
    import av  # noqa: F401
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False

from core.converter import (
    ConversionError,
    get_audio_bitrate_options,
    get_audio_codec_for_extension,
    get_audio_sample_rate_options,
    is_lossless_audio_codec,
    pick_closest_audio_bitrate,
    probe_media_info,
)
from tests.media_samples import write_sample_media

requires_av = pytest.mark.skipif(not AV_AVAILABLE, reason="مكتبة PyAV غير متاحة في هذه البيئة")


@pytest.fixture(scope="module")
def sample_video_file(tmp_path_factory):
    out_path = str(tmp_path_factory.mktemp("media") / "sample.mp4")
    write_sample_media(out_path, audio_bit_rate=128_000, video_bit_rate=500_000)
    return out_path


@pytest.fixture(scope="module")
def sample_audio_only_file(tmp_path_factory):
    out_path = str(tmp_path_factory.mktemp("media") / "sample.mp3")
    write_sample_media(out_path, with_video=False, audio_codec="libmp3lame",
                       audio_bit_rate=192_000)
    return out_path


@requires_av
def test_probe_media_info_video_file_reports_real_properties(sample_video_file):
    info = probe_media_info(sample_video_file)

    assert info["duration"] == pytest.approx(2.0, abs=0.3)
    assert info["file_size"] > 0
    assert info["container_format"] is not None

    assert info["video"] is not None
    assert info["video"]["codec"] is not None
    assert info["video"]["width"] == 160
    assert info["video"]["height"] == 120
    assert info["video"]["frame_rate"] == pytest.approx(10.0, abs=1.0)

    assert info["audio"] is not None
    assert info["audio"]["sample_rate"] is not None


@requires_av
def test_probe_media_info_audio_only_file_has_no_video_key(sample_audio_only_file):
    info = probe_media_info(sample_audio_only_file)

    assert info["video"] is None
    assert info["audio"] is not None
    assert info["audio"]["codec"] is not None
    # bit_rate هنا لازم يكون رقم حقيقي مستخرج من الملف (فُرِض 192kbps
    # وقت التوليد)، مش None ومش رقم تخميني ثابت
    bit_rate = info["audio"]["bit_rate"] or info["overall_bit_rate"]
    assert bit_rate is not None
    assert bit_rate > 0


@requires_av
def test_probe_media_info_missing_file_raises_conversion_error():
    with pytest.raises(ConversionError):
        probe_media_info("/this/path/does/not/exist.mp3")


# ------------------------------------------------------------------------ #
# جدول معدلات البت الحقيقية (core.converter.AUDIO_BITRATE_OPTIONS) - دول
# اختبارات منطق بايثون خالص، مش محتاجة av ولا ffmpeg فعلًا، عشان تشتغل
# حتى لو المكتبتين دول مش متاحين في بيئة الاختبار.
# ------------------------------------------------------------------------ #

def test_mp3_real_maximum_bitrate_is_320_not_a_guess():
    """أقصى معدل بت حقيقي لـ MP3 (MPEG-1 Layer III) هو 320 كيلوبت/ث -
    مفروض رسميًا من مواصفة الصيغة نفسها (ISO/IEC 11172-3)، مش رقم
    تخميني. 96 كيلوبت/ث موجودة كخطوة وسط الجدول، مش أقصى قيمة."""
    options = get_audio_bitrate_options("libmp3lame")
    assert options[-1] == 320_000
    assert 96_000 in options


def test_mp2_has_a_different_real_table_than_mp3():
    """MP2 (MPEG-1 Layer II) صيغة مختلفة عن MP3 (Layer III) رغم تشابه
    الاسم، وله جدول قيم رسمي منفصل تمامًا وأقصى أعلى (384 بدل 320)."""
    mp3_options = get_audio_bitrate_options("libmp3lame")
    mp2_options = get_audio_bitrate_options("mp2")
    assert mp2_options[-1] == 384_000
    assert mp2_options != mp3_options


def test_lossless_codecs_report_no_bitrate_options():
    for codec in ("pcm_s16le", "pcm_s16be", "pcm_u8", "flac", "alac", "tta", "wavpack"):
        assert get_audio_bitrate_options(codec) is None
        assert is_lossless_audio_codec(codec) is True


def test_lossy_codecs_are_not_reported_as_lossless():
    for codec in ("libmp3lame", "mp2", "aac", "libopus", "libvorbis", "wmav2", "ac3", "eac3", "amr_nb"):
        assert is_lossless_audio_codec(codec) is False


def test_amr_bitrate_ceiling_is_far_below_typical_music_presets():
    """قبل إضافة الجدول ده، كان بالإمكان اختيار "جودة عالية" (256 كيلوبت/ث)
    مع .amr كصيغة هدف - قيمة غير صالحة إطلاقًا لهذا الترميز (أقصاه
    الحقيقي 12.2 كيلوبت/ث بس، ترميز صوت بشري لمكالمات مش موسيقى) وكانت
    بتفشّل التحويل دايمًا."""
    options = get_audio_bitrate_options("amr_nb")
    assert options[-1] == 12_200
    assert 256_000 not in options
    assert pick_closest_audio_bitrate(options, 256_000) == 12_200


def test_get_audio_codec_for_extension_matches_real_encoder_used():
    assert get_audio_codec_for_extension(".mp3", is_video=False) == "libmp3lame"
    assert get_audio_codec_for_extension(".wav", is_video=False) == "pcm_s16le"
    assert get_audio_codec_for_extension(".mp4", is_video=True) == "aac"
    assert get_audio_codec_for_extension(".unknown_ext", is_video=False) is None


def test_mpa_extension_shares_real_mp2_tables():
    """.mpa امتداد بديل شائع لصوت MPEG (Layer II غالبًا)، بيُعامَل بنفس
    مرمّز/جدول .mp2 الرسمي بالظبط - مش جدول تخميني منفصل."""
    assert get_audio_codec_for_extension(".mpa", is_video=False) == "mp2"
    mpa_bitrates = get_audio_bitrate_options("mp2")
    assert mpa_bitrates[-1] == 384_000


def test_pick_closest_audio_bitrate_picks_nearest_not_first():
    options = (32_000, 64_000, 128_000, 256_000)
    assert pick_closest_audio_bitrate(options, 130_000) == 128_000
    assert pick_closest_audio_bitrate(options, 1_000_000) == 256_000
    # صفر/بلا قيمة معناه «أعلى جودة» - الافتراضي الجديد لمعدل البت
    assert pick_closest_audio_bitrate(options, 0) == 256_000


def test_mp3_does_not_support_96khz_despite_old_generic_list():
    """القائمة العامة القديمة كانت بتعرض 96000 هرتز كخيار متاح مع أي
    صيغة، لكن MP3 (MPEG-1/2/2.5 Layer III) مش بيدعم 96 كيلوهرتز إطلاقًا
    حسب مواصفته الرسمية."""
    mp3_rates = get_audio_sample_rate_options("libmp3lame")
    assert 96_000 not in mp3_rates
    assert 44_100 in mp3_rates
    assert 48_000 in mp3_rates


def test_amr_supports_exactly_one_sample_rate():
    assert get_audio_sample_rate_options("amr_nb") == (8_000,)


def test_flexible_codecs_support_high_sample_rates():
    assert 96_000 in get_audio_sample_rate_options("aac")


def test_lossless_codecs_have_no_sample_rate_restriction():
    for codec in ("pcm_s16le", "pcm_s16be", "pcm_u8", "flac", "alac", "tta", "wavpack"):
        assert get_audio_sample_rate_options(codec) is None
