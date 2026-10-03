# -*- coding: utf-8 -*-
"""
بناء تقرير تشخيصي نصي.

ليه موجود: شكاوى المستخدمين بتوصل في مجموعات عامة بلا أي وسيلة نتواصل
بيها مع صاحب الشكوى، فالتشخيص كان بيتوقف عند "الصوت مش نقي". التقرير ده
بيخلي المستخدم يبعت كل اللي محتاجينه بضغطة واحدة.

قاعدة صارمة: **بلا أي معرّف شخصي**. الملف ده الغالب إنه هينتشر في مجموعة
عامة، فما يحملش اسم جهاز ولا اسم مستخدم ولا مسار ملف ولا اسم ملف صوتي.
المسارات بتترجع كأشكال مجردة (موجود/مش موجود) بدل قيمها.
"""

import os
import platform
import re
import sys


def _safe(callable_or_value, default="غير متاح"):
    try:
        return callable_or_value() if callable(callable_or_value) else callable_or_value
    except Exception:
        return default


def _system_section():
    lines = ["[النظام]"]
    lines.append(f"  ويندوز        : {_safe(platform.platform)}")
    lines.append(f"  المعمارية     : {_safe(platform.machine)}")
    lines.append(f"  بايثون        : {sys.version.split()[0]}")
    lines.append(f"  عدد الأنوية   : {_safe(os.cpu_count)}")
    lines.append(f"  مجمّد (exe)?  : {getattr(sys, 'frozen', False)}")
    return lines


def _audio_section():
    lines = ["", "[أجهزة الإدخال الصوتي]"]
    try:
        import sounddevice as sd

        hostapis = sd.query_hostapis()
        found = False
        for index, device in enumerate(sd.query_devices()):
            if device.get("max_input_channels", 0) <= 0:
                continue
            found = True
            api_index = device.get("hostapi")
            api = ""
            if api_index is not None and 0 <= api_index < len(hostapis):
                api = hostapis[api_index].get("name", "")
            rate = int(round(float(device.get("default_samplerate", 0))))
            lines.append(
                f"  [{index}] {device.get('name', '?')} | {api} | "
                f"{rate}Hz | {device.get('max_input_channels')}ch"
            )
        if not found:
            lines.append("  لا توجد أجهزة إدخال")
    except Exception as exc:
        lines.append(f"  تعذّرت القراءة: {type(exc).__name__}")
    return lines


def _playback_section():
    lines = ["", "[محرك التشغيل]"]
    try:
        from core.engine import _load_vlc

        available = _load_vlc()
        lines.append(f"  libvlc متاحة  : {available}")
        if available:
            import vlc

            lines.append(f"  إصدار VLC     : {_safe(vlc.libvlc_get_version)}")
    except Exception as exc:
        lines.append(f"  تعذّر الفحص: {type(exc).__name__}")
    return lines


def _codec_section():
    lines = ["", "[محرك التحويل]"]
    try:
        import av

        lines.append(f"  PyAV          : {av.__version__}")
        lines.append(f"  FFmpeg        : {av.ffmpeg_version_info}")
    except Exception as exc:
        lines.append(f"  غير متاح: {type(exc).__name__}")
    return lines


def _settings_section(settings):
    lines = ["", "[الإعدادات المؤثرة]"]
    if settings is None:
        lines.append("  غير متاحة")
        return lines
    interesting = (
        "language", "auto_resume", "enable_folder_navigation",
        "enable_global_media_keys", "on_playback_ended_action",
        "announce_accessibility",
        "recorder_default_sample_rate", "recorder_default_channels",
        "recorder_default_bit_depth", "recorder_default_format",
        "converter_default_format",
    )
    for key in interesting:
        lines.append(f"  {key:<30}: {settings._data.get(key, '-')}")
    return lines


def _log_tail_section(log_path, max_lines=120):
    """
    آخر أسطر السجل - وفيها سطور REC_SUMMARY اللي بتحسم شكاوى التسجيل.

    بناخد الذيل لا الملف كله: الملف بيوصل 2 ميجا، والمهم دايمًا الأخير.
    """
    lines = ["", f"[آخر {max_lines} سطر من السجل]"]
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
            tail = handle.readlines()[-max_lines:]
        if not tail:
            lines.append("  السجل فاضي")
        else:
            lines.extend("  " + line.rstrip() for line in tail)
    except FileNotFoundError:
        lines.append("  مفيش ملف سجل")
    except Exception as exc:
        lines.append(f"  تعذّرت القراءة: {type(exc).__name__}")
    return lines


# أي مسار تحت مجلد مستخدم في ويندوز، بأي شكل للفواصل:
# C:\Users\Name أو c:/users/name - يُستبدل كله بـ <HOME>
_USER_PATH_PATTERN = re.compile(
    r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+",
    re.IGNORECASE,
)


def redact_personal_information(text: str) -> str:
    """
    يشيل المسارات وأسماء المستخدمين من النص.

    ضروري لأن آثار الاستثناءات في السجل بتحمل مسارات ملفات كاملة تحت
    مجلد المستخدم - والتقرير ده الغالب هينتشر في مجموعة عامة.

    بننقّي بدل ما نمنع الحفظ: السجل هو أهم جزء في التقرير، ومنعه عشان
    مسار جوّه معناه إننا نضيّع الفايدة كلها.
    """
    home = os.path.expanduser("~")
    username = os.path.basename(home)

    cleaned = text.replace(home, "<HOME>")
    cleaned = cleaned.replace(home.replace(os.sep, "/"), "<HOME>")
    # مسارات مستخدمين آخرين أو بحروف مختلفة الحالة
    # (السجل قد يكون منسوخًا من جهاز آخر)
    cleaned = _USER_PATH_PATTERN.sub("<HOME>", cleaned)
    # الاسم القصير جدًا يطابق كلمات عادية فيفسد النص
    if username and len(username) > 2:
        cleaned = re.sub(re.escape(username), "<USER>", cleaned, flags=re.IGNORECASE)

    return cleaned


def build_report(app_version, settings=None, log_path=None) -> str:
    """يبني التقرير كنص جاهز للحفظ، منقّى من أي معرّف شخصي."""
    lines = [
        "==============================================================",
        f"تقرير تشخيصي - Universal Media Player {app_version}",
        "==============================================================",
        "",
        "هذا الملف لا يحتوي على أي معلومات شخصية:",
        "لا اسم جهاز، ولا اسم مستخدم، ولا مسارات، ولا أسماء ملفاتك.",
        "",
    ]
    lines += _system_section()
    lines += _audio_section()
    lines += _playback_section()
    lines += _codec_section()
    lines += _settings_section(settings)
    if log_path:
        lines += _log_tail_section(log_path)
    lines.append("")
    return redact_personal_information("\n".join(lines))


def contains_personal_information(report: str) -> bool:
    """
    فحص أخير قبل الحفظ: هل التقرير سرّب حاجة تعرّف صاحبه؟

    موجود كشبكة أمان لا كتحقّق شكلي - أي قسم جديد يتضاف مستقبلًا ممكن
    يجيب مسارًا معاه بلا ما حد ياخد باله.
    """
    home = os.path.expanduser("~")
    username = os.path.basename(home)
    suspects = [home, "C:\\Users\\", "AppData"]
    if username and len(username) > 2:
        suspects.append(username)
    lowered = report.lower()
    return any(suspect.lower() in lowered for suspect in suspects if suspect)
