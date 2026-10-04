# -*- coding: utf-8 -*-
"""
روابط البث عبر الإنترنت (راديو، بث مباشر، ملفات على سيرفر).

التشغيل نفسه بيعمله libvlc. هنا بس التعرّف على الرابط وتنظيفه واسمه
المعروض - بلا أي استيراد، عشان القائمة والواجهة يستخدموه بحرية.
"""

from urllib.parse import unquote, urlsplit

# البروتوكولات اللي libvlc بيشغّلها كبث. ftp مستبعدة: بتحتاج أسماء
# مستخدمين غالبًا، ومش من استخدامات الراديو والبث.
STREAM_SCHEMES = ("http", "https", "rtsp", "rtmp", "rtmps", "mms", "mmsh", "mmst", "udp", "rtp", "srt")


def is_stream_url(text) -> bool:
    """هل النص رابط بث (مش مسار ملف على الجهاز)؟"""
    if not isinstance(text, str):
        return False
    scheme, sep, rest = text.strip().partition("://")
    return bool(sep) and bool(rest) and scheme.lower() in STREAM_SCHEMES


def normalize_stream_url(text):
    """
    يرجّع الرابط جاهز للتشغيل، أو None لو مش رابط.

    المستخدم بينسخ الرابط من صفحة أو رسالة، فبييجي فيه مسافات أو علامات
    تنصيص أو من غير http:// أصلًا (www.example.com/live). مسار ويندوز
    زي C:\\music مش رابط حتى لو فيه نقطة.
    """
    if not isinstance(text, str):
        return None
    url = text.strip().strip('"').strip("'").strip("<>").strip()
    if not url or any(ch.isspace() for ch in url):
        return None
    if is_stream_url(url):
        return url
    if "://" in url:
        # بروتوكول مش مدعوم (file:// أو ftp:// أو javascript:...)
        return None
    # من غير بروتوكول: لازم يبان كاسم موقع، مش مسار ملف
    if "\\" in url or (len(url) > 1 and url[1] == ":"):
        return None
    host = url.split("/", 1)[0].split(":", 1)[0]
    labels = host.split(".")
    if len(labels) < 2 or not all(labels):
        return None
    # "song.mp3" اسم ملف مش موقع: آخر جزء لازم يبقى حروف ومش امتداد وسائط
    from core.playlist import SUPPORTED_EXTENSIONS
    tld = labels[-1].lower()
    if not tld.isalpha() or "." + tld in SUPPORTED_EXTENSIONS:
        return None
    return "http://" + url


def stream_display_name(url: str) -> str:
    """
    اسم قصير للإعلان والعنوان: آخر جزء من المسار، وإلا اسم الموقع.

    الرابط كامل طويل ومزعج في قارئ الشاشة، وغالبًا آخره اسم القناة أو
    الملف (radio.example.com/stream/quran.mp3 -> quran.mp3).
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    tail = unquote(parts.path.rstrip("/").rsplit("/", 1)[-1]) if parts.path else ""
    host = parts.hostname or ""
    if tail and tail.lower() not in ("stream", "live", "listen", ";", "index.m3u8", "playlist.m3u8"):
        return f"{tail} ({host})" if host else tail
    return host or url
