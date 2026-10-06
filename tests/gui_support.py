# -*- coding: utf-8 -*-
"""
أدوات اختبارات الواجهة: محرك وهمي، ومعلن يسجّل ما يُقال، وأحداث مفاتيح.

الواجهة تُختبر بنوافذها الحقيقية (wx) لكن بلا VLC ولا قارئ شاشة: المحرك
الوهمي يتصرف كالحقيقي في الموضع والمدة والسرعة والصوت، والمعلن يحفظ
النصوص بدل أن يرسلها إلى NVDA. والاختصارات العامة لا تُسجَّل في ويندوز.
"""

import time

import wx

from core.engine import PlaybackState


class FakeEngine:
    """بديل PlayerEngine بالواجهة نفسها التي تستعملها النوافذ."""

    def __init__(self, on_state_change=None, on_error=None, tr=None, on_stream_title=None):
        self.on_state_change = on_state_change
        self.position = 0.0
        self.duration = 0.0
        self._speed = 1.0
        self.volume = 1.0
        self._muted = False
        self.state = PlaybackState.STOPPED
        self.is_stream = False
        self.has_video = False
        self.is_ready = True
        self.opened = []
        self.seeks = []
        self.equalizer = None

    # المحرك الحقيقي يجهّز VLC في الخلفية
    def warm_up(self):
        pass

    def open(self, path):
        self.opened.append(path)
        self.state = PlaybackState.PLAYING
        return True

    def play(self):
        self.state = PlaybackState.PLAYING

    def pause(self):
        self.state = PlaybackState.PAUSED

    def toggle_play_pause(self):
        self.state = (PlaybackState.PAUSED if self.state == PlaybackState.PLAYING
                      else PlaybackState.PLAYING)

    def stop(self):
        self.state = PlaybackState.STOPPED
        self.position = 0.0

    def seek(self, seconds):
        self.position = float(seconds)
        self.seeks.append(self.position)

    def play_and_seek(self, seconds):
        self.state = PlaybackState.PLAYING
        self.seek(seconds)

    def get_current_position(self):
        return self.position

    def get_effective_position(self):
        return self.position

    @property
    def speed(self):
        return self._speed

    def set_speed(self, factor):
        # الحدود نفسها في PlayerEngine.set_speed
        self._speed = max(0.5, min(2.0, float(factor)))

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))

    def set_muted(self, muted):
        self._muted = bool(muted)

    @property
    def is_muted(self):
        return self._muted

    def set_equalizer(self, preamp=None, bands=None):
        self.equalizer = None if preamp is None and bands is None else (preamp, bands)

    @staticmethod
    def get_equalizer_preset_values(index):
        return (0.0, [0.0] * 10)

    def set_video_widget_handle(self, handle):
        pass

    def get_media_info(self):
        return {"duration": self.duration, "bit_rate": 0}

    def get_stream_title(self):
        return None

    def shutdown(self):
        pass


class FakeAnnouncer:
    """يحفظ ما يُعلَن بدل أن يرسله إلى قارئ الشاشة."""

    def __init__(self, *args, **kwargs):
        self.said = []

    def announce(self, text, *args, **kwargs):
        self.said.append(text)

    def last(self):
        return self.said[-1] if self.said else None


def key_event(keycode, ctrl=False, shift=False, alt=False):
    """حدث مفتاح كما يصل لـ EVT_CHAR_HOOK، بمفاتيحه المساعدة."""
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetKeyCode(keycode)
    event.SetControlDown(ctrl)
    event.SetShiftDown(shift)
    event.SetAltDown(alt)
    return event


def pump(seconds=0.3):
    """
    يشغّل أحداث wx (المؤقتات وCallAfter) لمدة قصيرة.

    المؤقتات لا تنطلق بلا حلقة أحداث نشطة، والاختبارات تعمل خارج
    MainLoop؛ فحلقة مؤقتة تُفعَّل طوال الانتظار.
    """
    loop = wx.GUIEventLoop()
    previous = wx.EventLoopBase.GetActive()
    wx.EventLoopBase.SetActive(loop)
    try:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            wx.GetApp().Yield(True)
            time.sleep(0.01)
    finally:
        wx.EventLoopBase.SetActive(previous)
