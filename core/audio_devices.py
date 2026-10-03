# -*- coding: utf-8 -*-
"""
التعرّف على أجهزة الإدخال والتعامل معها مباشرة.

المشكلة اللي بيحلّها الملف ده: ويندوز بيعرض نفس المايكروفون أربع مرات،
مرة لكل واجهة صوت (MME و DirectSound و WASAPI و WDM-KS). والمستخدم
الكفيف بيلاقي عشرين مدخل في القائمة لستة أجهزة حقيقية، وأسماء فيها
مسارات تعريفات وأسطر جديدة.

والأهم إن الواجهات مش متساوية:

    نفس المايكروفون (RG6818) على الجهاز ده:
      MME              معدل 44100 (وهمي)   زمن استجابة  90 م.ث
      DirectSound      معدل 44100 (وهمي)   زمن استجابة 120 م.ث
      WASAPI           معدل 192000 (حقيقي) زمن استجابة   3 م.ث
      WDM-KS           معدل 192000 (حقيقي) زمن استجابة  10 م.ث

MME و DirectSound بيكذبوا: بيقولوا 44100 لأي جهاز مهما كان. WASAPI
بيتكلم مع الجهاز مباشرة فبيقول معدله الحقيقي.

الملف ما بيستوردش أي حاجة من الواجهة، علشان يتختبر لوحده.
"""

import re

try:
    import sounddevice as sd
except Exception:
    sd = None


# ترتيب الأفضلية بين الواجهات: الأقل زمن استجابة والأصدق في المعدل أولًا.
HOST_API_PRIORITY = (
    "Windows WASAPI",
    "Windows DirectSound",
    "MME",
)

# WDM-KS مستبعدة: بتفتح الجهاز حصريًا وتفشل كتير مع تعريفات معيّنة،
# وأسماؤها فيها مسارات التعريف. WASAPI بتدي نفس المعدل الحقيقي من غير
# المشاكل دي.
EXCLUDED_HOST_APIS = ("Windows WDM-KS",)

# MME بتقصّ أسماء الأجهزة على 31 حرفًا، فالمقارنة لازم تقصّ زيها.
_MME_NAME_LIMIT = 31

# المعدلات اللي بتتجرّب بعد معدل الجهاز الأصلي، من الأعلى للأقل.
FALLBACK_RATES = (48000, 44100, 32000, 22050, 16000, 8000)

# مداخل افتراضية بيعرضها ويندوز وهي مش أجهزة حقيقية، بكل اللغات اللي
# ممكن الويندوز يكون بيها.
_VIRTUAL_NAMES = (
    "sound mapper",
    "primary sound capture driver",
    "مخطط صوت",
    "محوّل الصوت الأساسي",
    "محول الصوت الأساسي",
    "برنامج تشغيل التقاط الصوت",
    "mappeur de sons",
    "primärer soundaufnahmetreiber",
    "soundzuordnung",
    "asignador de sonido",
    "mapeador de som",
)

# مسار التعريف في أسماء WDM-KS: @System32\drivers\...;...;(الاسم المفيد)
_DRIVER_PATH = re.compile(r"@[^;]*;[^;]*;?\s*\(([^)]+)\)")


def clean_device_name(raw_name):
    """
    اسم مقروء من اسم ويندوز الخام.

    أسماء WDM-KS بتيجي فيها مسار التعريف ورموز ومحارف سطر جديد. الاسم
    المفيد للمستخدم بيكون في آخر قوس.
    """
    if not raw_name:
        return ""
    # أسطر جديدة ومسافات متكررة إلى مسافة واحدة
    name = " ".join(str(raw_name).split())

    match = _DRIVER_PATH.search(name)
    if match:
        return match.group(1).strip()

    return name.strip()


def is_virtual_device(name):
    lowered = (name or "").lower()
    return any(marker in lowered for marker in _VIRTUAL_NAMES)


class AudioDevice:
    """
    جهاز إدخال حقيقي واحد، بأفضل واجهة متاحة له.

    alternatives فيها باقي الواجهات لنفس الجهاز، للرجوع لها لو الأفضل
    فشل وقت التشغيل الفعلي.
    """

    __slots__ = ("name", "index", "host_api", "native_rate",
                 "max_channels", "latency_ms", "alternatives")

    def __init__(self, name, index, host_api, native_rate, max_channels,
                 latency_ms, alternatives=None):
        self.name = name
        self.index = index
        self.host_api = host_api
        self.native_rate = native_rate
        self.max_channels = max_channels
        self.latency_ms = latency_ms
        self.alternatives = alternatives or []

    def __repr__(self):
        return (f"AudioDevice({self.name!r}, index={self.index}, api="
                f"{self.host_api!r}, rate={self.native_rate})")


def grouping_key(name):
    """
    مفتاح تطبيع للتجميع.

    بيقصّ على 31 حرف زي MME بالظبط، ويشيل الفروق اللي مالهاش معنى، علشان
    "Microphone Array (Realtek Audio" و "Microphone Array (Realtek Audio)"
    يتحسبوا جهاز واحد - وهما فعلًا جهاز واحد.
    """
    trimmed = " ".join(str(name or "").split())[:_MME_NAME_LIMIT]
    normalized = re.sub(r"[^\w\s]", "", trimmed.lower())
    return " ".join(normalized.split())


def _api_rank(api_name):
    try:
        return HOST_API_PRIORITY.index(api_name)
    except ValueError:
        return len(HOST_API_PRIORITY)


def enumerate_raw_inputs():
    """كل مداخل الإدخال كما يعرضها النظام، بلا تجميع ولا تصفية."""
    if sd is None:
        return []

    try:
        apis = sd.query_hostapis()
        devices = sd.query_devices()
    except Exception:
        return []

    found = []
    for index, device in enumerate(devices):
        if device.get("max_input_channels", 0) <= 0:
            continue
        try:
            api_name = apis[device["hostapi"]]["name"]
        except (IndexError, KeyError, TypeError):
            api_name = ""
        if api_name in EXCLUDED_HOST_APIS:
            continue
        found.append({
            "index": index,
            "raw_name": device.get("name", f"Device {index}"),
            "name": clean_device_name(device.get("name", "")),
            "host_api": api_name,
            "native_rate": int(round(float(device.get("default_samplerate") or 0))),
            "max_channels": int(device.get("max_input_channels", 0)),
            "latency_ms": float(device.get("default_low_input_latency") or 0) * 1000,
        })

    return found


def group_devices(raw_inputs=None, include_virtual=False):
    """
    يجمّع المداخل حسب الجهاز الحقيقي، ويختار أفضل واجهة لكل واحد.

    بيرجّع قائمة AudioDevice مرتّبة بالاسم.
    """
    entries = enumerate_raw_inputs() if raw_inputs is None else list(raw_inputs)

    by_key = {}
    for entry in entries:
        name = entry["name"]
        if not name:
            continue
        if not include_virtual and is_virtual_device(name):
            continue
        by_key.setdefault(grouping_key(name), []).append(entry)

    devices = []
    for group in by_key.values():
        # الأفضل: أعلى أولوية للواجهة، ثم أقل زمن استجابة
        group.sort(key=lambda e: (_api_rank(e["host_api"]), e["latency_ms"]))
        best = group[0]
        # أطول اسم في المجموعة، لأن MME بتقصّ الأسماء
        display_name = max((e["name"] for e in group), key=len)
        devices.append(AudioDevice(
            name=display_name,
            index=best["index"],
            host_api=best["host_api"],
            native_rate=best["native_rate"],
            max_channels=best["max_channels"],
            latency_ms=best["latency_ms"],
            alternatives=[
                {"index": e["index"], "host_api": e["host_api"],
                 "native_rate": e["native_rate"], "max_channels": e["max_channels"]}
                for e in group[1:]
            ],
        ))

    devices.sort(key=lambda d: d.name.lower())
    return devices


def wasapi_shared_settings():
    """
    إعدادات تخلي WASAPI يقبل معدلات غير معدل الجهاز الأصلي.

    WASAPI في الوضع المشترك بيرفض أي معدل غير معدل الجهاز:
        Error opening InputStream: Invalid sample rate [PaErrorCode -9997]
    فمايك بـ192 كيلوهرتز كان بيجبر التسجيل على 192، يعني حجم وحمل معالج
    أربع أضعاف بلا فايدة مسموعة - الأذن بتسمع لحد 20 كيلوهرتز، و48
    بتغطي 24. auto_convert بيخلي ويندوز يعمل التحويل، فالمستخدم يرجع
    يقدر يختار.

    بيرجّع None لو الواجهة مش WASAPI (الواجهات التانية بتقبل أصلًا).
    """
    if sd is None:
        return None
    try:
        return sd.WasapiSettings(auto_convert=True)
    except Exception:
        return None


def supported_rates(device_index, channels=1, native_rate=None):
    """
    المعدلات اللي الجهاز بيقبلها فعلًا.

    معدل الجهاز الأصلي بيتجرّب الأول. الكود القديم كان بيجرّب قائمة
    ثابتة (44100، 48000، ...) بس، فمايكروفون بيقبل 192000 لوحده كان
    بيتشال من القائمة خالص - والمستخدم يفضل على مدخل MME بزمن استجابة
    90 مللي ثانية بدل 3.
    """
    if sd is None:
        return (native_rate,) if native_rate else FALLBACK_RATES

    candidates = []
    if native_rate:
        candidates.append(int(native_rate))
    candidates.extend(r for r in FALLBACK_RATES if r != native_rate)

    extra = wasapi_shared_settings()
    working = []
    for rate in candidates:
        for setting in (None, extra):
            try:
                sd.check_input_settings(device=device_index, samplerate=rate,
                                        channels=channels, extra_settings=setting)
                working.append(rate)
                break
            except Exception:
                continue
    return tuple(sorted(set(working), reverse=True))


# سقف المعدل المقترح: الأذن بتسمع لحد 20 كيلوهرتز، و48 بتغطي 24 - وأي
# معدل أعلى بيضاعف الحجم وحمل المعالج بلا فايدة مسموعة.
RECOMMENDED_MAX_RATE = 48000


def recommended_profile(device, available_rates=None):
    """
    أفضل إعدادات لجهاز بعينه.

    المبدأ: نسجّل بما يعطيه الجهاز من غير تحويل، ما دام معقولًا. أي
    إعادة تشكيل للإشارة (resampling) بتضيف خطوة معالجة، ونظافتها
    بتعتمد على سواقة الصوت - وده مصدر التشويه اللي اشتكى منه مستخدمون.

    لكن "بما يعطيه الجهاز" له سقف: فوق 48 كيلوهرتز الفايدة صفر
    والتكلفة حقيقية. شوف RECOMMENDED_MAX_RATE.
    """
    rates = available_rates
    if rates is None:
        rates = supported_rates(device.index, channels=1,
                                native_rate=device.native_rate)

    sensible = [r for r in rates if r <= RECOMMENDED_MAX_RATE]
    if device.native_rate and device.native_rate in sensible:
        rate = device.native_rate
    elif sensible:
        rate = max(sensible)
    elif rates:
        rate = min(rates)
    else:
        rate = device.native_rate or 44100

    # ستيريو لصوت النظام فقط؛ المايكروفون أحادي في الغالب الأعم
    channels = 2 if device.max_channels >= 2 and looks_like_system_audio(device.name) else 1
    channels = min(channels, max(1, device.max_channels))

    # 16 بت تكفي للكلام والموسيقى المسجّلة من الجهاز
    bit_depth = 16

    return {
        "sample_rate": int(rate),
        "channels": int(channels),
        "bit_depth": bit_depth,
    }


# كلمات تدل على مدخل بيلتقط صوت النظام لا مايكروفون، بلغات ويندوز
# المختلفة.
_STEREO_HINTS = (
    "stereo mix", "stereo", "what u hear", "wave out", "line", "mix",
    "loopback", "what you hear",
    "مزيج ستيريو", "ستيريو", "مزيج", "صوت النظام",
    "stereomix", "mixage stéréo", "mezcla estéreo", "mistura estéreo",
    "stereo-mix",
)


def looks_like_system_audio(name):
    lowered = (name or "").lower()
    return any(hint in lowered for hint in _STEREO_HINTS)
