# -*- coding: utf-8 -*-
"""
قراءة وكتابة ملفات قوائم التشغيل (M3U / M3U8 / PLS).

الحفظ دايمًا M3U8 (UTF-8): بيقراه تقريبًا أي مشغّل (VLC و foobar
و Winamp و Windows Media Player)، وبيحفظ الأسماء العربية صح - M3U
العادي ملهوش ترميز محدد وكل برنامج بيخمّنه بطريقته.

المسارات بتتكتب نسبية لمجلد القائمة لو الملف جواه، عشان المستخدم
يقدر ينقل المجلد كله (أو يحطه على فلاشة) والقائمة تفضل شغالة.
"""

import os

from core.streams import is_stream_url

PLAYLIST_EXTENSIONS = (".m3u", ".m3u8", ".pls")


class PlaylistFileError(Exception):
    """فشل قراءة أو كتابة ملف القائمة."""


def is_playlist_file(path) -> bool:
    return isinstance(path, str) and os.path.splitext(path)[1].lower() in PLAYLIST_EXTENSIONS


def _read_text(path):
    # M3U القديم مالوش ترميز ثابت: UTF-8 الأول (يشمل BOM)، وبعده
    # ترميز ويندوز العربي لأنه الأشيع في القوائم المحفوظة من برامج قديمة
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise PlaylistFileError(str(exc)) from exc
    for encoding in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _resolve(entry, base_dir):
    entry = entry.strip()
    if not entry:
        return None
    if is_stream_url(entry):
        return entry
    if entry.lower().startswith("file:///"):
        from urllib.parse import unquote
        entry = unquote(entry[len("file:///"):])
    entry = entry.replace("/", os.sep) if os.sep == "\\" else entry
    if not os.path.isabs(entry):
        entry = os.path.join(base_dir, entry)
    return os.path.normpath(entry)


def read_playlist(path):
    """
    يرجّع [(المسار أو الرابط، العنوان أو None)] بترتيب القائمة.

    الملفات الناقصة على القرص بترجع زي ما هي - المستدعي هو اللي يقرر
    يشيلها ويقول للمستخدم كام واحد اتشال.
    """
    text = _read_text(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    if os.path.splitext(path)[1].lower() == ".pls":
        return _parse_pls(text, base_dir)
    return _parse_m3u(text, base_dir)


def _parse_m3u(text, base_dir):
    entries = []
    pending_title = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.upper().startswith("#EXTINF:"):
                # #EXTINF:مدة,العنوان - العنوان ممكن يكون فيه فواصل
                _, sep, title = line.partition(",")
                pending_title = title.strip() if sep and title.strip() else None
            continue
        resolved = _resolve(line, base_dir)
        if resolved:
            entries.append((resolved, pending_title))
        pending_title = None
    return entries


def _parse_pls(text, base_dir):
    files, titles = {}, {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if not sep:
            continue
        key = key.strip().lower()
        for prefix, target in (("file", files), ("title", titles)):
            if key.startswith(prefix) and key[len(prefix):].isdigit():
                target[int(key[len(prefix):])] = value.strip()
    entries = []
    for number in sorted(files):
        resolved = _resolve(files[number], base_dir)
        if resolved:
            entries.append((resolved, titles.get(number) or None))
    return entries


def _entry_for_writing(entry, base_dir):
    if is_stream_url(entry):
        return entry
    absolute = os.path.abspath(entry)
    try:
        relative = os.path.relpath(absolute, base_dir)
    except ValueError:
        # قرص تاني على ويندوز: مفيش مسار نسبي أصلًا
        return absolute
    if relative.startswith(".."):
        return absolute
    return relative


def write_m3u8(path, entries, titles=None):
    """
    يحفظ القائمة. titles قاموس اختياري {المسار: العنوان} للروابط
    أساسًا - اسم المحطة أوضح بكتير من الرابط في أي مشغّل.

    الكتابة لملف مؤقت ثم استبدال: لو حصل خطأ في النص ما تضيعش القائمة
    القديمة اللي المستخدم بيحفظ فوقها.
    """
    titles = titles or {}
    base_dir = os.path.dirname(os.path.abspath(path))
    lines = ["#EXTM3U"]
    for entry in entries:
        title = titles.get(entry)
        if title:
            lines.append(f"#EXTINF:-1,{title}")
        lines.append(_entry_for_writing(entry, base_dir))
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("\n".join(lines) + "\n")
        os.replace(temp_path, path)
    except OSError as exc:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise PlaylistFileError(str(exc)) from exc
