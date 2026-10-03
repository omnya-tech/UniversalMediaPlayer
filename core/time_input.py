# -*- coding: utf-8 -*-
"""
تحليل الوقت اللي المستخدم بيكتبه للقفز إليه.

الهدف إن المستخدم يكتب زي ما يتكلم، مش زي ما الآلة عايزة: كلهم صحيحين
ويعنوا نفس الشيء تقريبًا:

    90        تسعين ثانية
    1:30      دقيقة ونص
    01:30     نفس الشيء
    1:02:03   ساعة ودقيقتين وتلات ثوانٍ
    2:00:00   ساعتين

الوحدة مفصولة عن الواجهة عن قصد: تحليل مدخلات المستخدم أكتر مكان بتظهر
فيه حالات حافة، ولازم يتختبر بلا فتح نوافذ.
"""


class TimeParseError(ValueError):
    """المكتوب مش وقت صالح."""


def parse_time(text: str) -> float:
    """
    يحوّل نصًا لعدد ثوانٍ.

    بيرفع TimeParseError لو المكتوب مش مفهوم، بدل ما يخمّن رقمًا غلط
    وينقّز المستخدم لمكان ما طلبهوش.
    """
    if text is None:
        raise TimeParseError("مفيش مدخل")
    # النقطتان العريضة والفاصلة العشرية العربية تُعامَلان كنقطتين
    cleaned = text.strip().replace("：", ":").replace("٫", ":")
    # الأرقام العربية الهندية إلى أرقام لاتينية
    cleaned = cleaned.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

    if not cleaned:
        raise TimeParseError("مفيش مدخل")

    parts = cleaned.split(":")
    if len(parts) > 3:
        raise TimeParseError("أجزاء كتير")

    values = []
    for part in parts:
        part = part.strip()
        if not part:
            part = "0"
        if not part.isdigit():
            raise TimeParseError(f"جزء غير رقمي: {part!r}")
        values.append(int(part))

    if len(values) == 1:
        seconds = values[0]
    elif len(values) == 2:
        minutes, secs = values
        if secs >= 60:
            raise TimeParseError("الثواني لازم تقل عن 60")
        seconds = minutes * 60 + secs
    else:
        hours, minutes, secs = values
        if minutes >= 60 or secs >= 60:
            raise TimeParseError("الدقائق والثواني لازم تقل عن 60")
        seconds = hours * 3600 + minutes * 60 + secs

    return float(seconds)


def format_time_for_input(seconds: float) -> str:
    """يعرض الموضع الحالي بنفس الشكل اللي المستخدم بيكتبه."""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
