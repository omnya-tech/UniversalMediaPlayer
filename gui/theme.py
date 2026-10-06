# -*- coding: utf-8 -*-
"""
مظهر البرنامج: يتبع ويندوز، أو فاتح، أو داكن.

يُحسم مرة واحدة عند البدء (apply_app_theme في main.py) ثم تسأله النوافذ:
الوضع الداكن الأصلي في ويندوز (MSWEnableDarkMode في wxPython 4.3) يقلب
القوائم والنوافذ والقوائم المنسدلة والأزرار كلها، لكنه لا يُفعَّل إلا قبل
إنشاء أول نافذة. فتغيير المظهر من الخيارات يُطبَّق بعد إعادة التشغيل.

والتباين العالي في ويندوز يتقدم على كل اختيار: البرنامج لا يضع أي لون من
عنده، فتبقى ألوان النظام التي اختارها ضعيف البصر.
"""

import ctypes
import sys

import wx

THEMES = ("system", "light", "dark")
DEFAULT_THEME = "system"

_state = {"dark": False, "high_contrast": False}


def _windows_high_contrast():
    if sys.platform != "win32":
        return False

    class HIGHCONTRAST(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                    ("lpszDefaultScheme", ctypes.c_wchar_p)]

    info = HIGHCONTRAST()
    info.cbSize = ctypes.sizeof(HIGHCONTRAST)
    try:
        # SPI_GETHIGHCONTRAST = 0x42، وHCF_HIGHCONTRASTON = 1
        if ctypes.windll.user32.SystemParametersInfoW(0x42, info.cbSize, ctypes.byref(info), 0):
            return bool(info.dwFlags & 1)
    except Exception:
        pass
    return False


def _windows_apps_dark():
    """وضع التطبيقات في إعدادات ويندوز (التخصيص ← الألوان)."""
    try:
        return bool(wx.SystemSettings.GetAppearance().IsDark())
    except Exception:
        return False


def apply_app_theme(app, theme):
    """يُستدعى بعد إنشاء التطبيق وقبل أي نافذة."""
    high_contrast = _windows_high_contrast()
    if theme == "dark":
        dark = True
    elif theme == "light":
        dark = False
    else:
        dark = _windows_apps_dark()
    dark = dark and not high_contrast
    if dark and hasattr(app, "MSWEnableDarkMode"):
        # «دائمًا»: الافتراضي (Auto) لا يقلب شيئًا ما دام ويندوز نفسه فاتحًا،
        # فيبقى اختيار «داكن» بلا أثر إلا في ألوان النافذة الرئيسية
        try:
            dark = bool(app.MSWEnableDarkMode(wx.App.DarkMode_Always))
        except Exception:
            dark = False
    _state.update(dark=dark, high_contrast=high_contrast)


def is_dark():
    return _state["dark"]


def custom_colours_allowed():
    """لا ألوان من البرنامج في التباين العالي."""
    return not _state["high_contrast"]


# ألوان النافذة الرئيسية. الشريط العلوي داكن في المظهرين (اسم الملف بالأبيض)
_PALETTES = {
    "light": {
        "main_bg": (240, 243, 246), "header_bg": (30, 35, 45), "controls_bg": (250, 252, 255),
        "header_text": (255, 255, 255), "header_secondary": (170, 185, 205),
        "time_text": (40, 50, 65), "time_playing": (0, 120, 215), "time_idle": (0, 0, 0),
        "time_remaining": (100, 110, 125), "volume_text": (0, 120, 0),
        "button_bg": (255, 255, 255), "button_fg": (30, 35, 45), "play_fg": (0, 84, 166),
        "seek_target": (230, 120, 0), "badge": (255, 190, 80),
    },
    "dark": {
        "main_bg": (20, 20, 20), "header_bg": (30, 35, 45), "controls_bg": (35, 40, 50),
        "header_text": (255, 255, 255), "header_secondary": (170, 185, 205),
        "time_text": (100, 180, 255), "time_playing": (100, 180, 255), "time_idle": (255, 255, 255),
        "time_remaining": (180, 190, 205), "volume_text": (120, 220, 120),
        "button_bg": (55, 60, 75), "button_fg": (255, 255, 255), "play_fg": (255, 255, 255),
        "seek_target": (255, 170, 60), "badge": (255, 190, 80),
    },
}


def colour(name):
    """لون من لوحة المظهر الحالي، أو wx.NullColour (لون النظام) في التباين العالي."""
    if not custom_colours_allowed():
        return wx.NullColour
    return wx.Colour(*_PALETTES["dark" if is_dark() else "light"][name])


def hint_colour():
    """نص ثانوي (التلميحات): رمادي النظام، يناسب الفاتح والداكن والتباين العالي."""
    return wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
