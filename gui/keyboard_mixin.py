# -*- coding: utf-8 -*-
"""
لوحة المفاتيح في النافذة الرئيسية: الاختصارات، والتقديم بالضغط المطوّل على
السهمين، ومفاتيح الوسائط العامة.

نُقلت كما هي من gui/main_window.py لتصغيره.
"""

import time

import wx


class KeyboardMixin:
    """اختصارات النافذة الرئيسية ومفاتيح الوسائط والتقديم المتواصل."""

    _MEDIA_HOTKEY_PLAY_PAUSE = 0xB301
    _MEDIA_HOTKEY_STOP = 0xB302
    _MEDIA_HOTKEY_NEXT = 0xB303
    _MEDIA_HOTKEY_PREV = 0xB304

    def _register_global_media_keys(self):
        if not self.settings.get_enable_global_media_keys():
            return
        hotkeys = (
            (self._MEDIA_HOTKEY_PLAY_PAUSE, getattr(wx, "WXK_MEDIA_PLAY_PAUSE", 0xB3)),
            (self._MEDIA_HOTKEY_STOP, getattr(wx, "WXK_MEDIA_STOP", 0xB2)),
            (self._MEDIA_HOTKEY_NEXT, getattr(wx, "WXK_MEDIA_NEXT_TRACK", 0xB0)),
            (self._MEDIA_HOTKEY_PREV, getattr(wx, "WXK_MEDIA_PREV_TRACK", 0xB1)),
        )
        for hotkey_id, keycode in hotkeys:
            try:
                if self.RegisterHotKey(hotkey_id, wx.MOD_NONE, keycode):
                    self._registered_media_hotkey_ids.add(hotkey_id)
            except Exception:
                pass

    def _unregister_global_media_keys(self):
        for hotkey_id in list(self._registered_media_hotkey_ids):
            try: self.UnregisterHotKey(hotkey_id)
            except Exception: pass
        self._registered_media_hotkey_ids.clear()

    def _refresh_global_media_keys(self):
        self._unregister_global_media_keys()
        self._register_global_media_keys()

    def _on_global_media_hotkey(self, event):
        hotkey_id = event.GetId()
        if hotkey_id == self._MEDIA_HOTKEY_PLAY_PAUSE:
            self._on_play_pause(event)
        elif hotkey_id == self._MEDIA_HOTKEY_STOP:
            self._on_stop(event)
        elif hotkey_id == self._MEDIA_HOTKEY_NEXT:
            self._on_next(event)
        elif hotkey_id == self._MEDIA_HOTKEY_PREV:
            self._on_previous(event)
        elif self.is_editor_hotkey(hotkey_id):
            self._on_editor_hotkey(hotkey_id)

    def _bind_shortcuts(self):
        accel_entries = []

        def bind(modifier, key, handler):
            new_id = wx.NewIdRef()
            self.Bind(wx.EVT_MENU, handler, id=new_id)
            accel_entries.append(wx.AcceleratorEntry(modifier, key, new_id))

        bind(wx.ACCEL_NORMAL, wx.WXK_UP, lambda e: self._volume_relative(5))
        bind(wx.ACCEL_NORMAL, wx.WXK_DOWN, lambda e: self._volume_relative(-5))
        bind(wx.ACCEL_CTRL, wx.WXK_UP, lambda e: self._volume_relative(20))
        bind(wx.ACCEL_CTRL, wx.WXK_DOWN, lambda e: self._volume_relative(-20))
        bind(wx.ACCEL_NORMAL, ord("M"), lambda e: self._on_toggle_mute(e))

        bind(wx.ACCEL_CTRL, wx.WXK_SPACE, self._on_stop)

        bind(wx.ACCEL_NORMAL, ord("R"), self._on_announce_remaining_time)
        bind(wx.ACCEL_NORMAL, ord("E"), self._on_announce_duration)
        bind(wx.ACCEL_NORMAL, ord("T"), self._on_announce_time_status)
        bind(wx.ACCEL_NORMAL, ord("N"), self._on_announce_stream_title)

        bind(wx.ACCEL_SHIFT, ord("Q"), lambda e: self._cycle_equalizer(-1))
        bind(wx.ACCEL_NORMAL, ord("Q"), lambda e: self._cycle_equalizer(1))
        bind(wx.ACCEL_CTRL, ord("E"), self._on_equalizer)
        bind(wx.ACCEL_CTRL, ord("U"), self._on_open_url)
        bind(wx.ACCEL_CTRL, ord("L"), self._on_playlist_dialog)
        bind(wx.ACCEL_CTRL, ord("S"), self._on_save_playlist)

        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("R"), self._on_recorder)
        bind(wx.ACCEL_CTRL, ord("R"), self._on_start_recording_shortcut)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("X"), self._on_media_editor)

        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("P"), self._on_options)

        bind(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("A"), self._on_toggle_accessibility_shortcut)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("H"), self._on_export_shortcuts_doc)
        # تقرير التشخيص (شوف ToolsMixin._on_export_diagnostics)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("D"), self._on_export_diagnostics)

        if self.settings.get_enable_folder_navigation():
            bind(wx.ACCEL_NORMAL, wx.WXK_PAGEDOWN, self._on_next)
            bind(wx.ACCEL_NORMAL, wx.WXK_PAGEUP, self._on_previous)

        numpad_keys = (wx.WXK_NUMPAD1, wx.WXK_NUMPAD2, wx.WXK_NUMPAD3, wx.WXK_NUMPAD4, wx.WXK_NUMPAD5, wx.WXK_NUMPAD6, wx.WXK_NUMPAD7, wx.WXK_NUMPAD8, wx.WXK_NUMPAD9)
        for index, numpad_key in enumerate(numpad_keys, start=1):
            bind(wx.ACCEL_NORMAL, numpad_key, lambda e, p=index * 10: self._seek_to_percent(p))

        bind(wx.ACCEL_NORMAL, wx.WXK_NUMPAD0, lambda e: self._seek_to_start())
        bind(wx.ACCEL_NORMAL, wx.WXK_HOME, lambda e: self._seek_to_start())
        bind(wx.ACCEL_NORMAL, wx.WXK_END, lambda e: self._seek_to_near_end())

        bind(wx.ACCEL_ALT, wx.WXK_UP, lambda e: self._change_speed(0.25))
        bind(wx.ACCEL_ALT, wx.WXK_DOWN, lambda e: self._change_speed(-0.25))
        bind(wx.ACCEL_ALT, wx.WXK_NUMPAD0, lambda e: self._reset_speed())

        bind(wx.ACCEL_CTRL, ord("G"), self._on_go_to_time)

        # Ctrl+Alt+B قبل Ctrl+B: جدول المسرّعات بياخد أول تطابق
        bind(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("B"), lambda e: self._rename_bookmark())
        bind(wx.ACCEL_CTRL, ord("B"), lambda e: self._add_bookmark())
        bind(wx.ACCEL_NORMAL, wx.WXK_F2, lambda e: self._jump_bookmark(forward=True))
        bind(wx.ACCEL_SHIFT, wx.WXK_F2, lambda e: self._jump_bookmark(forward=False))
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("B"), lambda e: self._clear_bookmarks())

        bind(wx.ACCEL_NORMAL, wx.WXK_F11, self._on_toggle_fullscreen)
        bind(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._on_escape_exit_fullscreen)

        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

    def _start_hold_seek(self, keycode, initial_delta_seconds):
        if not self._is_holding_seek:
            self._is_holding_seek = True
            self._holding_key = keycode
            self._seek_speed_multiplier = 1.0
            self._hold_target_position = self.engine.get_effective_position()
            # نقطة البداية علشان مقدار القفزة الكلي يتحسب عند الإفلات
            # (شوف _announce_seek وحدّ الإعلان الأدنى)
            self._hold_start_position = self._hold_target_position
            self.engine.set_muted(True)
            # الضغطة الأولى بالمقدار المضبوط بالضبط: كان المعامل يكبر قبلها
            # فتقفز الضغطة الواحدة 12.5 ثانية بدل 10. التسارع للضغط المطوّل
            self._step_hold_seek(initial_delta_seconds, accelerate=False)
            self._hold_seek_timer.Start(80)

    def _step_hold_seek(self, base_delta, accelerate=True):
        if not self.engine.duration:
            return
        if self._hold_target_position is None:
            self._hold_target_position = self.engine.get_effective_position()

        if accelerate:
            self._seek_speed_multiplier = min(60.0, self._seek_speed_multiplier * 1.25)
        step = base_delta * self._seek_speed_multiplier

        self._hold_target_position = max(0.0, min(self.engine.duration, self._hold_target_position + step))
        self.seek_slider.SetValue(int(self._hold_target_position))
        self._update_info_labels(is_seeking=True, seek_target=self._hold_target_position)

    def _on_hold_seek_timer(self, event):
        if not (wx.GetKeyState(wx.WXK_RIGHT) or wx.GetKeyState(wx.WXK_LEFT)):
            self._stop_hold_seek()
            return

        if self._holding_key in (wx.WXK_RIGHT, wx.WXK_LEFT):
            base_delta = 1.5 if self._holding_key == wx.WXK_RIGHT else -1.5
            self._step_hold_seek(base_delta)
        else:
            self._stop_hold_seek()

    def _stop_hold_seek(self):
        if self._is_holding_seek:
            self._is_holding_seek = False
            self._holding_key = None
            self._hold_seek_timer.Stop()

            if hasattr(self, '_hold_target_position') and self._hold_target_position is not None:
                self.engine.seek(self._hold_target_position)
                self._last_seek_time = time.time()
                target = self._hold_target_position
                self._hold_target_position = None
                start = getattr(self, "_hold_start_position", None)
                jump = target - start if start is not None else None
                self._hold_start_position = None
                self._announce_seek(target, seek_type="seconds", jump_seconds=jump)

            self.engine.set_muted(False)
            self._update_info_labels()

    def _on_key_up(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RIGHT, wx.WXK_LEFT) and self._holding_key == keycode:
            self._stop_hold_seek()
        event.Skip()

    def _on_char_hook(self, event):
        keycode = event.GetKeyCode()
        # Tab مقفول: التنقّل بين الأزرار ممنوع (شوف _enforce_focusless_behavior)
        if keycode == wx.WXK_TAB: return
        alt = event.AltDown()
        ctrl = event.ControlDown() or event.CmdDown()
        shift = event.ShiftDown()

        focused = wx.Window.FindFocus()
        interactive_controls = (wx.Button, wx.TextCtrl, wx.CheckBox, wx.ComboBox, wx.ListBox, wx.RadioButton, wx.SpinCtrl)

        if focused and isinstance(focused, interactive_controls):
            if keycode in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                event.Skip()
                return

        if keycode in (wx.WXK_RIGHT, wx.WXK_LEFT):
            delta = self.SEEK_NORMAL_SECONDS
            if ctrl and shift: delta = self.SEEK_CTRL_SHIFT_SECONDS
            elif ctrl: delta = self.SEEK_CTRL_SECONDS
            elif shift: delta = self.SEEK_SHIFT_SECONDS
            elif alt: delta = self.SEEK_ALT_SECONDS

            if keycode == wx.WXK_LEFT: delta = -delta

            if not (alt or ctrl or shift):
                if self._holding_key != keycode:
                    self._holding_key = keycode
                    self._start_hold_seek(keycode, delta)
            else:
                self._seek_relative(delta)
            return

        if keycode == wx.WXK_SPACE:
            if ctrl and not (alt or shift):
                self._on_stop(event)
                return
            elif not (alt or ctrl or shift):
                self._on_play_pause(event)
                return

        event.Skip()
