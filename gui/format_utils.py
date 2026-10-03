# -*- coding: utf-8 -*-
"""
دوال تنسيق بسيطة مفصولة عن main_window.py عمدًا، عشان تفضل قابلة
للاختبار من غير الحاجة لتثبيت wxPython (اللي محتاج بيئة رسومية غالبًا).
"""


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
