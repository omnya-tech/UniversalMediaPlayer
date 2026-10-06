# -*- coding: utf-8 -*-
"""
عناصر نافذة مسجّل الصوت: مؤشر المستوى المرئي، وعرض مدة التسجيل،
واسم ملف التسجيل الافتراضي.

نُقلت كما هي من gui/audio_recorder_dialog.py.
"""

import datetime
import os

import wx

from core.logging_setup import configure_logging

_logger = configure_logging()


def _format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _default_recording_path(folder: str, extension: str, prefix: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder, f"{prefix}{timestamp}{extension}")


class _LevelMeter(wx.Panel):
    _CLIP_THRESHOLD = 0.98

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._rms_level = 0.0
        self._peak_level = 0.0
        self.SetMinSize((-1, 32))
        self.SetBackgroundColour(wx.Colour(18, 18, 18))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)

    def AcceptsFocus(self):
        return False

    def set_level(self, rms_level: float, peak_level: float = None):
        self._rms_level = max(0.0, min(1.0, rms_level))
        self._peak_level = max(0.0, min(1.0, peak_level if peak_level is not None else rms_level))
        self.Refresh()

    def _on_paint(self, event):
        try:
            self._paint_content()
        except Exception:
            _logger.exception("خطأ أثناء رسم مؤشر الصوت")

    def _paint_content(self):
        width, height = self.GetClientSize()
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.Colour(18, 18, 18)))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return

        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(wx.Colour(35, 35, 35)))
        gc.DrawRoundedRectangle(0, 0, width, height, 6)

        rms_width = width * self._rms_level
        if rms_width > 0:
            is_clipping = self._peak_level >= self._CLIP_THRESHOLD
            color = wx.Colour(235, 60, 60) if is_clipping else wx.Colour(0, 180, 120)
            gc.SetBrush(wx.Brush(color))
            gc.DrawRoundedRectangle(0, 0, rms_width, height, 6)

        if self._peak_level > 0:
            peak_x = min(width - 3, width * self._peak_level)
            gc.SetBrush(wx.Brush(wx.Colour(255, 255, 255)))
            gc.DrawRectangle(peak_x, 0, 3, height)
