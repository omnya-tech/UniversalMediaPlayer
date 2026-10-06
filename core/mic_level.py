# -*- coding: utf-8 -*-
"""
مستوى المايكروفون في ويندوز (نفس شريط «مستوى الصوت» في إعدادات الصوت).

ليه من ويندوز لا من البرنامج: التشبّع بيحصل داخل المايك نفسه قبل ما الصوت
يوصل للبرنامج، وأي تخفيض بعدها بيخفّض صوتًا مقصوصًا أصلًا. مايك USB على
جهاز التطوير كان مستواه في ويندوز 100% يعني +32 ديسيبل، فكل كلمة عالية
تتقص. ومستوى ويندوز بيتطبّق في الجهاز نفسه لو بيدعمه (أغلب مايكات USB
وكروت الصوت)، فبيشتغل كمان في الوضع الحصري.

بـctypes مباشرة على واجهات Core Audio (COM)، بلا comtypes ولا pycaw:
مكتبات إضافية في المثبّت لأربع دوال.

الجهاز بيتعرف بالاسم: sounddevice ما بيدّيش معرّف ويندوز للجهاز، واسم
WASAPI هو نفسه الاسم الودّي للجهاز في ويندوز. (MME بتقصّه، فالمقارنة
بـgrouping_key زي قائمة الأجهزة)
"""

import ctypes
import sys
from ctypes import POINTER, byref, c_float, c_uint, c_void_p, wintypes

from core.audio_devices import grouping_key

_HRESULT = ctypes.HRESULT if sys.platform == "win32" else ctypes.c_long


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), byref(self))


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(ctypes.Structure):
    # النوع ثم ثلاث خانات محجوزة ثم القيمة؛ نقرأ منها مؤشر النص وحده
    _fields_ = [("vt", wintypes.USHORT), ("r1", wintypes.WORD), ("r2", wintypes.WORD),
                ("r3", wintypes.WORD), ("pwszVal", ctypes.c_wchar_p), ("pad", c_void_p)]


_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
_IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
_PKEY_FRIENDLY_NAME = ("{A45C254E-DF1C-4EFD-8020-67D146A850E0}", 14)
_CLSCTX_ALL = 0x17
_E_CAPTURE = 1
_DEVICE_STATE_ACTIVE = 1
_STGM_READ = 0
_VT_LPWSTR = 31
_HW_SUPPORT_VOLUME = 0x1

# مواضع الدوال في جداول الواجهات (بعد QueryInterface وAddRef وRelease)
_RELEASE = 2
_ENUM_AUDIO_ENDPOINTS = 3
_COLLECTION_GET_COUNT, _COLLECTION_ITEM = 3, 4
_DEVICE_ACTIVATE, _DEVICE_OPEN_PROPERTY_STORE = 3, 4
_PROPERTY_STORE_GET_VALUE = 5
_SET_LEVEL_SCALAR, _GET_LEVEL_SCALAR = 7, 9
_QUERY_HARDWARE_SUPPORT = 19


def _call(obj, index, *args):
    """
    ينادي الدالة رقم index في جدول كائن COM، ويرفع OSError لو فشلت.

    المؤشرات (byref وNone) بتعدّي كـc_void_p، والقيم بنوعها هي.
    """
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    argtypes = [type(arg) if isinstance(arg, (ctypes.c_int, c_uint, c_float, wintypes.DWORD))
                else c_void_p for arg in args]
    prototype = ctypes.WINFUNCTYPE(_HRESULT, c_void_p, *argtypes)
    return prototype(vtable[index])(obj, *args)


def _release(obj):
    if obj:
        prototype = ctypes.WINFUNCTYPE(c_uint, c_void_p)
        vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
        prototype(vtable[_RELEASE])(obj)


def _friendly_name(device):
    store = c_void_p()
    _call(device, _DEVICE_OPEN_PROPERTY_STORE, wintypes.DWORD(_STGM_READ), byref(store))
    try:
        key = _PROPERTYKEY(_GUID(_PKEY_FRIENDLY_NAME[0]), _PKEY_FRIENDLY_NAME[1])
        value = _PROPVARIANT()
        _call(store, _PROPERTY_STORE_GET_VALUE, byref(key), byref(value))
        try:
            return value.pwszVal if value.vt == _VT_LPWSTR else ""
        finally:
            ctypes.oledll.ole32.PropVariantClear(byref(value))
    finally:
        _release(store)


class MicLevel:
    """
    مستوى مايكروفون واحد في ويندوز، من 0 لـ100 زي إعدادات الصوت.

    open يرجّع None لو الجهاز مش لاقيه أو ويندوز ما بيسمحش بالتحكم فيه
    (الواجهة تخفي الشريط ساعتها). الكائن لازم يتقفل بـclose.
    """

    def __init__(self, volume, hardware):
        self._volume = volume
        # مستوى في الجهاز نفسه: بيمنع التشبّع وبيشتغل في الوضع الحصري.
        # من غيره ويندوز بيطبّقه برمجيًا في الوضع العادي بس
        self.hardware = hardware

    @classmethod
    def open(cls, device_name):
        if sys.platform != "win32" or not device_name:
            return None
        ole32 = ctypes.oledll.ole32
        # نافذة wx هيّأت COM أصلًا في الخيط ده؛ التهيئة التانية بترجع
        # S_FALSE أو RPC_E_CHANGED_MODE وكلاهما سليم
        ctypes.windll.ole32.CoInitializeEx(None, 0x2)
        wanted = grouping_key(device_name)
        enumerator = c_void_p()
        collection = c_void_p()
        try:
            ole32.CoCreateInstance(byref(_GUID(_CLSID_MMDeviceEnumerator)), None, _CLSCTX_ALL,
                                   byref(_GUID(_IID_IMMDeviceEnumerator)), byref(enumerator))
            _call(enumerator, _ENUM_AUDIO_ENDPOINTS, ctypes.c_int(_E_CAPTURE),
                  wintypes.DWORD(_DEVICE_STATE_ACTIVE), byref(collection))
            count = c_uint()
            _call(collection, _COLLECTION_GET_COUNT, byref(count))
            for position in range(count.value):
                device = c_void_p()
                _call(collection, _COLLECTION_ITEM, c_uint(position), byref(device))
                try:
                    if grouping_key(_friendly_name(device)) != wanted:
                        continue
                    volume = c_void_p()
                    _call(device, _DEVICE_ACTIVATE, byref(_GUID(_IID_IAudioEndpointVolume)),
                          wintypes.DWORD(_CLSCTX_ALL), None, byref(volume))
                    support = wintypes.DWORD()
                    try:
                        _call(volume, _QUERY_HARDWARE_SUPPORT, byref(support))
                    except OSError:
                        support.value = 0
                    return cls(volume, bool(support.value & _HW_SUPPORT_VOLUME))
                finally:
                    _release(device)
        except OSError:
            return None
        finally:
            _release(collection)
            _release(enumerator)
        return None

    def get(self):
        """المستوى الحالي (0-100)، أو None لو الجهاز اتفصل."""
        level = c_float()
        try:
            _call(self._volume, _GET_LEVEL_SCALAR, byref(level))
        except OSError:
            return None
        return int(round(level.value * 100))

    def set(self, percent):
        percent = max(0, min(100, int(percent)))
        try:
            _call(self._volume, _SET_LEVEL_SCALAR, c_float(percent / 100.0), None)
        except OSError:
            return False
        return True

    def close(self):
        _release(self._volume)
        self._volume = None
