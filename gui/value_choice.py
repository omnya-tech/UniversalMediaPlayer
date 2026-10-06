# -*- coding: utf-8 -*-
"""
قائمة اختيار لقيم رقمية بدل خانة الأرقام (SpinCtrl).

خانة الأرقام تُكتب فيها القيمة أو تُغيَّر بالأسهم رقمًا رقمًا، وقارئ الشاشة
يقرأ كل خطوة. القائمة تعرض قيمًا جاهزة معقولة تُختار بالأسهم أو بالماوس.

GetValue وSetValue بنفس معنى SpinCtrl، فكل كود يقرأ الخانة أو يضبطها يعمل
كما هو. وقيمة محفوظة من قبل ليست في القائمة تُضاف إليها في مكانها ولا
تضيع.
"""

import wx


class ValueChoice(wx.Choice):
    def __init__(self, parent, values, initial=None, formatter=str):
        self._formatter = formatter
        self._values = sorted(set(values))
        super().__init__(parent, choices=[formatter(v) for v in self._values])
        self.SetValue(initial if initial is not None else self._values[0])

    def GetValue(self):
        index = self.GetSelection()
        return self._values[index if index != wx.NOT_FOUND else 0]

    def SetValue(self, value):
        if value not in self._values:
            self._values.append(value)
            self._values.sort()
            self.Insert(self._formatter(value), self._values.index(value))
        self.SetSelection(self._values.index(value))


# القيم الجاهزة لكل خانة
RECENT_FILES_COUNTS = (3, 5, 10, 15, 20, 25, 30, 40, 50)
AUDIO_BITRATES_KBPS = (32, 48, 64, 96, 128, 160, 192, 224, 256, 320, 384, 448, 512)
VIDEO_BITRATES_KBPS = (500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000,
                       10000, 12000, 15000, 20000)
CRF_VALUES = tuple(range(0, 52))
VIDEO_WIDTHS = (320, 426, 480, 640, 720, 854, 960, 1024, 1280, 1366, 1440, 1600, 1920,
                2048, 2560, 3840, 4096, 7680)
VIDEO_HEIGHTS = (180, 240, 270, 360, 480, 540, 576, 600, 720, 768, 900, 1080, 1200, 1440,
                 1600, 2160, 4320)
FRAME_RATES = (10, 12, 15, 20, 23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60, 90, 100, 120,
               144, 240)


def format_number(value):
    """23.976 تبقى كما هي، و30.0 تُعرض 30."""
    return f"{value:g}"
