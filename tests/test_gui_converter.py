# -*- coding: utf-8 -*-
"""
اختبارات نافذة محول الصيغ: قائمة الملفات، والصيغ حسب النوع، ومعدل البت،
والخيارات المتقدمة، وإعلان التقدم، وتحويل حقيقي من البداية للنهاية.
"""

import os

import pytest

wx = pytest.importorskip("wx")

from core.settings import Settings
from i18n.plural import count_phrase
from i18n.strings import Translator
from tests.gui_support import FakeAnnouncer, pump
from tests.media_samples import write_sample_media


@pytest.fixture
def make_converter(wx_app, app_data, monkeypatch):
    import gui.converter_dialog as module

    boxes = []
    monkeypatch.setattr(wx, "MessageBox", lambda *args, **kwargs: boxes.append(args[0]))
    monkeypatch.setattr(module, "play_completion_chime", lambda: None)
    monkeypatch.setattr(module, "play_error_chime", lambda: None)
    dialogs = []

    def make(files=(), lang="ar"):
        dialog = module.ConverterDialog(None, Translator(lang), FakeAnnouncer(), settings=Settings(),
                                        initial_files=list(files) or None)
        dialog.boxes = boxes
        dialogs.append(dialog)
        return dialog

    yield make
    for dialog in dialogs:
        if dialog:
            if dialog._converter is not None:
                dialog._converter.cancel()
            dialog.Destroy()


@pytest.fixture
def sample(tmp_path):
    path = str(tmp_path / "song.m4a")
    write_sample_media(path, seconds=2, with_video=False)
    return path


def test_files_are_added_once_and_counted(make_converter, sample, tmp_path):
    dialog = make_converter()
    other = str(tmp_path / "other.m4a")
    write_sample_media(other, seconds=1, with_video=False)
    dialog.add_input_files([sample, other, sample])
    assert dialog._input_paths == [sample, other]
    assert dialog.files_listbox.GetStrings() == ["song.m4a", "other.m4a"]
    assert dialog.announcer.last() == dialog.tr.t(
        "converter_announce_files_added", files=count_phrase(dialog.tr, "count_files", 2))


def test_remove_selected_and_clear(make_converter, sample, tmp_path):
    other = str(tmp_path / "b.m4a")
    write_sample_media(other, seconds=1, with_video=False)
    dialog = make_converter([sample, other])
    dialog.files_listbox.SetSelection(0)
    dialog._on_remove_selected(None)
    assert dialog._input_paths == [other]
    dialog._on_clear_files(None)
    assert dialog._input_paths == [] and dialog.files_listbox.GetCount() == 0


def test_formats_follow_the_media_type(make_converter):
    dialog = make_converter()
    dialog.media_type_radio.SetSelection(0)
    dialog._on_media_type_change(None)
    audio = dialog.format_choice.GetStrings()
    assert ".mp3" in audio and ".mp4" not in audio
    dialog.media_type_radio.SetSelection(1)
    dialog._on_media_type_change(None)
    video = dialog.format_choice.GetStrings()
    assert ".mp4" in video and ".mp3" not in video


def test_lossless_audio_has_no_bitrate(make_converter):
    dialog = make_converter()
    dialog.media_type_radio.SetSelection(0)
    dialog._on_media_type_change(None)
    dialog.format_choice.SetStringSelection(".mp3")
    dialog._on_format_change(None)
    assert dialog.audio_bitrate_choice.IsShown() and dialog.audio_bitrate_choice.IsEnabled()
    dialog.format_choice.SetStringSelection(".flac")
    dialog._on_format_change(None)
    assert not (dialog.audio_bitrate_choice.IsShown() and dialog.audio_bitrate_choice.IsEnabled())
    assert dialog._get_conversion_params()["audio_bitrate"] == 0


def test_video_format_without_sound_hides_the_audio_options(make_converter):
    dialog = make_converter()
    dialog.media_type_radio.SetSelection(1)
    dialog._on_media_type_change(None)
    dialog.format_choice.SetStringSelection(".gif")
    dialog._on_format_change(None)
    assert dialog.audio_no_track_note.IsShown()
    dialog.format_choice.SetStringSelection(".mp4")
    dialog._on_format_change(None)
    assert not dialog.audio_no_track_note.IsShown()


def test_advanced_choices_reach_the_conversion(make_converter):
    dialog = make_converter()
    dialog.media_type_radio.SetSelection(1)
    dialog._on_media_type_change(None)
    dialog.format_choice.SetStringSelection(".mp4")
    dialog._on_format_change(None)
    dialog.channels_choice.SetSelection(1)
    dialog.resolution_choice.SetSelection(1)
    dialog.width_spin.SetValue(640)
    dialog.height_spin.SetValue(360)
    dialog.quality_mode_crf_radio.SetValue(True)
    dialog.crf_spin.SetValue(28)
    params = dialog._get_conversion_params()
    assert (params["channels"], params["width"], params["height"]) == (1, 640, 360)
    assert params["crf"] == 28 and params["video_bitrate"] is None
    dialog.quality_mode_bitrate_radio.SetValue(True)
    dialog.video_bitrate_spin.SetValue(1500)
    params = dialog._get_conversion_params()
    assert params["crf"] is None and params["video_bitrate"] == 1_500_000


def test_start_without_files_explains_why(make_converter):
    dialog = make_converter()
    dialog._on_start_conversion(None)
    assert dialog.boxes[-1] == dialog.tr.t("converter_error_no_files")
    assert dialog._converter is None


def test_progress_is_announced_at_every_step_even_when_values_jump(make_converter):
    """كل 15% يُعلَن مرة حتى لو قفز التقدم فوقها (14 ثم 16)؛ كان يُعلَن فقط عند 15 بالضبط."""
    dialog = make_converter()
    dialog._last_announced_pct = -1
    for fraction in (0.05, 0.14, 0.16, 0.2, 0.29, 0.31, 0.47, 0.47, 0.99):
        dialog._apply_file_progress(1, 1, "a.m4a", fraction)
    assert [s for s in dialog.announcer.said if s.endswith("%")] == ["16%", "31%", "47%", "99%"]


def test_convert_a_real_file_from_start_to_finish(make_converter, sample):
    import av

    dialog = make_converter([sample])
    dialog.media_type_radio.SetSelection(0)
    dialog._on_media_type_change(None)
    dialog.format_choice.SetStringSelection(".mp3")
    dialog._on_format_change(None)
    dialog._on_start_conversion(None)
    assert not dialog.convert_button.IsEnabled()
    for _ in range(150):
        pump(0.1)
        if not dialog._is_converting:
            break
    tr = dialog.tr
    assert dialog.announcer.last() == tr.t(
        "converter_announce_batch_done",
        succeeded_files=count_phrase(tr, "count_files", 1),
        failed_files=count_phrase(tr, "count_files", 0))
    assert dialog.convert_button.IsEnabled()
    output = os.path.join(dialog._output_folder, "song.mp3")
    with av.open(output) as container:
        assert float(container.duration) / av.time_base == pytest.approx(2.0, abs=0.2)
