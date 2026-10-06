# -*- coding: utf-8 -*-
"""
اختبارات نافذة محرر الوسائط: الأوقات، والمقاطع، والعلامات، والاختصارات
الشبحية، وإعلان التقدم، وقص حقيقي لملف من البداية للنهاية.
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
def media_file(tmp_path):
    path = str(tmp_path / "talk.m4a")
    write_sample_media(path, seconds=4, with_video=False)
    return path


@pytest.fixture
def make_editor(wx_app, app_data, monkeypatch):
    import gui.media_editor_dialog as module
    from gui.media_editor_dialog import MediaEditorDialog

    errors = []
    monkeypatch.setattr(wx, "MessageBox", lambda *args, **kwargs: errors.append(args[0]))
    monkeypatch.setattr(module, "play_completion_chime", lambda: None)
    monkeypatch.setattr(module, "play_error_chime", lambda: None)
    editors = []

    def make(bookmarks=(), position=None, **kwargs):
        editor = MediaEditorDialog(
            Translator("ar"), announcer=FakeAnnouncer(), settings=Settings(),
            bookmarks_provider=lambda path: list(bookmarks),
            position_provider=(lambda: position) if position else None,
            **kwargs)
        editor.errors = errors
        editors.append(editor)
        return editor

    yield make
    for editor in editors:
        if editor:
            editor.Destroy()


def _said(editor):
    return editor.announcer.last()


def test_loading_a_file_fills_every_page(make_editor, media_file):
    editor = make_editor()
    editor.load_file(media_file)
    assert editor.split_file.path == media_file
    assert editor.segments_file.path == media_file
    assert editor.split_many_list.paths == [media_file]
    assert editor.merge_list.paths == [media_file]


def test_bad_time_is_refused_with_the_field_name(make_editor):
    editor = make_editor()
    editor.split_time.text.SetValue("1:75")
    assert editor.split_time.value() is None
    assert editor.errors[-1] == editor.tr.t("editor_err_time", field=editor.split_time.label)
    editor.split_time.text.SetValue("1:15.5")
    assert editor.split_time.value() == pytest.approx(75.5)


def test_current_position_comes_from_the_player_only_for_the_same_file(make_editor, media_file, tmp_path):
    editor = make_editor(position=(media_file, 42.5))
    editor.load_file(media_file)
    editor.notebook.SetSelection(0)
    editor.split_time._on_position(None)
    assert editor.split_time.text.GetValue() == "0:42.5"

    other = make_editor(position=(str(tmp_path / "another.mp3"), 10))
    other.load_file(media_file)
    other.notebook.SetSelection(0)
    other.split_time._on_position(None)
    assert other.split_time.text.GetValue() == ""
    assert _said(other) == other.tr.t("editor_no_position")


def test_segments_add_remove_and_move(make_editor, media_file):
    editor = make_editor()
    editor.load_file(media_file)
    for start, end in (("0:01", "0:02"), ("0:03", "0:04")):
        editor.segment_start.text.SetValue(start)
        editor.segment_end.text.SetValue(end)
        editor._on_add_segment(None)
    assert editor._segments == [(1, 2), (3, 4)]
    assert editor.segment_start.text.GetValue() == ""      # الخانتان تفرغان للمقطع التالي

    editor.segment_start.text.SetValue("0:05")
    editor.segment_end.text.SetValue("0:04")
    editor._on_add_segment(None)
    assert editor.errors[-1] == editor.tr.t("editor_err_segment")
    assert len(editor._segments) == 2

    editor.segments_listbox.SetSelection(1)
    editor._move_segment(-1)
    assert editor._segments == [(3, 4), (1, 2)]
    editor._on_remove_segment(None)
    assert editor._segments == [(1, 2)]


def test_segments_from_bookmarks_pair_them_and_mention_the_leftover(make_editor, media_file):
    marks = [(10, "مقدمة"), (20, ""), (30, ""), (40, ""), (50, "")]
    editor = make_editor(bookmarks=marks)
    editor.load_file(media_file)
    editor._on_segments_from_bookmarks(None)
    assert editor._segments == [(10, 20), (30, 40)]
    assert editor.tr.t("editor_bookmark_left_over", time="0:50") in _said(editor)


def test_segments_from_bookmarks_without_any(make_editor, media_file):
    editor = make_editor(bookmarks=[])
    editor.load_file(media_file)
    editor._on_segments_from_bookmarks(None)
    assert editor._segments == []
    assert editor.errors[-1] == editor.tr.t("editor_no_bookmarks")


def test_ghost_shortcuts_build_segments_while_listening(make_editor, media_file):
    editor = make_editor()
    tr = editor.tr
    assert editor.ghost_segment_end(media_file, 5).endswith(tr.t("ghost_need_start", keys=editor.hotkey_text("start")))
    assert tr.t("ghost_start_set", time="0:01") in editor.ghost_segment_start(media_file, 1)
    assert editor.ghost_segment_end(media_file, 0.5) == tr.t("ghost_end_before_start", start="0:01")
    editor.ghost_segment_end(media_file, 3)
    assert editor._segments == [(1, 3)]
    assert editor.ghost_status() == tr.t("ghost_status_segments", name="talk.m4a",
                                         segments=count_phrase(tr, "count_segments", 1))
    assert editor.ghost_undo_segment() == tr.t("ghost_segment_undone_last")
    assert editor.ghost_undo_segment() == tr.t("ghost_no_segments")


def test_ghost_add_to_lists_refuses_duplicates(make_editor, media_file):
    from gui.media_editor_dialog import PAGE_MERGE, PAGE_SPLIT_MANY
    editor = make_editor()
    tr = editor.tr
    assert editor.ghost_add_to_list(PAGE_MERGE, media_file) == tr.t(
        "ghost_added_to_merge", name="talk.m4a", count=1, files=count_phrase(tr, "count_files", 1))
    assert editor.ghost_add_to_list(PAGE_MERGE, media_file) == editor.tr.t("ghost_already_in_list", name="talk.m4a")
    editor.ghost_add_to_list(PAGE_SPLIT_MANY, media_file)
    assert editor.split_many_list.paths == [media_file]
    assert editor.ghost_cancel() == editor.tr.t("ghost_nothing_running")


def test_merge_needs_two_files(make_editor, media_file):
    from gui.media_editor_dialog import PAGE_MERGE
    editor = make_editor()
    editor.merge_list.add([media_file])
    editor.notebook.SetSelection(PAGE_MERGE)
    assert editor._collect_jobs() is None
    assert editor.errors[-1] == editor.tr.t("editor_err_merge_count")


def test_progress_is_announced_every_step_once(make_editor):
    editor = make_editor()
    editor.settings.set_editor_progress_step(25)
    editor._last_pct = -1
    for fraction in (0.1, 0.2, 0.3, 0.3, 0.55, 0.8, 0.99):
        editor._apply_progress(1, 1, fraction)
    assert [s for s in editor.announcer.said if s.endswith("%")] == ["30%", "55%", "80%"]


def test_hide_on_close_keeps_what_was_set(make_editor, media_file):
    editor = make_editor(hide_on_close=True)
    editor.ghost_segment_start(media_file, 1)
    editor.Show()
    editor.Close()
    assert editor and not editor.IsShown()
    assert editor._pending_start == 1


def test_split_a_real_file_from_start_to_finish(make_editor, media_file):
    """قص فعلي عبر النافذة: جزآن في مجلد «محرر الوسائط/صوت» ومدتاهما صحيحتان."""
    import av

    editor = make_editor()
    editor.load_file(media_file)
    editor.notebook.SetSelection(0)
    editor.split_time.text.SetValue("0:01.5")
    editor._on_start(None)
    for _ in range(100):
        pump(0.1)
        if editor._runner is not None and not editor._runner.is_running() and editor.start_button.IsEnabled():
            break
    assert _said(editor) == editor.tr.t("editor_done")
    folder = editor.settings.get_editor_output_folder(False)
    outputs = sorted(os.path.join(folder, name) for name in os.listdir(folder))
    assert len(outputs) == 2
    durations = []
    for path in outputs:
        with av.open(path) as container:
            durations.append(float(container.duration) / av.time_base)
    assert durations[0] == pytest.approx(1.5, abs=0.15)
    assert sum(durations) == pytest.approx(4.0, abs=0.2)
