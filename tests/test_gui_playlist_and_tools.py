# -*- coding: utf-8 -*-
"""
اختبارات نافذة قائمة التشغيل، والمعادل الصوتي، ومؤقت النوم، وخانة الوقت.
"""

import pytest

wx = pytest.importorskip("wx")

from core import equalizer
from core.time_input import TimeParseError, format_time_for_input, format_time_precise, parse_time


# ---------------------------------------------------------------- قائمة التشغيل

def _list_key(keycode, alt=False):
    event = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    event.SetKeyCode(keycode)
    event.SetAltDown(alt)
    return event


@pytest.fixture
def playlist_dialog(main_window, tmp_path):
    from gui.playlist_mixin import PlaylistDialog

    paths = []
    for name in ("a.mp3", "b.mp3", "c.mp3"):
        path = tmp_path / name
        path.write_bytes(b"")
        paths.append(str(path))
    main_window.playlist.add(paths)
    main_window.playlist.select(1)
    dialog = PlaylistDialog(main_window)
    ended = []
    dialog.EndModal = ended.append
    dialog.ended = ended
    dialog.paths = paths
    yield dialog
    dialog.Destroy()


def test_playlist_lists_entries_and_marks_the_current(playlist_dialog):
    tr = playlist_dialog.tr
    assert playlist_dialog.list.GetStrings() == ["a.mp3", tr.t("pl_item_current", name="b.mp3"), "c.mp3"]
    assert playlist_dialog.list.GetSelection() == 1


def test_playlist_delete_removes_and_says_what(playlist_dialog):
    main = playlist_dialog.main
    playlist_dialog.list.SetSelection(0)
    playlist_dialog._on_list_key(_list_key(wx.WXK_DELETE))
    assert [e.rsplit("\\", 1)[-1] for e in main.playlist.entries] == ["b.mp3", "c.mp3"]
    assert main.announcer.last() == playlist_dialog.tr.t("pl_announce_removed", name="a.mp3")


def test_playlist_alt_arrows_move_and_say_the_new_place(playlist_dialog):
    main = playlist_dialog.main
    playlist_dialog.list.SetSelection(0)
    playlist_dialog._on_list_key(_list_key(wx.WXK_DOWN, alt=True))
    assert main.playlist.entries[1] == playlist_dialog.paths[0]
    assert main.announcer.last() == playlist_dialog.tr.t("pl_announce_moved", name="a.mp3", index=2, total=3)
    playlist_dialog.list.SetSelection(0)
    before = list(main.playlist.entries)
    playlist_dialog._on_list_key(_list_key(wx.WXK_UP, alt=True))   # الأول لا يصعد
    assert main.playlist.entries == before


def test_playlist_enter_plays_and_escape_closes(playlist_dialog):
    playlist_dialog.list.SetSelection(2)
    playlist_dialog._on_list_key(_list_key(wx.WXK_RETURN))
    assert playlist_dialog.play_requested == 2
    assert playlist_dialog.ended == [wx.ID_OK]
    esc = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    esc.SetKeyCode(wx.WXK_ESCAPE)
    playlist_dialog._on_char_hook(esc)
    assert playlist_dialog.ended[-1] == wx.ID_CANCEL


def test_playlist_ctrl_s_and_ctrl_o(playlist_dialog, monkeypatch):
    calls = []
    monkeypatch.setattr(playlist_dialog.main, "_save_playlist_as", lambda parent: calls.append("save"))
    monkeypatch.setattr(playlist_dialog.main, "_ask_playlist_file", lambda parent: calls.append("open"))
    for key in ("S", "O"):
        event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        event.SetKeyCode(ord(key))
        event.SetControlDown(True)
        playlist_dialog._on_char_hook(event)
    assert calls == ["save", "open"]


def test_playlist_buttons_follow_the_selection(playlist_dialog):
    buttons = playlist_dialog.buttons
    playlist_dialog.list.SetSelection(0)
    playlist_dialog._refresh_buttons()
    assert not buttons["pl_btn_up"].IsEnabled() and buttons["pl_btn_down"].IsEnabled()
    playlist_dialog.list.SetSelection(2)
    playlist_dialog._refresh_buttons()
    assert buttons["pl_btn_up"].IsEnabled() and not buttons["pl_btn_down"].IsEnabled()


# ---------------------------------------------------------------- المعادل

@pytest.fixture
def eq_dialog(wx_app):
    from gui.equalizer_mixin import EqualizerDialog
    from i18n.strings import Translator

    previews = []
    presets = lambda mode: (2.0, [float(i) for i in range(equalizer.BAND_COUNT)])
    dialog = EqualizerDialog(None, Translator("ar"), "rock", None, presets, previews.append)
    dialog.previews = previews
    yield dialog
    dialog.Destroy()


def test_equalizer_opens_on_the_current_preset_and_previews_it(eq_dialog):
    assert eq_dialog.mode == "rock"
    assert eq_dialog.previews[-1] == (2.0, [float(i) for i in range(equalizer.BAND_COUNT)])
    assert eq_dialog.band_sliders[3].GetValue() == 3


def test_moving_a_band_makes_the_preset_custom(eq_dialog):
    slider = eq_dialog.band_sliders[0]
    slider.SetValue(6)
    event = wx.CommandEvent(wx.wxEVT_SLIDER)
    event.SetEventObject(slider)
    eq_dialog._on_slider(event)
    assert eq_dialog.mode == equalizer.MODE_CUSTOM
    preamp, bands = eq_dialog.custom_values()
    assert bands[0] == 6.0
    assert eq_dialog.previews[-1] == eq_dialog.custom_values()


def test_off_disables_the_sliders_and_reset_goes_flat(eq_dialog):
    eq_dialog._select_mode(equalizer.MODE_OFF)
    assert not eq_dialog.band_sliders[0].IsEnabled()
    assert eq_dialog.previews[-1] is None
    eq_dialog._on_reset(None)
    assert eq_dialog.mode == "flat"
    assert eq_dialog.band_sliders[0].IsEnabled()


# ---------------------------------------------------------------- مؤقت النوم

@pytest.fixture
def sleep_choice(monkeypatch):
    """يستبدل نافذة مؤقت النوم بإجابة جاهزة."""
    import gui.sleep_timer_mixin as module

    answer = {"minutes": 15, "at_end": False, "action": ("pause", 0)}

    class FakeSleepDialog:
        def __init__(self, *args, **kwargs):
            pass

        def ShowModal(self):
            return wx.ID_OK

        def get_minutes(self):
            return answer["minutes"]

        def at_end_of_file(self):
            return answer["at_end"]

        def get_action_key(self):
            return answer["action"][0]

        def get_action_idx(self):
            return answer["action"][1]

        def Destroy(self):
            pass

    monkeypatch.setattr(module, "SleepTimerDialog", FakeSleepDialog)
    return answer


def test_sleep_timer_set_and_cancel(main_window, sleep_choice):
    tr = main_window.tr
    main_window._on_sleep_timer(None)
    assert main_window._sleep_timer.IsRunning()
    assert main_window.sleep_timer_badge.IsShown()
    assert main_window.settings.get_sleep_timer_last_minutes() == 15
    assert main_window.announcer.last() == tr.t("announce_sleep_timer_set", duration="15 دقيقة")

    sleep_choice["minutes"] = 0
    main_window._on_sleep_timer(None)
    assert not main_window._sleep_timer.IsRunning()
    assert not main_window.sleep_timer_badge.IsShown()
    assert main_window.announcer.last() == tr.t("announce_sleep_timer_cancelled")


def test_sleep_timer_firing_pauses_playback(main_window, sleep_choice):
    main_window._on_sleep_timer(None)
    main_window.engine.play()
    main_window._on_sleep_timer_fired(None)
    assert main_window.engine.state == "paused"
    assert not main_window.sleep_timer_badge.IsShown()


def test_sleep_at_end_of_file_pauses_instead_of_moving_on(main_window, sleep_choice, monkeypatch):
    sleep_choice["at_end"] = True
    main_window._on_sleep_timer(None)
    moved = []
    monkeypatch.setattr(main_window, "_on_next", lambda event: moved.append(True))
    main_window.settings.set_on_playback_ended_action("next_file")
    main_window.engine.play()
    main_window._handle_playback_ended()
    assert main_window.engine.state == "paused"
    assert moved == []
    assert main_window.announcer.last() == main_window.tr.t("announce_sleep_timer_fired")


# ---------------------------------------------------------------- خانة الوقت (Ctrl+G والمحرر)

@pytest.mark.parametrize("text, seconds", [
    ("90", 90), ("1:30", 90), ("1:02:03", 3723), ("1:30.5", 90.5), (" 2:05 ", 125),
    ("١:٣٠", 90), ("1٫30", 90), ("0:00", 0), (":30", 30),
])
def test_time_input_accepts_what_people_type(text, seconds):
    assert parse_time(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", ["", "abc", "1:60", "1:61:00", "1:2:3:4", "1.5:30", None])
def test_time_input_refuses_what_it_cannot_understand(text):
    with pytest.raises(TimeParseError):
        parse_time(text)


def test_time_is_shown_the_way_it_is_typed():
    assert format_time_for_input(90) == "1:30"
    assert format_time_for_input(3723) == "1:02:03"
    assert format_time_precise(90.5) == "1:30.5"
    assert format_time_precise(90) == "1:30"
