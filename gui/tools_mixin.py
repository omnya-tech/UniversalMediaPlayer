# -*- coding: utf-8 -*-
"""
فتح النوافذ والأدوات: الخيارات، حول، الدليل، المسجّل، المحول، القص والدمج،
    وتصدير/استيراد الإعدادات والتقرير التشخيصي.

    الاستيرادات جوّه التوابع مقصودة - دي اللي خلّت الإقلاع ينزل
    من 4538 لـ ~170 مللي ثانية، فما تتنقلش لأعلى الملف.
"""

import logging
import os
import sys

import wx

from accessibility.announcer import ScreenReaderAnnouncer
from core.logging_setup import get_app_data_dir, get_documents_dir
from core.playlist import SUPPORTED_EXTENSIONS
from core.version import APP_VERSION

logger = logging.getLogger(__name__)

# حد ويندوز 32767 حرفًا؛ نترك هامشًا لمسار البرنامج والخيارات وعلامات
# التنصيص حول كل مسار.
_MAX_COMMAND_LINE = 30000


def _write_path_list_if_needed(command, paths):
    """
    يكتب المسارات في ملف مؤقت لو سطر الأوامر هيطول أكتر من اللازم.

    ويندوز بيرفض أي سطر أوامر فوق 32767 حرفًا. مجلد فيه تلتمية ملف
    بمسارات عربية طويلة بيوصل لأربعين ألف حرف - فالمحوّل ما كانش
    بيشتغل أصلًا، أو بيشتغل بجزء من الاختيار.

    وده اللي بيفسّر إن العطل بيظهر "في بعض الأجهزة" بس: نفس العدد
    بيعدّي على جهاز مساراته قصيرة ويفشل على جهاز مجلداته متداخلة
    وأسماؤها عربية. القياس: خمسمية ملف في D:\\a يعدّي، وتلتمية في
    مجلد عربي عميق يفشل.

    بيرجّع مسار الملف، أو None لو سطر الأوامر قصير بما يكفي.
    """
    length = sum(len(part) + 3 for part in command)
    length += sum(len(path) + 3 for path in paths)
    if length <= _MAX_COMMAND_LINE:
        return None

    try:
        import tempfile

        handle, list_path = tempfile.mkstemp(prefix="ump_convert_", suffix=".txt")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write("\n".join(paths))
        return list_path
    except OSError:
        # بلا ملف القائمة يُمرَّر السطر الطويل كما هو: قد يفشل، لكنه لا
        # يكون أسوأ مما كان قبل هذا الإصلاح
        logger.exception("تعذّر كتابة قائمة الملفات المؤقتة")
        return None


class ToolsMixin:
    """فتح النوافذ والأدوات: الخيارات، حول، الدليل، المسجّل، المحول،"""

    def _on_options(self, event):
        # استيراد متأخر: نافذة الخيارات لا تُحتاج عند الإقلاع
        # (انظر رأس الملف)
        from gui.dialogs import OptionsDialog

        dialog = OptionsDialog(self, self.tr, self.settings)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                if dialog.apply_to_settings():
                    self.tr.lang = self.settings.get_language()
                    self.SetMenuBar(None)
                    self._build_menu()
                    self._update_window_title()
                self._bind_shortcuts()
                self.seek_slider.SetHelpText(self._format_seek_help_text())
                self._refresh_global_media_keys()
                self._apply_ui_theme()
                self._announce(self.tr.t("options_saved_announcement"))
        finally: dialog.Destroy()

    def _on_about(self, event):
        # استيراد متأخر: نافذة «حول» لا تُحتاج عند الإقلاع
        # (انظر رأس الملف)
        from gui.dialogs import AboutDialog

        dialog = AboutDialog(self, self.tr, on_open_user_guide=lambda: self._on_user_guide(None))
        try: dialog.ShowModal()
        finally: dialog.Destroy()

    def _on_user_guide(self, event):
        import webbrowser

        from gui.user_guide import build_user_guide_html

        guide_path = os.path.join(get_app_data_dir(), f"user_guide_{self.tr.lang}.html")
        try:
            with open(guide_path, "w", encoding="utf-8") as f:
                f.write(build_user_guide_html(self.tr, self._seek_duration_kwargs()))
        except OSError as e:
            wx.MessageBox(str(e), self.tr.t("menu_user_guide"), wx.ICON_ERROR)
            return
        webbrowser.open(f"file://{guide_path}")

    def _on_export_shortcuts_doc(self, event):
        from gui.user_guide import get_shortcuts_list

        with wx.FileDialog(self, self.tr.t("export_shortcuts_dialog_title"), wildcard="Text files|*.txt|All files|*.*", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            dlg.SetFilename("shortcuts_guide.txt")
            if dlg.ShowModal() == wx.ID_CANCEL: return
            path = dlg.GetPath()
        if not path.lower().endswith(".txt"): path += ".txt"
        header = self.tr.t("shortcuts_header", app_name=self.tr.t("app_title"))
        shortcuts_list = get_shortcuts_list(getattr(self.tr, "lang", "ar"))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + "\n" + "=" * len(header) + "\n\n")
                for line in shortcuts_list: f.write(f"• {line}\n")
            self._announce(self.tr.t("announce_shortcuts_export_success"))
            wx.MessageBox(f"{self.tr.t('announce_shortcuts_export_success')}:\n{path}", self.tr.t("export_shortcuts_dialog_title"), wx.ICON_INFORMATION)
        except Exception as e: wx.MessageBox(str(e), self.tr.t("title_error"), wx.ICON_ERROR)

    def _on_export_settings(self, event):
        with wx.FileDialog(self, self.tr.t("export_settings_dialog_title"), wildcard=self.tr.t("settings_file_wildcard"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            path = dlg.GetPath()
        if not path.lower().endswith(".json"): path += ".json"
        success = self.settings.export_to(path)
        self._announce(self.tr.t("announce_export_settings_success" if success else "announce_export_settings_failed"), "announce_settings_import_export")

    def _on_import_settings(self, event):
        with wx.FileDialog(self, self.tr.t("import_settings_dialog_title"), wildcard=self.tr.t("settings_file_wildcard"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            path = dlg.GetPath()
        success = self.settings.import_from(path)
        self._announce(self.tr.t("announce_import_settings_success" if success else "announce_import_settings_failed"), "announce_settings_import_export")

    def _on_export_diagnostics(self, event):
        """
        يحفظ تقريرًا تشخيصيًا على سطح المكتب ويعلن مكانه.

        على سطح المكتب مباشرة بلا نافذة حفظ عن قصد: المستخدم بيعمل كده وهو
        بيواجه مشكلة أصلًا، ومربع حوار الحفظ احتكاك زيادة لمستخدم قارئ
        شاشة. مسار ثابت + إعلان أبسط بمراحل.
        """
        from core.diagnostics import build_report, contains_personal_information
        from core.logging_setup import configure_logging, log_file_path

        report = build_report(APP_VERSION, self.settings, log_file_path())

        # شبكة الأمان الأخيرة: لو تسرّب معرّف شخصي لا يُحفظ شيء
        if contains_personal_information(report):
            configure_logging().warning(
                "التقرير التشخيصي فيه معلومات شخصية - أُلغي الحفظ"
            )
            self._announce(self.tr.t("diagnostics_blocked"), force=True)
            return

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(desktop):
            desktop = get_documents_dir()
        target = os.path.join(desktop, "Omnya_Diagnostics.txt")

        try:
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(report)
        except OSError as exc:
            self._announce(self.tr.t("diagnostics_failed", error=str(exc)), force=True)
            return

        self._announce(self.tr.t("diagnostics_saved", name=os.path.basename(target)), force=True)
        wx.MessageBox(
            self.tr.t("diagnostics_saved_details", path=target),
            self.tr.t("diagnostics_title"),
            wx.ICON_INFORMATION,
        )

    def _on_recorder(self, event):
        # المسجّل نافذة مستقلة بلا أب: لو كان ابنًا للنافذة الرئيسية
        # لاختفى معها عند تصغيرها، والتسجيل غالبًا يجري والمشغّل مصغَّر.
        # وله معلن خاص به، فإعلاناته تُنطق وهو في المقدمة.
        # (الاستيراد متأخر؛ انظر رأس الملف)
        from gui.audio_recorder_dialog import AudioRecorderDialog

        if getattr(self, "_quick_record_dialog", None) is None:
            self._quick_record_dialog = AudioRecorderDialog(None, self.tr, None, self.settings)
            self._quick_record_dialog.announcer = ScreenReaderAnnouncer(self._quick_record_dialog)
            self._quick_record_dialog.Bind(wx.EVT_CLOSE, self._on_quick_record_dialog_closed)
        self._quick_record_dialog.Show()
        self._quick_record_dialog.Raise()

    def _on_media_editor(self, event):
        # نافذة مستقلة في نفس العملية، مثل المسجّل: القص والدمج نسخ مباشر
        # سريع في خيط خلفي، ولا يحتاج عملية منفصلة كالمحوّل. القص الدقيق
        # للفيديو وحده يعيد الترميز، وهو أيضًا في الخيط الخلفي.
        # والملف المفتوح في المشغّل يُوضع فيها جاهزًا، وزر «الموضع
        # الحالي» يقرأ موضع التشغيل منها.
        # (الاستيراد متأخر؛ انظر رأس الملف)
        from core.streams import is_stream_url
        from gui.media_editor_dialog import MediaEditorDialog

        dialog = getattr(self, "_media_editor_dialog", None)
        if dialog:
            dialog.Show()
            dialog.Raise()
            return

        current = self._current_file_path
        if current and (is_stream_url(current) or not os.path.isfile(current)):
            current = None

        def position_provider():
            path = self._current_file_path
            if not path or is_stream_url(path):
                return None
            return path, self.engine.get_current_position()

        dialog = MediaEditorDialog(self.tr, initial_path=current, position_provider=position_provider,
                                   bookmarks_provider=self.settings.get_bookmark_entries)
        dialog.announcer = ScreenReaderAnnouncer(dialog)
        self._media_editor_dialog = dialog
        dialog.Show()
        dialog.Raise()

    def _on_converter(self, event):
        self._launch_standalone_converter()

    def _launch_standalone_converter(self, paths=None, is_folder=False):
        # المحوّل يعمل في عملية منفصلة، فتحويل ثقيل لا يجمّد المشغّل
        import platform
        import subprocess

        cmd = [sys.executable]
        if sys.executable.lower().endswith("python.exe") or sys.executable.lower().endswith("pythonw.exe"):
            main_script = sys.argv[0]
            if not main_script.endswith(".py"):
                main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
            cmd.append(main_script)

        cmd.append("--converter-only")
        if paths:
            list_file = _write_path_list_if_needed(cmd, paths)
            if list_file:
                cmd.append("--file-list")
                cmd.append(list_file)
            else:
                cmd.extend(paths)

        flags = 0
        if platform.system() == "Windows":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(cmd, creationflags=flags)

    def open_converter_with_paths(self, paths, is_folder=False):
        if not paths: return
        self._launch_standalone_converter(paths, is_folder)

    # مهلة التجميع: ويندوز يشغّل نسخة من البرنامج لكل ملف محدد عند
    # «تحويل» من قائمة السياق، فتصل الطلبات متتابعة خلال أجزاء من الثانية.
    # نصف ثانية تكفي لجمعها دون تأخير محسوس.
    _CONVERT_BATCH_MS = 500

    def queue_converter_paths(self, paths, is_folder=False):
        """
        يجمّع ملفات وصلت من طلبات متلاحقة، ويفتح محوّلًا واحدًا بيها.

        كل طلب جديد بيأجّل الفتح شوية كمان، فطابور العمليات اللي ويندوز
        بيشغّلها بيتلمّ في نداء واحد.
        """
        if not paths:
            return

        pending = getattr(self, "_pending_convert_paths", None)
        if pending is None:
            pending = self._pending_convert_paths = []
        seen = set(pending)
        for path in paths:
            if path not in seen:
                seen.add(path)
                pending.append(path)
        self._pending_convert_is_folder = is_folder or getattr(
            self, "_pending_convert_is_folder", False)

        # مؤقّت واحد يُعاد ضبطه مع كل طلب: الفتح يحدث بعد آخر طلب
        # بنصف ثانية، لا بعد أوّلها، فلا ينقسم الاختيار على
        # محوّلين.
        # (CallLater يعمل في خيط الواجهة، فلا حاجة لقفل)
        timer = getattr(self, "_convert_batch_timer", None)
        if timer is not None and timer.IsRunning():
            timer.Restart(self._CONVERT_BATCH_MS)
            return
        self._convert_batch_timer = wx.CallLater(
            self._CONVERT_BATCH_MS, self._flush_converter_queue)

    def _flush_converter_queue(self):
        paths = getattr(self, "_pending_convert_paths", None)
        if not paths:
            return
        is_folder = getattr(self, "_pending_convert_is_folder", False)
        self._pending_convert_paths = []
        self._pending_convert_is_folder = False
        self._launch_standalone_converter(paths, is_folder)

    def open_converter_with_folder(self, folder):
        try: entries = sorted(os.listdir(folder), key=str.lower)
        except OSError: return
        paths = [os.path.join(folder, n) for n in entries if os.path.splitext(n)[1].lower() in SUPPORTED_EXTENSIONS]
        if not paths:
            wx.MessageBox(self.tr.t("converter_error_no_files"), self.tr.t("converter_dialog_title"), wx.ICON_WARNING)
            return
        self._launch_standalone_converter(paths, is_folder=True)
