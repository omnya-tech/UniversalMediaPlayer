# -*- coding: utf-8 -*-
"""
شكل النافذة الرئيسية: الأيقونة والخلفية، وحجم النافذة وموضعها، والألوان،
وملء الشاشة، والتبديل بين عرض الفيديو والصوت.

نُقلت كما هي من gui/main_window.py لتصغيره.
"""

import os

import wx

from core.engine import PlaybackState
from core.logging_setup import get_app_data_dir
from accessibility.announcer import _resource_path
from gui import player_icons
from gui import theme


class WindowLayoutMixin:
    """مظهر النافذة الرئيسية وتخطيطها."""

    def _set_app_icon(self):
        icon_path = _resource_path("resources", "omnya_icon.ico")
        try:
            if os.path.isfile(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def _load_background_image(self):
        candidates = [
            _resource_path("resources", "background.png"), _resource_path("resources", "background.jpg"),
            _resource_path("background.png"), os.path.join(get_app_data_dir(), "background.png"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                try:
                    img = wx.Image(path, wx.BITMAP_TYPE_ANY)
                    if img.IsOk(): return img
                except Exception: pass
        return None

    def _restore_window_geometry(self):
        """
        يرجّع النافذة لحجمها وموضعها الأخيرين.

        بنتأكد إن الموضع لسه على شاشة موجودة: المستخدم ممكن يكون فصل شاشة
        تانية، والنافذة ساعتها كانت هتفتح برّه حدود المعروض ويبقى مستحيل
        يوصلها - وده أسوأ بكتير من إنها تفتح في النص.
        """
        geometry = self.settings.get_window_geometry()
        if not geometry:
            return False
        width, height, x, y = geometry
        if wx.Display.GetFromPoint(wx.Point(x + width // 2, y + 20)) == wx.NOT_FOUND:
            return False
        self.SetSize(width, height)
        self.SetPosition(wx.Point(x, y))
        return True

    def _save_window_geometry(self):
        # المصغّرة والمكبّرة وملء الشاشة مش حجم المستخدم الحقيقي
        if self.IsIconized() or self.IsMaximized() or self.IsFullScreen():
            return
        try:
            width, height = self.GetSize()
            x, y = self.GetPosition()
            self.settings.set_window_geometry(width, height, x, y)
        except Exception:
            pass

    def _apply_ui_theme(self):
        """
        ألوان النافذة من مظهر البرنامج (gui/theme.py).

        المظهر يُحسم عند البدء؛ وفي التباين العالي لا لون من البرنامج
        (theme.colour يرجع لون النظام).
        """
        c = theme.colour
        self.main_panel.SetBackgroundColour(c("main_bg"))
        self.header_panel.SetBackgroundColour(c("header_bg"))
        self.controls_panel.SetBackgroundColour(c("controls_bg"))

        self.file_label.SetForegroundColour(c("header_text"))
        self.media_info_label.SetForegroundColour(c("header_secondary"))
        self.sleep_timer_badge.SetForegroundColour(c("badge"))

        self.time_current_label.SetForegroundColour(c("time_text"))
        self.time_remaining_total_label.SetForegroundColour(c("time_remaining"))
        self.volume_label.SetForegroundColour(c("volume_text"))
        self.vol_pct_label.SetForegroundColour(c("volume_text"))

        for btn in [self.previous_button, self.seek_backward_button, self.stop_button, self.seek_forward_button, self.next_button]:
            btn.SetBackgroundColour(c("button_bg"))
            btn.SetForegroundColour(c("button_fg"))

        # زر التشغيل بمظهر ويندوز الأصلي: أزرار ويندوز تتجاهل لون النص، فلما
        # تلوّنت خلفيته بالأزرق ظهر نصه باهتًا لا يكاد يُقرأ. يتميز بخطه العريض
        self.play_pause_button.SetBackgroundColour(wx.NullColour)
        self.play_pause_button.SetForegroundColour(c("play_fg"))

        # الأيقونات مرسومة بلون نص الزر وقت رسمها، فلازم تترسم من جديد
        # بعد تغيير الألوان وإلا تفضل بلون السمة القديمة
        # (شوف _retint_button_icons)
        # والرسم بعد الألوان مش قبلها.
        self._retint_button_icons()
        self.main_panel.Refresh()

    def _retint_button_icons(self):
        """يعيد رسم أيقونات الأزرار بلون نص كل زر."""
        pairs = (
            (self.stop_button, player_icons.stop_icon),
            (self.seek_backward_button, player_icons.rewind_icon),
            (self.previous_button, player_icons.previous_icon),
            (self.next_button, player_icons.next_icon),
            (self.seek_forward_button, player_icons.forward_icon),
        )
        for button, maker in pairs:
            button.SetBitmap(maker(size=18, scale=self._icon_scale,
                                   colour=button.GetForegroundColour()))
        # زر التشغيل أيقونته بتتبع الحالة
        playing = self.engine.state == PlaybackState.PLAYING
        maker = player_icons.pause_icon if playing else player_icons.play_icon
        self.play_pause_button.SetBitmap(
            maker(size=18, scale=self._icon_scale,
                  colour=self.play_pause_button.GetForegroundColour())
        )

    def _on_toggle_fullscreen(self, event):
        going_fullscreen = not self.IsFullScreen()
        self.ShowFullScreen(going_fullscreen)

        if going_fullscreen:
            self.header_panel.Hide()
            self.controls_panel.Hide()
        else:
            self.header_panel.Show()
            self.controls_panel.Show()
        self.main_panel.Layout()

        message = self.tr.t("announce_fullscreen_on" if going_fullscreen else "announce_fullscreen_off")
        self.status_bar.SetStatusText(message)
        self._announce(message, "announce_fullscreen")

    def _on_escape_exit_fullscreen(self, event):
        if self.IsFullScreen():
            self._on_toggle_fullscreen(event)
        else:
            event.Skip()

    def _apply_media_layout(self, has_video: bool):
        if self._current_media_has_video == has_video:
            if has_video:
                self.video_panel.Show()
                self.audio_spacer_panel.Hide()
                self.engine.set_video_widget_handle(self.video_panel.GetHandle())
                self.video_panel.Refresh()
            else:
                self.video_panel.Hide()
                self.audio_spacer_panel.Show()
                try: self.engine.set_video_widget_handle(0)
                except Exception: pass
                self.audio_spacer_panel.Refresh()
            return

        self._current_media_has_video = has_video

        if has_video:
            self.video_panel.Show()
            self.audio_spacer_panel.Hide()
            self.engine.set_video_widget_handle(self.video_panel.GetHandle())
            self.video_panel.Refresh()
        else:
            self.video_panel.Hide()
            self.audio_spacer_panel.Show()
            try: self.engine.set_video_widget_handle(0)
            except Exception: pass
            self.audio_spacer_panel.Refresh()

        self.main_panel.Layout()
        self.Layout()
        self.Refresh()
