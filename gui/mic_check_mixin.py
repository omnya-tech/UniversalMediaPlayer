# -*- coding: utf-8 -*-
"""
اختبار المايكروفون في نافذة المسجّل: يسجّل عشر ثوانٍ ثم يخبر بالنتيجة نصًا
يقرؤه قارئ الشاشة، مع خطوات الإصلاح وتفاصيل تقنية للنسخ.

نُقلت كما هي من gui/audio_recorder_dialog.py.
"""

import os
import tempfile
import wave

import numpy as np
import wx

from core.audio_recorder import SUPPORTED_SAMPLE_RATES, RecorderError
from core.version import APP_VERSION
from gui.dialog_helpers import bind_escape_closes
from core.logging_setup import configure_logging

_logger = configure_logging()


class MicCheckMixin:
    """اختبار المايكروفون."""

    # مدة اختبار المايكروفون بالثواني
    MIC_CHECK_SECONDS = 10

    def _on_mic_check(self, event):
        if self.recorder.is_recording:
            return
        if not self._devices:
            wx.MessageBox(
                self.tr.t("recorder_error_no_device"),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_WARNING,
            )
            return

        self._mic_check_path = os.path.join(tempfile.gettempdir(), "omnya_mic_check.wav")
        device_index = self._devices[self.device_choice.GetSelection()][0]
        rate_string = self.rate_choice.GetStringSelection()
        try:
            self._mic_check_rate = int(rate_string.split()[0])
        except (ValueError, IndexError):
            self._mic_check_rate = SUPPORTED_SAMPLE_RATES[0]
        self._mic_check_channels = 1 if self.channels_choice.GetSelection() == 0 else 2
        self._mic_check_depth = self._selected_bit_depth()

        # WAV دايمًا: التحليل بيقرا العيّنات الخام من الملف
        try:
            self.recorder.start(
                device_index=device_index,
                sample_rate=self._mic_check_rate,
                channels=self._mic_check_channels,
                wav_path=self._mic_check_path,
                bit_depth=self._mic_check_depth,
                target_ext=".wav",
            )
        except RecorderError as exc:
            wx.MessageBox(str(exc), self.tr.t("recorder_dialog_title"), wx.ICON_ERROR)
            return

        self._mic_check_remaining = self.MIC_CHECK_SECONDS
        self.mic_check_button.Disable()
        self.record_button.Disable()
        self.elapsed_label.SetLabel(str(self._mic_check_remaining))
        if self.announcer:
            self.announcer.announce(
                self.tr.t("mic_check_running", seconds=self._mic_check_remaining)
            )

        self._mic_check_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_mic_check_tick, self._mic_check_timer)
        self._mic_check_timer.Start(1000)

    def _on_mic_check_tick(self, event):
        self._mic_check_remaining -= 1
        if self._mic_check_remaining > 0:
            self.elapsed_label.SetLabel(str(self._mic_check_remaining))
            return

        self._mic_check_timer.Stop()
        self.recorder.stop()
        self.elapsed_label.SetLabel("00:00")
        self.level_meter.set_level(0.0)
        self.mic_check_button.Enable()
        self.record_button.Enable()
        self._show_mic_check_result()

    def _read_mic_check_samples(self):
        try:
            with wave.open(self._mic_check_path, "rb") as handle:
                raw = handle.readframes(handle.getnframes())
        except Exception:
            _logger.exception("تعذّرت قراءة ملف اختبار المايكروفون")
            return None
        if self._mic_check_depth == 16:
            return np.frombuffer(raw, dtype=np.int16)
        if self._mic_check_depth == 24:
            # ثلاثة بايتات للعينة: تُوسَّع إلى int32 بوضعها في أعلى البايتات،
            # فتبقى على مقياس 32 بت نفسه (max_abs تحت)
            triples = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            widened = np.zeros((len(triples), 4), dtype=np.uint8)
            widened[:, 1:] = triples
            return widened.view("<i4").reshape(-1)
        return np.frombuffer(raw, dtype=np.int32)

    def _show_mic_check_result(self):
        from core.mic_check import analyse, technical_line, verdict_message

        samples = self._read_mic_check_samples()
        max_abs = 32768.0 if self._mic_check_depth == 16 else 2147483648.0
        verdict = analyse(samples, max_abs, self.recorder.clip_events)
        message = verdict_message(verdict, self.tr)
        details = technical_line(
            verdict,
            self.device_choice.GetStringSelection() or "?",
            self._mic_check_rate,
            self._mic_check_channels,
            self._mic_check_depth,
            APP_VERSION,
        )

        # ملف الاختبار مؤقت: ما يتسابش في مجلد المؤقتات
        try:
            os.remove(self._mic_check_path)
        except OSError:
            pass

        if self.announcer:
            self.announcer.announce(message)
        self._show_mic_check_dialog(message, details)

    def _show_mic_check_dialog(self, message, details):
        """
        النتيجة في نافذة فيها حقل نص للقراءة فقط لا رسالة عابرة.

        السبب: المستخدم محتاج يقرا الحكم بمهله وينسخ السطر التقني، ورسالة
        منبثقة عادية ما بتسمحش بالتحديد ولا بالنسخ.
        """
        dialog = wx.Dialog(
            self, title=self.tr.t("mic_check_title"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)

        verdict_field = wx.TextCtrl(
            panel, value=message,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(520, 110),
        )
        verdict_field.SetName(self.tr.t("mic_check_title"))
        sizer.Add(verdict_field, flag=wx.EXPAND | wx.ALL, border=12)

        sizer.Add(
            wx.StaticText(panel, label=self.tr.t("mic_check_details_label")),
            flag=wx.LEFT | wx.RIGHT, border=12,
        )
        details_field = wx.TextCtrl(panel, value=details, style=wx.TE_READONLY, size=(520, -1))
        details_field.SetName(self.tr.t("mic_check_details_label"))
        sizer.Add(details_field, flag=wx.EXPAND | wx.ALL, border=12)

        row = wx.BoxSizer(wx.HORIZONTAL)
        copy_button = wx.Button(panel, label=self.tr.t("mic_check_copy_button"))
        copy_button.Bind(wx.EVT_BUTTON, lambda e: self._copy_mic_details(details))
        close_button = wx.Button(panel, wx.ID_CANCEL, label=self.tr.t("options_cancel_button"))
        row.Add(copy_button, flag=wx.RIGHT, border=8)
        row.Add(close_button)
        sizer.Add(row, flag=wx.ALIGN_RIGHT | wx.ALL, border=12)

        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        dialog.SetSizerAndFit(outer)
        bind_escape_closes(dialog)
        verdict_field.SetFocus()
        dialog.ShowModal()
        dialog.Destroy()

    def _copy_mic_details(self, details):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(details))
            wx.TheClipboard.Close()
            if self.announcer:
                self.announcer.announce(self.tr.t("mic_check_copied"))
