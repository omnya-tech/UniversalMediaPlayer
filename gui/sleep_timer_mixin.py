# -*- coding: utf-8 -*-
"""
توابع مؤقّت النوم وإيقاف الكمبيوتر.

    اتفصلت عن MainWindow. نفس self ونفس السلوك.
"""

import time

import wx

from i18n.plural import count_phrase


class SleepTimerDialog(wx.Dialog):
    def __init__(self, parent, tr, default_minutes, default_action_idx):
        self.tr = tr
        super().__init__(parent, title=self.tr.t("sleep_timer_dialog_title"), size=(450, 230))
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_hours = wx.StaticText(panel, label=self.tr.t("lbl_hours"))
        self.combo_hours = wx.ComboBox(panel, choices=[str(i) for i in range(25)], style=wx.CB_READONLY)
        lbl_mins = wx.StaticText(panel, label=self.tr.t("lbl_minutes"))
        self.combo_mins = wx.ComboBox(panel, choices=[str(i) for i in range(60)], style=wx.CB_READONLY)
        h = default_minutes // 60
        m = default_minutes % 60
        self.combo_hours.SetSelection(h if h <= 24 else 24)
        self.combo_mins.SetSelection(m)
        time_sizer.Add(lbl_hours, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, 10)
        time_sizer.Add(self.combo_hours, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        time_sizer.Add(lbl_mins, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, 15)
        time_sizer.Add(self.combo_mins, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        act_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_act = wx.StaticText(panel, label=self.tr.t("lbl_action_required"))
        self.actions = [self.tr.t("action_pause"), self.tr.t("action_close"), self.tr.t("action_shutdown")]
        self.action_keys = ["pause", "close", "shutdown"]
        self.combo_act = wx.ComboBox(panel, choices=self.actions, style=wx.CB_READONLY)
        self.combo_act.SetSelection(default_action_idx if 0 <= default_action_idx < len(self.actions) else 0)
        act_sizer.Add(lbl_act, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        act_sizer.Add(self.combo_act, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)

        # بديل الوقت: الإيقاف عند نهاية الملف الحالي، وهو الأنسب لمن
        # يستمع لمحاضرة أو كتاب قبل النوم
        self.chk_at_end = wx.CheckBox(panel, label=self.tr.t("sleep_at_end_of_file"))
        self.chk_at_end.SetToolTip(self.tr.t("sleep_at_end_of_file_hint"))
        self.chk_at_end.Bind(wx.EVT_CHECKBOX, self._on_toggle_at_end)
        main_sizer.Add(time_sizer, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 15)
        main_sizer.Add(act_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.Add(self.chk_at_end, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, label=self.tr.t("btn_ok_activate"))
        ok_btn.SetDefault()
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=self.tr.t("btn_cancel"))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 20)
        panel.SetSizer(main_sizer)
        self.Layout()
        self.CenterOnParent()

    def _on_toggle_at_end(self, event):
        """اختيار "عند نهاية الملف" بيلغي معنى الساعات والدقائق."""
        at_end = self.chk_at_end.GetValue()
        self.combo_hours.Enable(not at_end)
        self.combo_mins.Enable(not at_end)

    def get_minutes(self): return (self.combo_hours.GetSelection() * 60) + self.combo_mins.GetSelection()
    def get_action_key(self): return self.action_keys[self.combo_act.GetSelection()]
    def get_action_idx(self): return self.combo_act.GetSelection()
    def at_end_of_file(self): return self.chk_at_end.GetValue()


class SleepTimerMixin:
    """توابع مؤقّت النوم وإيقاف الكمبيوتر."""

    def _on_sleep_timer(self, event):
        default_minutes = 30
        if hasattr(self.settings, "get_sleep_timer_last_minutes"):
            try: default_minutes = self.settings.get_sleep_timer_last_minutes()
            except Exception: pass
        dialog = SleepTimerDialog(self, self.tr, default_minutes, self._sleep_timer_action_idx)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            minutes = dialog.get_minutes()
            if minutes < 0: return
            at_end = dialog.at_end_of_file()
            self._sleep_timer_action_idx = dialog.get_action_idx()
            self._sleep_timer_action_key = dialog.get_action_key()
        finally: dialog.Destroy()

        if at_end:
            # المؤقّت الزمني والإيقاف عند النهاية لا يجتمعان: الأحدث
            # يلغي الأقدم
            self._cancel_sleep_timer()
            self._sleep_at_end_of_file = True
            self._announce(self.tr.t("announce_sleep_at_end_set"), "announce_sleep_timer")
            return
        if minutes == 0:
            self._cancel_sleep_timer()
            return
        if hasattr(self.settings, "set_sleep_timer_last_minutes"):
            try: self.settings.set_sleep_timer_last_minutes(minutes)
            except Exception: pass
        self._sleep_timer_end_time = time.time() + (minutes * 60)
        self._is_sleep_timer_active = True
        self.sleep_timer_badge.Show()
        self.header_panel.Layout()
        self._sleep_timer.Stop()
        self._sleep_timer.Start(minutes * 60 * 1000, wx.TIMER_ONE_SHOT)
        self._announce(self.tr.t("announce_sleep_timer_set", duration=count_phrase(self.tr, "count_minutes", minutes)),
                       "announce_sleep_timer")

    def _cancel_sleep_timer(self):
        self._sleep_at_end_of_file = False
        if self._sleep_timer.IsRunning() or self._is_sleep_timer_active:
            self._sleep_timer.Stop()
            self._is_sleep_timer_active = False
            self.sleep_timer_badge.Hide()
            self.header_panel.Layout()
            self._announce(self.tr.t("announce_sleep_timer_cancelled"), "announce_sleep_timer")

    def _on_sleep_timer_fired(self, event):
        self._is_sleep_timer_active = False
        self.sleep_timer_badge.Hide()
        self.header_panel.Layout()
        self._announce(self.tr.t("announce_sleep_timer_triggered"), "announce_sleep_timer")
        self._apply_sleep_timer_action()

    def _apply_sleep_timer_action(self):
        """ينفّذ إجراء مؤقّت النوم - مشترك بين المؤقّت الزمني ونهاية الملف."""
        if self._sleep_timer_action_key == "pause": self.engine.pause()
        elif self._sleep_timer_action_key == "close": self.Close()
        elif self._sleep_timer_action_key == "shutdown": self._shutdown_computer()

    def _shutdown_computer(self):
        # استيراد محلي: لا يُحتاج إليهما إلا عند الإيقاف الفعلي
        import platform
        import subprocess

        system = platform.system()
        try:
            if system == "Windows": subprocess.Popen(["shutdown", "/s", "/t", "30"])
            elif system == "Darwin": subprocess.Popen(["osascript", "-e", 'tell app "System Events" to shut down'])
            elif system == "Linux": subprocess.Popen(["shutdown", "-h", "+1"])
            else:
                self._announce(self.tr.t("announce_shutdown_unsupported"))
                return
        except OSError as error:
            self._announce(self.tr.t("announce_shutdown_failed", error=str(error)))
            return
        self._announce(self.tr.t("announce_shutdown_scheduled"))
