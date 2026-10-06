# -*- coding: utf-8 -*-
import os
import platform
import ctypes
import wx

from core.converter import (
    CRF_SUPPORTED_VCODECS,
    VIDEO_FORMATS,
    BatchConverter,
    ConversionError,
    get_audio_codec_for_extension,
    get_audio_sample_rate_options,
    get_supported_target_extensions,
    probe_media_info,
    target_supports_audio,
)
from gui.audio_bitrate_widget import current_audio_bitrate_bps, refresh_audio_bitrate_choice
from gui.dialog_helpers import bind_escape_closes, bind_space_like_enter
from gui.format_utils import format_time
from gui.value_choice import (
    CRF_VALUES,
    FRAME_RATES,
    VIDEO_BITRATES_KBPS,
    VIDEO_HEIGHTS,
    VIDEO_WIDTHS,
    ValueChoice,
    format_number,
)
from core.notification_sound import play_completion_chime, play_error_chime
from i18n.plural import count_phrase
from accessibility.announcer import _resource_path

_SAMPLE_RATES = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000]


def get_default_converter_dir(tr) -> str:
    """
    مجلد الملفات المحولة من إعدادات المستخدم (Settings.resolve_output_folders).

    كان يُبنى من نصوص الواجهة («مشغل الوسائط الشامل» بلا «- Omnya»)، فيصنع
    مجلدًا رئيسيًا ثانيًا بجانب مجلد البرنامج، وبالإنجليزية ثالثًا.
    """
    from core.settings import default_output_folder

    target_folder = default_output_folder("converted")
    try:
        os.makedirs(target_folder, exist_ok=True)
    except OSError:
        pass
    return target_folder


def _format_file_size(tr, num_bytes) -> str:
    if not num_bytes:
        return None
    size = float(num_bytes)
    unit_keys = [
        "converter_file_info_unit_bytes",
        "converter_file_info_unit_kb",
        "converter_file_info_unit_mb",
        "converter_file_info_unit_gb",
    ]
    for index, unit_key in enumerate(unit_keys):
        if size < 1024.0 or index == len(unit_keys) - 1:
            formatted = f"{size:.0f}" if index == 0 else f"{size:.1f}"
            return f"{formatted} {tr.t(unit_key)}"
        size /= 1024.0
    return None


def _format_bit_rate(tr, bits_per_second) -> str:
    if not bits_per_second:
        return None
    return tr.t("converter_file_info_kbps_value", value=int(bits_per_second) // 1000)


def _unique_output_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


class ConverterDialog(wx.Frame):
    def __init__(self, parent, tr, announcer, settings=None, initial_files=None, initial_is_video=None, subfolder_name=None):
        super().__init__(
            None,
            title=tr.t("converter_dialog_title"),
            size=(600, 760),
            style=wx.DEFAULT_FRAME_STYLE,
        )

        self.tr = tr
        self.announcer = announcer
        self.settings = settings
        self._input_paths = list(initial_files) if initial_files else []
        self._initial_is_video = initial_is_video

        self._set_app_icon()

        # نافذة مستقلة لها زرها في شريط المهام، فيصل إليها المستخدم بـ Alt+Tab
        if platform.system() == "Windows":
            try:
                hwnd = self.GetHandle()
                user32 = ctypes.windll.user32
                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000

                if hasattr(user32, "GetWindowLongPtrW"):
                    get_long = user32.GetWindowLongPtrW
                    set_long = user32.SetWindowLongPtrW
                else:
                    get_long = user32.GetWindowLongW
                    set_long = user32.SetWindowLongW

                get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
                get_long.restype = ctypes.c_void_p
                set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                set_long.restype = ctypes.c_void_p

                ex_style = get_long(hwnd, GWL_EXSTYLE)
                if ex_style is not None:
                    set_long(hwnd, GWL_EXSTYLE, ex_style | WS_EX_APPWINDOW)
            except Exception as e:
                pass

        configured_folder = self.settings.get_converter_output_folder() if self.settings is not None else ""
        if configured_folder and os.path.exists(configured_folder):
            self._output_folder = configured_folder
        else:
            self._output_folder = get_default_converter_dir(self.tr)

        # حفظ طلب المجلد الفرعي الصريح (لو تم إرساله من القائمة السياقية مثلاً)
        self._explicit_subfolder = subfolder_name
        self._subfolder_name = subfolder_name
        
        # لا مجلد فرعي لكل دفعة: كان يُصنع مجلد باسم مجلد المصدر مع كل
        # تحويل لعدة ملفات، فازدحم مجلد الملفات المحولة بمجلدات مكررة

        self._converter = None
        self._is_converting = False
        self._last_announced_pct = -1

        self._build_ui()
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _set_app_icon(self):
        icon_path = _resource_path("resources", "omnya_icon.ico")
        try:
            if os.path.isfile(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def _update_subfolder_and_label(self):

        if hasattr(self, 'output_folder_label') and self.output_folder_label:
            display_folder = (
                os.path.join(self._output_folder, self._subfolder_name)
                if self._subfolder_name
                else self._output_folder
            )
            if not display_folder:
                display_folder = self.tr.t("converter_output_folder_none")
            self.output_folder_label.SetLabel(display_folder)
            self.output_folder_label.SetToolTip(display_folder)
            self.Layout()

    def add_input_files(self, paths):
        added_count = 0
        for p in paths:
            if p not in self._input_paths:
                self._input_paths.append(p)
                self.files_listbox.Append(os.path.basename(p))
                added_count += 1

        self._update_subfolder_and_label()

        if added_count > 0:
            self._refresh_file_info()
            if self.announcer:
                self.announcer.announce(
                    self.tr.t("converter_announce_files_added",
                              files=count_phrase(self.tr, "count_files", added_count))
                )

        self.Raise()
        self.SetFocus()

    def _build_ui(self):
        outer_panel = wx.Panel(self)
        scroller = wx.ScrolledWindow(outer_panel, style=wx.VSCROLL)
        scroller.SetScrollRate(0, 20)
        panel = scroller
        sizer = wx.BoxSizer(wx.VERTICAL)
        tr = self.tr

        files_label = wx.StaticText(panel, label=tr.t("converter_files_label"))
        sizer.Add(files_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.files_listbox = wx.ListBox(panel, style=wx.LB_EXTENDED, size=(-1, 110))
        self.files_listbox.SetName(tr.t("converter_files_label"))
        self.Bind(wx.EVT_LISTBOX, self._on_file_selection_changed, self.files_listbox)
        sizer.Add(self.files_listbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        files_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_files_button = wx.Button(panel, label=tr.t("converter_add_files_button"))
        remove_files_button = wx.Button(panel, label=tr.t("converter_remove_files_button"))
        clear_files_button = wx.Button(panel, label=tr.t("converter_clear_files_button"))
        self.Bind(wx.EVT_BUTTON, self._on_add_files, add_files_button)
        self.Bind(wx.EVT_BUTTON, self._on_remove_selected, remove_files_button)
        self.Bind(wx.EVT_BUTTON, self._on_clear_files, clear_files_button)
        files_buttons_sizer.Add(add_files_button, flag=wx.RIGHT, border=8)
        files_buttons_sizer.Add(remove_files_button, flag=wx.RIGHT, border=8)
        files_buttons_sizer.Add(clear_files_button)
        sizer.Add(files_buttons_sizer, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.file_info_label = wx.StaticText(panel, label=tr.t("converter_file_info_none"))
        self.file_info_label.SetName(tr.t("converter_file_info_section_label"))
        sizer.Add(self.file_info_label, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.ALL, border=10)

        self.media_type_radio = wx.RadioBox(
            panel,
            label=tr.t("converter_media_type_label"),
            choices=[tr.t("converter_media_type_audio"), tr.t("converter_media_type_video")],
        )
        self.media_type_radio.SetName(tr.t("converter_media_type_label"))
        if self._initial_is_video is not None:
            self.media_type_radio.SetSelection(1 if self._initial_is_video else 0)
        elif self.settings is not None:
            self.media_type_radio.SetSelection(1 if self.settings.get_converter_default_is_video() else 0)
        self.Bind(wx.EVT_RADIOBOX, self._on_media_type_change, self.media_type_radio)
        sizer.Add(self.media_type_radio, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        format_row = wx.BoxSizer(wx.HORIZONTAL)
        format_label = wx.StaticText(panel, label=tr.t("converter_target_format_label"))
        self.format_choice = wx.Choice(panel)
        self.format_choice.SetName(tr.t("converter_target_format_label"))
        self.Bind(wx.EVT_CHOICE, self._on_format_change, self.format_choice)
        format_row.Add(format_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        format_row.Add(self.format_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(format_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.ALL, border=10)

        audio_section_label = wx.StaticText(panel, label=tr.t("converter_advanced_audio_section_label"))
        sizer.Add(audio_section_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.audio_no_track_note = wx.StaticText(panel, label=tr.t("converter_no_audio_track_note"))
        sizer.Add(self.audio_no_track_note, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.audio_bitrate_row = wx.BoxSizer(wx.HORIZONTAL)
        audio_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_audio_bitrate_label"))
        self.audio_bitrate_choice = wx.Choice(panel)
        self.audio_bitrate_choice.SetName(tr.t("converter_custom_audio_bitrate_label"))
        self.audio_bitrate_lossless_note = wx.StaticText(
            panel, label=tr.t("converter_audio_bitrate_not_applicable")
        )
        self.audio_bitrate_row.Add(audio_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.audio_bitrate_row.Add(self.audio_bitrate_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        self.audio_bitrate_row.Add(
            self.audio_bitrate_lossless_note, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=4
        )
        sizer.Add(self.audio_bitrate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.sample_rate_row = wx.BoxSizer(wx.HORIZONTAL)
        sample_rate_label = wx.StaticText(panel, label=tr.t("converter_sample_rate_label"))
        self.sample_rate_choice = wx.Choice(panel)
        self.sample_rate_choice.SetName(tr.t("converter_sample_rate_label"))
        self.sample_rate_row.Add(sample_rate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.sample_rate_row.Add(self.sample_rate_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.sample_rate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.channels_row = wx.BoxSizer(wx.HORIZONTAL)
        channels_label = wx.StaticText(panel, label=tr.t("converter_channels_label"))
        self.channels_choice = wx.Choice(
            panel,
            choices=[
                tr.t("converter_channels_source"),
                tr.t("converter_channels_mono"),
                tr.t("converter_channels_stereo"),
            ],
        )
        self.channels_choice.SetName(tr.t("converter_channels_label"))
        self.channels_choice.SetSelection(0)
        self.channels_row.Add(channels_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.channels_row.Add(self.channels_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.channels_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.ALL, border=10)

        self.video_section_label = wx.StaticText(panel, label=tr.t("converter_advanced_video_section_label"))
        sizer.Add(self.video_section_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.video_quality_mode_label = wx.StaticText(panel, label=tr.t("converter_video_quality_mode_label"))
        sizer.Add(self.video_quality_mode_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.quality_mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.quality_mode_bitrate_radio = wx.RadioButton(
            panel, label=tr.t("converter_video_quality_mode_bitrate"), style=wx.RB_GROUP
        )
        self.quality_mode_crf_radio = wx.RadioButton(panel, label=tr.t("converter_video_quality_mode_crf"))
        self.quality_mode_row.Add(self.quality_mode_bitrate_radio, flag=wx.RIGHT, border=16)
        self.quality_mode_row.Add(self.quality_mode_crf_radio)
        self.Bind(wx.EVT_RADIOBUTTON, self._on_quality_mode_change, self.quality_mode_bitrate_radio)
        self.Bind(wx.EVT_RADIOBUTTON, self._on_quality_mode_change, self.quality_mode_crf_radio)
        sizer.Add(self.quality_mode_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.video_bitrate_row = wx.BoxSizer(wx.HORIZONTAL)
        video_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_video_bitrate_label"))
        self.video_bitrate_spin = ValueChoice(panel, VIDEO_BITRATES_KBPS, initial=4000)
        self.video_bitrate_spin.SetName(tr.t("converter_custom_video_bitrate_label"))
        self.video_bitrate_row.Add(video_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.video_bitrate_row.Add(self.video_bitrate_spin, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.video_bitrate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.crf_row = wx.BoxSizer(wx.HORIZONTAL)
        crf_label = wx.StaticText(panel, label=tr.t("converter_crf_label"))
        self.crf_spin = ValueChoice(panel, CRF_VALUES, initial=23)
        self.crf_spin.SetName(tr.t("converter_crf_label"))
        self.crf_row.Add(crf_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.crf_row.Add(self.crf_spin, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.crf_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.resolution_row = wx.BoxSizer(wx.HORIZONTAL)
        resolution_label = wx.StaticText(panel, label=tr.t("converter_resolution_label"))
        self.resolution_choice = wx.Choice(
            panel,
            choices=[tr.t("converter_resolution_source"), tr.t("converter_resolution_custom")],
        )
        self.resolution_choice.SetName(tr.t("converter_resolution_label"))
        self.resolution_choice.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_resolution_mode_change, self.resolution_choice)
        self.resolution_row.Add(resolution_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.resolution_row.Add(self.resolution_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.resolution_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.resolution_custom_row = wx.BoxSizer(wx.HORIZONTAL)
        width_label = wx.StaticText(panel, label=tr.t("converter_width_label"))
        self.width_spin = ValueChoice(panel, VIDEO_WIDTHS, initial=1280)
        self.width_spin.SetName(tr.t("converter_width_label"))
        height_label = wx.StaticText(panel, label=tr.t("converter_height_label"))
        self.height_spin = ValueChoice(panel, VIDEO_HEIGHTS, initial=720)
        self.height_spin.SetName(tr.t("converter_height_label"))
        self.resolution_custom_row.Add(width_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.resolution_custom_row.Add(self.width_spin, flag=wx.RIGHT, border=16)
        self.resolution_custom_row.Add(height_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.resolution_custom_row.Add(self.height_spin, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.resolution_custom_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.frame_rate_row = wx.BoxSizer(wx.HORIZONTAL)
        frame_rate_label = wx.StaticText(panel, label=tr.t("converter_frame_rate_label"))
        self.frame_rate_choice = wx.Choice(
            panel,
            choices=[tr.t("converter_frame_rate_source"), tr.t("converter_frame_rate_custom")],
        )
        self.frame_rate_choice.SetName(tr.t("converter_frame_rate_label"))
        self.frame_rate_choice.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_frame_rate_mode_change, self.frame_rate_choice)
        self.frame_rate_row.Add(frame_rate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.frame_rate_row.Add(self.frame_rate_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.frame_rate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.frame_rate_custom_row = wx.BoxSizer(wx.HORIZONTAL)
        frame_rate_value_label = wx.StaticText(panel, label=tr.t("converter_frame_rate_value_label"))
        self.frame_rate_spin = ValueChoice(panel, FRAME_RATES, initial=30, formatter=format_number)
        self.frame_rate_spin.SetName(tr.t("converter_frame_rate_value_label"))
        self.frame_rate_custom_row.Add(frame_rate_value_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.frame_rate_custom_row.Add(self.frame_rate_spin, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.frame_rate_custom_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.ALL, border=10)

        output_row = wx.BoxSizer(wx.HORIZONTAL)
        display_folder = (
            os.path.join(self._output_folder, self._subfolder_name)
            if self._subfolder_name
            else self._output_folder
        )
        initial_folder_text = display_folder if display_folder else tr.t("converter_output_folder_none")
        # المسار الطويل يُختصر من الوسط بـ«...»، ويظهر كاملًا في التلميح
        self.output_folder_label = wx.StaticText(panel, label=initial_folder_text,
                                                 style=wx.ST_ELLIPSIZE_MIDDLE)
        self.output_folder_label.SetToolTip(initial_folder_text)
        # بلا عرض أدنى صغير يأخذ النص عرضه كاملًا فيمدّ النافذة ولا يُختصر
        self.output_folder_label.SetMinSize((60, -1))
        self.output_folder_label.SetName(tr.t("converter_output_folder_label"))
        output_row.Add(self.output_folder_label, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        sizer.Add(output_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.ALL, border=10)

        self.progress_label = wx.StaticText(panel, label=tr.t("converter_progress_idle"))
        self.progress_label.SetName(tr.t("converter_progress_idle"))
        sizer.Add(self.progress_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.progress_gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.progress_gauge.SetName(tr.t("converter_progress_idle"))
        sizer.Add(self.progress_gauge, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        sizer.AddSpacer(10)
        panel.SetSizer(sizer)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.convert_button = wx.Button(outer_panel, label=tr.t("converter_start_button"))
        self.convert_button.SetDefault()
        bind_space_like_enter(self)
        bind_escape_closes(self)
        self.cancel_button = wx.Button(outer_panel, label=tr.t("converter_cancel_button"))
        self.cancel_button.Disable()
        close_button = wx.Button(outer_panel, wx.ID_CLOSE, label=tr.t("converter_close_button"))
        self.Bind(wx.EVT_BUTTON, self._on_start_conversion, self.convert_button)
        self.Bind(wx.EVT_BUTTON, self._on_cancel_conversion, self.cancel_button)
        self.Bind(wx.EVT_BUTTON, lambda e: self.Close(), close_button)
        buttons_sizer.Add(self.convert_button, flag=wx.RIGHT, border=8)
        buttons_sizer.Add(self.cancel_button, flag=wx.RIGHT, border=8)
        buttons_sizer.Add(close_button)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(scroller, proportion=1, flag=wx.EXPAND)
        outer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=12)
        outer_panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(outer_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(frame_sizer)

        if self.settings is not None:
            self.video_bitrate_spin.SetValue(self.settings.get_converter_default_video_bitrate())

        self._refresh_format_choices(prefer_default=True)
        self._refresh_video_section_visibility()
        self._refresh_audio_section_visibility()
        self._refresh_quality_mode_availability()
        self._refresh_quality_mode_visibility()
        self._refresh_resolution_visibility()
        self._refresh_frame_rate_visibility()
        for path in self._input_paths:
            self.files_listbox.Append(os.path.basename(path))
        if self._input_paths:
            self.files_listbox.SetSelection(0)
        self._refresh_file_info()
        self.files_listbox.SetFocus()

    def _on_add_files(self, event):
        with wx.FileDialog(
            self,
            message=self.tr.t("converter_add_files_button"),
            wildcard=self.tr.t("dialog_open_wildcard"),
            style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            dlg.SetFilterIndex(1)
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            new_paths = dlg.GetPaths()

        first_new_index = len(self._input_paths)
        for path in new_paths:
            if path not in self._input_paths:
                self._input_paths.append(path)
                self.files_listbox.Append(os.path.basename(path))

        self._update_subfolder_and_label()

        if new_paths and not self.files_listbox.GetSelections():
            self.files_listbox.SetSelection(first_new_index)
        self._refresh_file_info()

        self.announcer.announce(
            self.tr.t("converter_announce_files_added",
                      files=count_phrase(self.tr, "count_files", len(new_paths)))
        )

    def _on_remove_selected(self, event):
        selected = list(self.files_listbox.GetSelections())
        if not selected:
            return
        for index in sorted(selected, reverse=True):
            del self._input_paths[index]
            self.files_listbox.Delete(index)
            
        self._update_subfolder_and_label()

        self._refresh_file_info()
        self.announcer.announce(self.tr.t("converter_announce_files_removed"))

    def _on_clear_files(self, event):
        self._input_paths = []
        self.files_listbox.Clear()
        
        self._update_subfolder_and_label()
        
        self._refresh_file_info()
        self.announcer.announce(self.tr.t("converter_announce_files_removed"))

    def _on_file_selection_changed(self, event):
        self._refresh_file_info()

    def _refresh_file_info(self):
        tr = self.tr
        selections = self.files_listbox.GetSelections()
        if selections:
            path = self._input_paths[selections[0]]
        elif self._input_paths:
            path = self._input_paths[0]
        else:
            self.file_info_label.SetLabel(tr.t("converter_file_info_none"))
            self.Layout()
            return

        try:
            info = probe_media_info(path)
        except ConversionError as exc:
            self.file_info_label.SetLabel(tr.t("converter_file_info_error", error=str(exc)))
            self.Layout()
            return

        na = tr.t("converter_file_info_not_available")
        container_display = info["container_format"] or na
        
        lines = [
            tr.t(
                "converter_file_info_general_line",
                container=container_display,
                duration=format_time(info["duration"]) if info["duration"] else na,
                size=_format_file_size(tr, info["file_size"]) or na,
            )
        ]

        if info["video"] is not None:
            video = info["video"]
            resolution = (
                f"{video['width']}x{video['height']}" if video["width"] and video["height"] else na
            )
            lines.append(
                tr.t(
                    "converter_file_info_video_line",
                    codec=video["codec"] or na,
                    resolution=resolution,
                    frame_rate=f"{video['frame_rate']:.2f}" if video["frame_rate"] else na,
                    bit_rate=_format_bit_rate(tr, video["bit_rate"]) or na,
                )
            )

        if info["audio"] is not None:
            audio = info["audio"]
            lines.append(
                tr.t(
                    "converter_file_info_audio_line",
                    codec=audio["codec"] or na,
                    sample_rate=self.tr.t("sample_rate_value", rate=audio["sample_rate"]) if audio["sample_rate"] else na,
                    channels=str(audio["channels"]) if audio["channels"] else na,
                    bit_rate=_format_bit_rate(tr, audio["bit_rate"])
                    or _format_bit_rate(tr, info["overall_bit_rate"])
                    or na,
                )
            )

        self.file_info_label.SetLabel("\n".join(lines))
        self.Layout()

    def _is_video_mode(self) -> bool:
        return self.media_type_radio.GetSelection() == 1

    def _current_target_ext(self):
        selection = self.format_choice.GetStringSelection()
        return selection if selection else None

    def _current_vcodec(self):
        ext = self._current_target_ext()
        if not ext or not self._is_video_mode():
            return None
        preset = VIDEO_FORMATS.get(ext)
        return preset.get("vcodec") if preset else None

    def _refresh_format_choices(self, prefer_default: bool = False):
        extensions = get_supported_target_extensions(self._is_video_mode())
        self.format_choice.Clear()
        self.format_choice.AppendItems(extensions)
        if not extensions:
            return
        selection = 0
        if prefer_default and self.settings is not None:
            saved_format = self.settings.get_converter_default_format()
            found = self.format_choice.FindString(saved_format)
            if found != wx.NOT_FOUND:
                selection = found
        self.format_choice.SetSelection(selection)

    def _on_media_type_change(self, event):
        self._refresh_format_choices()
        self._refresh_video_section_visibility()
        self._refresh_audio_section_visibility()
        self._refresh_quality_mode_availability()

    def _on_format_change(self, event):
        self._refresh_audio_section_visibility()
        self._refresh_quality_mode_availability()

    def _refresh_audio_section_visibility(self):
        ext = self._current_target_ext()
        is_video = self._is_video_mode()
        has_audio_track = (not is_video) or (ext is not None and target_supports_audio(ext, True))
        self.audio_no_track_note.Show(is_video and not has_audio_track)
        self.audio_bitrate_row.ShowItems(has_audio_track)
        self.sample_rate_row.ShowItems(has_audio_track)
        self.channels_row.ShowItems(has_audio_track)
        if has_audio_track:
            self._refresh_audio_bitrate_options(ext, is_video)
            self._refresh_audio_sample_rate_options(ext, is_video)
        self.Layout()

    def _refresh_audio_bitrate_options(self, ext, is_video):
        refresh_audio_bitrate_choice(
            self.audio_bitrate_choice,
            self.audio_bitrate_lossless_note,
            self.tr,
            ext,
            is_video,
            self._current_audio_bitrate_bps(),
        )

    def _refresh_audio_sample_rate_options(self, ext, is_video):
        codec = get_audio_codec_for_extension(ext, is_video) if ext else None
        valid_rates = get_audio_sample_rate_options(codec) if codec else None
        rates_to_show = valid_rates if valid_rates is not None else _SAMPLE_RATES

        previous_selection = self.sample_rate_choice.GetSelection()
        previous_rate = (
            self.sample_rate_choice.GetClientData(previous_selection)
            if previous_selection > 0
            else None
        )

        self.sample_rate_choice.Clear()
        self.sample_rate_choice.Append(self.tr.t("converter_sample_rate_source"), None)
        for rate in rates_to_show:
            self.sample_rate_choice.Append(self.tr.t("sample_rate_value", rate=rate), rate)

        if previous_rate is not None and previous_rate in rates_to_show:
            for index in range(self.sample_rate_choice.GetCount()):
                if self.sample_rate_choice.GetClientData(index) == previous_rate:
                    self.sample_rate_choice.SetSelection(index)
                    return
        self.sample_rate_choice.SetSelection(0)

    def _current_audio_bitrate_bps(self) -> int:
        if not self.audio_bitrate_choice.IsShown():
            return 0
        fallback = (
            self.settings.get_converter_default_audio_bitrate() * 1000
            if self.settings is not None
            else 0
        )
        return current_audio_bitrate_bps(self.audio_bitrate_choice, fallback)

    def _refresh_video_section_visibility(self):
        is_video = self._is_video_mode()
        for control in (
            self.video_section_label,
            self.video_quality_mode_label,
            self.quality_mode_row,
            self.resolution_row,
            self.frame_rate_row,
        ):
            control.ShowItems(is_video) if hasattr(control, "ShowItems") else control.Show(is_video)
        if not is_video:
            self.video_bitrate_row.ShowItems(False)
            self.crf_row.ShowItems(False)
            self.resolution_custom_row.ShowItems(False)
            self.frame_rate_custom_row.ShowItems(False)
        self.Layout()

    def _refresh_quality_mode_availability(self):
        vcodec = self._current_vcodec()
        crf_supported = vcodec in CRF_SUPPORTED_VCODECS
        self.quality_mode_crf_radio.Enable(crf_supported)
        self.quality_mode_crf_radio.SetLabel(
            self.tr.t("converter_video_quality_mode_crf")
            if crf_supported
            else self.tr.t("converter_video_quality_mode_crf_unavailable")
        )
        if not crf_supported and self.quality_mode_crf_radio.GetValue():
            self.quality_mode_bitrate_radio.SetValue(True)
        self._refresh_quality_mode_visibility()

    def _on_quality_mode_change(self, event):
        self._refresh_quality_mode_visibility()

    def _refresh_quality_mode_visibility(self):
        if not self._is_video_mode():
            return
        use_crf = self.quality_mode_crf_radio.GetValue()
        self.video_bitrate_row.ShowItems(not use_crf)
        self.crf_row.ShowItems(use_crf)
        self.Layout()

    def _on_resolution_mode_change(self, event):
        self._refresh_resolution_visibility()

    def _refresh_resolution_visibility(self):
        is_custom = self.resolution_choice.GetSelection() == 1
        self.resolution_custom_row.ShowItems(is_custom and self._is_video_mode())
        self.Layout()

    def _on_frame_rate_mode_change(self, event):
        self._refresh_frame_rate_visibility()

    def _refresh_frame_rate_visibility(self):
        is_custom = self.frame_rate_choice.GetSelection() == 1
        self.frame_rate_custom_row.ShowItems(is_custom and self._is_video_mode())
        self.Layout()

    def _get_conversion_params(self):
        is_video = self._is_video_mode()

        audio_bitrate = self._current_audio_bitrate_bps() if self.audio_bitrate_choice.IsShown() else 0

        sample_rate_index = self.sample_rate_choice.GetSelection()
        sample_rate = (
            None if sample_rate_index <= 0 else self.sample_rate_choice.GetClientData(sample_rate_index)
        )

        channels_index = self.channels_choice.GetSelection()
        channels = None if channels_index == 0 else (1 if channels_index == 1 else 2)

        video_bitrate = None
        crf = None
        width = None
        height = None
        frame_rate = None

        if is_video:
            vcodec = self._current_vcodec()
            use_crf = self.quality_mode_crf_radio.GetValue() and vcodec in CRF_SUPPORTED_VCODECS
            if use_crf:
                crf = self.crf_spin.GetValue()
            else:
                video_bitrate = self.video_bitrate_spin.GetValue() * 1000

            if self.resolution_choice.GetSelection() == 1:
                width = self.width_spin.GetValue()
                height = self.height_spin.GetValue()

            if self.frame_rate_choice.GetSelection() == 1:
                frame_rate = self.frame_rate_spin.GetValue()

        return {
            "audio_bitrate": audio_bitrate,
            "sample_rate": sample_rate,
            "channels": channels,
            "video_bitrate": video_bitrate,
            "crf": crf,
            "width": width,
            "height": height,
            "frame_rate": frame_rate,
        }

    def _on_start_conversion(self, event):
        if not self._input_paths:
            wx.MessageBox(
                self.tr.t("converter_error_no_files"),
                self.tr.t("converter_dialog_title"),
                wx.ICON_WARNING,
            )
            return

        if not self._output_folder:
            self._output_folder = get_default_converter_dir(self.tr)

        effective_output_folder = (
            os.path.join(self._output_folder, self._subfolder_name)
            if self._subfolder_name
            else self._output_folder
        )
        try:
            os.makedirs(effective_output_folder, exist_ok=True)
        except Exception:
            pass

        is_video = self._is_video_mode()
        target_ext = self.format_choice.GetStringSelection()

        if target_ext and not target_ext.startswith("."):
            target_ext = "." + target_ext.lower()
        elif target_ext:
            target_ext = target_ext.lower()

        params = self._get_conversion_params()

        if target_ext == ".ogg" and params.get("sample_rate") is None:
            params["sample_rate"] = 44100

        jobs = []
        for input_path in self._input_paths:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = _unique_output_path(
                os.path.join(effective_output_folder, base_name + target_ext)
            )
            job = {
                "input_path": input_path,
                "output_path": output_path,
                "target_ext": target_ext,
                "is_video": is_video,
            }
            job.update(params)
            jobs.append(job)

        self._is_converting = True
        self._last_announced_pct = -1
        self._set_controls_enabled(False)
        self.progress_gauge.SetValue(0)
        self.progress_label.SetLabel(
            self.tr.t("converter_progress_starting",
                      files=count_phrase(self.tr, "count_files", len(jobs)))
        )
        self.announcer.announce(self.tr.t("converter_announce_start",
                                          files=count_phrase(self.tr, "count_files", len(jobs))))

        self._converter = BatchConverter(
            on_file_progress=self._on_file_progress,
            on_file_done=self._on_file_done,
            on_batch_done=self._on_batch_done,
        )
        self._converter.start(jobs)

    def _on_cancel_conversion(self, event):
        if self._converter is not None:
            self._converter.cancel()
        self.cancel_button.Disable()

    def _set_controls_enabled(self, enabled: bool):
        self.convert_button.Enable(enabled)
        self.cancel_button.Enable(not enabled)
        for control in (
            self.files_listbox,
            self.media_type_radio,
            self.format_choice,
            self.audio_bitrate_choice,
            self.sample_rate_choice,
            self.channels_choice,
            self.quality_mode_bitrate_radio,
            self.quality_mode_crf_radio,
            self.video_bitrate_spin,
            self.crf_spin,
            self.resolution_choice,
            self.width_spin,
            self.height_spin,
            self.frame_rate_choice,
            self.frame_rate_spin,
        ):
            control.Enable(enabled)
        if enabled:
            self._refresh_quality_mode_availability()

    def _on_file_progress(self, index, total, filename, fraction):
        wx.CallAfter(self._apply_file_progress, index, total, filename, fraction)

    def _apply_file_progress(self, index, total, filename, fraction):
        pct = int(fraction * 100)
        self.progress_gauge.SetValue(pct)
        self.progress_label.SetLabel(
            self.tr.t(
                "converter_progress_running",
                index=index,
                total=total,
                filename=filename,
                percent=pct,
            )
        )

        if pct > 0 and pct % 15 == 0 and pct != self._last_announced_pct:
            self._last_announced_pct = pct
            self.announcer.announce(f"{pct}%")

    def _on_file_done(self, index, total, filename, success, error_message):
        wx.CallAfter(self._apply_file_done, index, total, filename, success, error_message)

    def _apply_file_done(self, index, total, filename, success, error_message):
        self._last_announced_pct = -1
        if success:
            self.announcer.announce(
                self.tr.t("converter_announce_file_done", index=index, total=total, filename=filename)
            )
        else:
            self.announcer.announce(
                self.tr.t(
                    "converter_announce_file_failed",
                    filename=filename,
                    error=error_message or "",
                )
            )

    def _on_batch_done(self, succeeded, failed, cancelled):
        wx.CallAfter(self._apply_batch_done, succeeded, failed, cancelled)

    def _apply_batch_done(self, succeeded, failed, cancelled):
        self._is_converting = False
        self._set_controls_enabled(True)
        self.cancel_button.Disable()

        if cancelled:
            summary = self.tr.t("converter_announce_batch_cancelled",
                                succeeded_files=count_phrase(self.tr, "count_files", succeeded))
        else:
            summary = self.tr.t(
                "converter_announce_batch_done",
                succeeded_files=count_phrase(self.tr, "count_files", succeeded),
                failed_files=count_phrase(self.tr, "count_files", failed),
            )
            if self.settings is None or self.settings.get_enable_completion_sound():
                if failed and not succeeded:
                    play_error_chime()
                else:
                    play_completion_chime()

        self.progress_label.SetLabel(summary)
        self.announcer.announce(summary)

    def _on_close(self, event):
        if self._is_converting:
            dlg = wx.MessageDialog(
                self,
                self.tr.t("msg_confirm_cancel_conversion"),
                self.tr.t("title_warning") if "title_warning" in getattr(self.tr, "lang", "") else "تنبيه",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
            )

            result = dlg.ShowModal()
            dlg.Destroy()

            if result != wx.ID_YES:
                event.Veto()
                return

            if self._converter is not None:
                self._converter.cancel()

        self.Destroy()