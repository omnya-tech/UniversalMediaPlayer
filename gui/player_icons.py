# -*- coding: utf-8 -*-
"""
أيقونات أزرار التحكّم، مرسومة في وقت التشغيل.

ليه مرسومة لا صور جاهزة:

  • بتتحجّم مع إعدادات العرض. المستخدم اللي مكبّر النظام 150% بياخد
    أيقونة حادّة، لا صورة متمططة.
  • بتاخد لون النص من النظام، فتشتغل مع الوضع الفاتح والداكن ومع
    أوضاع التباين العالي - وهي أوضاع بيستعملها ضعاف البصر فعلًا.
  • مفيش ملفات تتنسى في البناء أو تضيع من المثبّت.

والشكل هو المتعارف عليه عالميًا: مثلث للتشغيل، وعمودان للإيقاف
المؤقت، ومربع للإيقاف، ومثلثان للتقديم والإرجاع. الاتجاه بيتبع
اتجاه الزمن لا اتجاه القراءة - التقديم لليمين حتى في الواجهة
العربية، زي كل مشغّلات الوسائط.
"""

import wx


def _canvas(size, scale):
    """سطح رسم شفاف بحجم مضروب في معامل العرض."""
    side = int(size * scale)
    bitmap = wx.Bitmap(side, side, 32)
    bitmap.UseAlpha()
    return bitmap, side


def _context(bitmap, colour):
    memory = wx.MemoryDC(bitmap)
    memory.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
    memory.Clear()
    gc = wx.GraphicsContext.Create(memory)
    gc.SetBrush(wx.Brush(colour))
    gc.SetPen(wx.Pen(colour, 1))
    return memory, gc


def _triangle(gc, x, y, width, height, pointing_right=True):
    path = gc.CreatePath()
    if pointing_right:
        path.MoveToPoint(x, y)
        path.AddLineToPoint(x + width, y + height / 2)
        path.AddLineToPoint(x, y + height)
    else:
        path.MoveToPoint(x + width, y)
        path.AddLineToPoint(x, y + height / 2)
        path.AddLineToPoint(x + width, y + height)
    path.CloseSubpath()
    gc.FillPath(path)


def _finish(memory, bitmap):
    memory.SelectObject(wx.NullBitmap)
    return bitmap


def play_icon(size=18, scale=1.0, colour=None):
    colour = colour or wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
    bitmap, side = _canvas(size, scale)
    memory, gc = _context(bitmap, colour)
    _triangle(gc, side * 0.24, side * 0.14, side * 0.56, side * 0.72, True)
    return _finish(memory, bitmap)


def pause_icon(size=18, scale=1.0, colour=None):
    colour = colour or wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
    bitmap, side = _canvas(size, scale)
    memory, gc = _context(bitmap, colour)
    bar = side * 0.2
    gc.DrawRectangle(side * 0.22, side * 0.14, bar, side * 0.72)
    gc.DrawRectangle(side * 0.58, side * 0.14, bar, side * 0.72)
    return _finish(memory, bitmap)


def stop_icon(size=18, scale=1.0, colour=None):
    colour = colour or wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
    bitmap, side = _canvas(size, scale)
    memory, gc = _context(bitmap, colour)
    gc.DrawRectangle(side * 0.22, side * 0.22, side * 0.56, side * 0.56)
    return _finish(memory, bitmap)


def _double_triangle(size, scale, colour, pointing_right, with_bar=False):
    colour = colour or wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
    bitmap, side = _canvas(size, scale)
    memory, gc = _context(bitmap, colour)

    top = side * 0.18
    height = side * 0.64
    width = side * 0.3
    gap = side * 0.04
    bar_width = side * 0.1

    if with_bar:
        # السابق والتالي: مثلثان وعمود عند طرف الاتجاه، فالمجموعة
        # تُزاح لتبقى في الوسط.
        if pointing_right:
            left = side * 0.1
            gc.DrawRectangle(side * 0.8, top, bar_width, height)
        else:
            left = side * 0.2
            gc.DrawRectangle(side * 0.1, top, bar_width, height)
    else:
        left = side * 0.16

    _triangle(gc, left, top, width, height, pointing_right)
    _triangle(gc, left + width + gap, top, width, height, pointing_right)
    return _finish(memory, bitmap)


def rewind_icon(size=18, scale=1.0, colour=None):
    return _double_triangle(size, scale, colour, pointing_right=False)


def forward_icon(size=18, scale=1.0, colour=None):
    return _double_triangle(size, scale, colour, pointing_right=True)


def previous_icon(size=18, scale=1.0, colour=None):
    return _double_triangle(size, scale, colour, pointing_right=False, with_bar=True)


def next_icon(size=18, scale=1.0, colour=None):
    return _double_triangle(size, scale, colour, pointing_right=True, with_bar=True)
