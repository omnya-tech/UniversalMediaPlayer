# -*- coding: utf-8 -*-
"""
منطق معادل الصوت (Equalizer) - بلا أي استيراد لـ vlc عن قصد.

المعادل نفسه بيطبّقه libvlc (شوف PlayerEngine.set_equalizer). هنا بس:
أسماء الأنماط بترتيبها في libvlc، وحدود القيم، والتنقّل بين الأنماط
بالكيبورد. كده المنطق ده يتختبر من غير VLC، ومن غير ما الواجهة تستورد
المحرك.

النمط (mode) نص واحد من:
- "off": المعادل مطفي
- مفتاح نمط جاهز من PRESET_KEYS (رقمه في libvlc هو ترتيبه في الصف)
- "custom": قيم المستخدم المحفوظة في الإعدادات
"""

# نفس ترتيب libvlc_audio_equalizer_get_preset_name بالظبط: الرقم هو
# اللي بيتبعت لـ libvlc، فأي تغيير في الترتيب بيبدّل الأنماط ببعض.
# (اتأكدنا منه على libvlc 3.0.23)
PRESET_KEYS = (
    "flat", "classical", "club", "dance", "full_bass", "full_bass_treble",
    "full_treble", "headphones", "large_hall", "live", "party", "pop",
    "reggae", "rock", "ska", "soft", "soft_rock", "techno",
)

MODE_OFF = "off"
MODE_CUSTOM = "custom"

# الترددات الثابتة لنطاقات libvlc العشرة بالهرتز
BAND_FREQUENCIES = (31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
BAND_COUNT = len(BAND_FREQUENCIES)

# حدود libvlc نفسها للتضخيم المسبق ولكل نطاق
MIN_GAIN_DB = -20.0
MAX_GAIN_DB = 20.0


def all_modes(has_custom: bool = True):
    """كل الأنماط بترتيب التنقّل: مطفي، ثم الجاهزة، ثم المخصص."""
    modes = (MODE_OFF,) + PRESET_KEYS
    return modes + (MODE_CUSTOM,) if has_custom else modes


def is_valid_mode(mode) -> bool:
    return mode in all_modes()


def preset_index(mode):
    """رقم النمط الجاهز في libvlc، أو None لو مش نمط جاهز."""
    try:
        return PRESET_KEYS.index(mode)
    except ValueError:
        return None


def clamp_gain(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if value != value:  # NaN
        return 0.0
    return max(MIN_GAIN_DB, min(MAX_GAIN_DB, value))


def normalize_bands(bands):
    """
    قائمة بعشر قيم صالحة دايمًا.

    الإعدادات ممكن تكون متعدّلة يدويًا أو من نسخة قديمة: الناقص بيتكمّل
    أصفار، والزيادة بتتشال، وأي قيمة غريبة بتبقى صفر.
    """
    if not isinstance(bands, (list, tuple)):
        bands = []
    values = [clamp_gain(v) for v in bands[:BAND_COUNT]]
    return values + [0.0] * (BAND_COUNT - len(values))


def cycle_mode(current: str, step: int, has_custom: bool) -> str:
    """
    النمط اللي بعده (step=1) أو اللي قبله (step=-1) مع الالتفاف.

    "مخصص" بيدخل في الدورة بس لو المستخدم حفظ قيم فعلًا - من غيرها هو
    هو "مسطّح" تحت اسم تاني، وده يلخبط.
    """
    modes = all_modes(has_custom)
    try:
        index = modes.index(current)
    except ValueError:
        index = 0
    return modes[(index + step) % len(modes)]


def format_frequency(hz) -> str:
    """31.25 -> "31"، 1000 -> "1k"، 16000 -> "16k" - للأسماء المنطوقة."""
    if hz >= 1000:
        k = hz / 1000
        return f"{k:g}k"
    return f"{int(hz)}"
