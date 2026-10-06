# -*- coding: utf-8 -*-
"""
اختبارات النافذة الرئيسية: الاختصارات، والإعلانات، والتقديم، والصوت،
والسرعة، والعلامات، والمعادل، والتنقل بين الملفات.

النافذة حقيقية بمحرك وهمي ومعلن يسجّل ما يُقال (شوف tests/gui_support.py).
"""

import pytest

wx = pytest.importorskip("wx")

from gui.format_utils import format_time
from tests.gui_support import key_event, pump

N, C, S, A = wx.ACCEL_NORMAL, wx.ACCEL_CTRL, wx.ACCEL_SHIFT, wx.ACCEL_ALT

# (المفاتيح المساعدة، المفتاح) -> (الدالة، معاملاتها): كما في دليل الاختصارات
EXPECTED_SHORTCUTS = {
    (N, wx.WXK_UP): ("_volume_relative", (5,)),
    (N, wx.WXK_DOWN): ("_volume_relative", (-5,)),
    (C, wx.WXK_UP): ("_volume_relative", (20,)),
    (C, wx.WXK_DOWN): ("_volume_relative", (-20,)),
    (N, ord("M")): ("_on_toggle_mute", ()),
    (C, wx.WXK_SPACE): ("_on_stop", ()),
    (N, ord("R")): ("_on_announce_remaining_time", ()),
    (N, ord("E")): ("_on_announce_duration", ()),
    (N, ord("T")): ("_on_announce_time_status", ()),
    (N, ord("N")): ("_on_announce_stream_title", ()),
    (N, ord("Q")): ("_cycle_equalizer", (1,)),
    (S, ord("Q")): ("_cycle_equalizer", (-1,)),
    (C, ord("E")): ("_on_equalizer", ()),
    (C, ord("U")): ("_on_open_url", ()),
    (C, ord("L")): ("_on_playlist_dialog", ()),
    (C, ord("S")): ("_on_save_playlist", ()),
    (C | S, ord("R")): ("_on_recorder", ()),
    (C, ord("R")): ("_on_start_recording_shortcut", ()),
    (C | S, ord("X")): ("_on_media_editor", ()),
    (C | S, ord("P")): ("_on_options", ()),
    (C | A, ord("A")): ("_on_toggle_accessibility_shortcut", ()),
    (C | S, ord("H")): ("_on_export_shortcuts_doc", ()),
    (C | S, ord("D")): ("_on_export_diagnostics", ()),
    (N, wx.WXK_PAGEDOWN): ("_on_next", ()),
    (N, wx.WXK_PAGEUP): ("_on_previous", ()),
    **{(N, getattr(wx, f"WXK_NUMPAD{digit}")): ("_seek_to_percent", (digit * 10,)) for digit in range(1, 10)},
    (N, wx.WXK_NUMPAD0): ("_seek_to_start", ()),
    (N, wx.WXK_HOME): ("_seek_to_start", ()),
    (N, wx.WXK_END): ("_seek_to_near_end", ()),
    (A, wx.WXK_UP): ("_change_speed", (0.25,)),
    (A, wx.WXK_DOWN): ("_change_speed", (-0.25,)),
    (A, wx.WXK_NUMPAD0): ("_reset_speed", ()),
    (C, ord("G")): ("_on_go_to_time", ()),
    (C | A, ord("B")): ("_rename_bookmark", ()),
    (C, ord("B")): ("_add_bookmark", ()),
    (N, wx.WXK_F2): ("_jump_bookmark", ((), {"forward": True})),
    (S, wx.WXK_F2): ("_jump_bookmark", ((), {"forward": False})),
    (C | S, ord("B")): ("_clear_bookmarks", ()),
    (N, wx.WXK_F11): ("_on_toggle_fullscreen", ()),
    (N, wx.WXK_ESCAPE): ("_on_escape_exit_fullscreen", ()),
}


def _capture_shortcuts(window, monkeypatch):
    """
    يعيد بناء جدول الاختصارات مع تسجيل ما يربطه كل مفتاح.

    كل دالة هدف تُستبدل بمسجّل قبل البناء (بعض الروابط تحفظ الدالة نفسها
    وقت الربط)، ثم يُشغَّل رابط كل مفتاح ويُرى أي دالة نادى وبأي معاملات.
    """
    calls = []
    for name in {name for name, _args in EXPECTED_SHORTCUTS.values()}:
        def recorder(*args, _name=name, **kwargs):
            args = tuple(a for a in args if not isinstance(a, wx.Event) and a is not None)
            calls.append((_name, args, kwargs))
        monkeypatch.setattr(window, name, recorder)

    handlers = {}
    monkeypatch.setattr(window, "Bind", lambda event_type, handler, id=None, **kw: handlers.__setitem__(int(id), handler))
    tables = []
    monkeypatch.setattr(wx, "AcceleratorTable", lambda entries: entries)
    monkeypatch.setattr(window, "SetAcceleratorTable", tables.append)
    window._bind_shortcuts()

    bound = []
    for entry in tables[-1]:
        del calls[:]
        handlers[entry.GetCommand()](None)
        name, args, kwargs = calls[0]
        bound.append(((entry.GetFlags(), entry.GetKeyCode()), (name, args, kwargs)))
    return bound


def test_every_shortcut_runs_its_action(main_window, monkeypatch):
    bound = _capture_shortcuts(main_window, monkeypatch)
    actual = dict(bound)
    for combo, (name, args) in EXPECTED_SHORTCUTS.items():
        expected_args, expected_kwargs = args if (args and isinstance(args[0], tuple)) else (args, {})
        assert combo in actual, f"اختصار مفقود: {combo} -> {name}"
        assert actual[combo] == (name, expected_args, expected_kwargs), combo
    # لا اختصار مكرر ولا اختصار غير موثّق
    assert len(bound) == len(actual) == len(EXPECTED_SHORTCUTS)


def test_ctrl_alt_b_is_matched_before_ctrl_b(main_window, monkeypatch):
    """جدول المسرّعات يأخذ أول تطابق: Ctrl+B قبلها كان سيبتلع Ctrl+Alt+B."""
    combos = [combo for combo, _target in _capture_shortcuts(main_window, monkeypatch)]
    assert combos.index((C | A, ord("B"))) < combos.index((C, ord("B")))


def test_page_keys_follow_the_folder_navigation_option(main_window, monkeypatch):
    main_window.settings.set_enable_folder_navigation(False)
    combos = [combo for combo, _target in _capture_shortcuts(main_window, monkeypatch)]
    assert (N, wx.WXK_PAGEDOWN) not in combos and (N, wx.WXK_PAGEUP) not in combos


# ---------------------------------------------------------------- الأسهم والمسافة

@pytest.fixture
def seek_calls(main_window, monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "_seek_relative", lambda delta: calls.append(("relative", delta)))
    monkeypatch.setattr(main_window, "_start_hold_seek", lambda key, delta: calls.append(("hold", key, delta)))
    return calls


@pytest.mark.parametrize("mods, kind", [
    ({"ctrl": True}, "ctrl"), ({"shift": True}, "shift"), ({"alt": True}, "alt"),
    ({"ctrl": True, "shift": True}, "ctrl_shift"),
])
@pytest.mark.parametrize("key, sign", [(wx.WXK_RIGHT, 1), (wx.WXK_LEFT, -1)])
def test_arrow_with_modifier_seeks_the_amount_from_options(main_window, seek_calls, mods, kind, key, sign):
    main_window.settings.set_seek_step(kind, main_window.settings.SEEK_STEP_LIMITS[kind][0] + 60)
    main_window._on_char_hook(key_event(key, **mods))
    assert seek_calls == [("relative", sign * main_window.settings.get_seek_step(kind))]


def test_plain_arrow_starts_hold_seek_with_the_normal_amount(main_window, seek_calls):
    main_window.settings.set_seek_step("normal", 5)
    main_window._on_char_hook(key_event(wx.WXK_LEFT))
    assert seek_calls == [("hold", wx.WXK_LEFT, -5)]


def test_space_and_ctrl_space(main_window, monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "_on_play_pause", lambda e: calls.append("play_pause"))
    monkeypatch.setattr(main_window, "_on_stop", lambda e: calls.append("stop"))
    main_window._on_char_hook(key_event(wx.WXK_SPACE))
    main_window._on_char_hook(key_event(wx.WXK_SPACE, ctrl=True))
    assert calls == ["play_pause", "stop"]


def test_tab_is_swallowed_and_other_keys_pass_through(main_window):
    tab = key_event(wx.WXK_TAB)
    main_window._on_char_hook(tab)
    assert not tab.GetSkipped()
    other = key_event(ord("X"))
    main_window._on_char_hook(other)
    assert other.GetSkipped()


# ---------------------------------------------------------------- إعلانات الوقت

@pytest.fixture
def playing(main_window):
    main_window.engine.duration = 3600.0
    main_window.engine.position = 90.0
    return main_window


def _said_after(window, action):
    del window.announcer.said[:]
    action()
    pump(0.3)
    return list(window.announcer.said)


@pytest.mark.parametrize("handler, key, values", [
    ("_on_announce_time_status", "announce_time_status", {"current": format_time(90)}),
    ("_on_announce_remaining_time", "announce_remaining_only", {"remaining": format_time(3510)}),
    ("_on_announce_duration", "announce_duration", {"total": format_time(3600)}),
])
def test_time_keys_say_one_thing_each(playing, handler, key, values):
    """T الحالي وحده، وR المتبقي، وE المدة الكاملة."""
    said = _said_after(playing, lambda: getattr(playing, handler)(None))
    assert said == [playing.tr.t(key, **values)]


def test_rapid_time_keys_speak_only_the_last(playing):
    """ضغطات متتالية لا تتراكم في قارئ الشاشة: يُقال آخرها فقط."""
    def press_three():
        playing._on_announce_time_status(None)
        playing._on_announce_duration(None)
        playing._on_announce_remaining_time(None)
    assert _said_after(playing, press_three) == [playing.tr.t("announce_remaining_only", remaining=format_time(3510))]


def test_turned_off_announcement_stays_silent(playing):
    playing.settings.set_announce_time_status(False)
    assert _said_after(playing, lambda: playing._on_announce_time_status(None)) == []


def test_master_switch_silences_everything_but_says_its_own_state(playing):
    tr = playing.tr
    assert _said_after(playing, lambda: playing._on_toggle_accessibility_shortcut(None)) == [
        tr.t("announce_accessibility_disabled")]
    assert _said_after(playing, lambda: playing._on_announce_remaining_time(None)) == []
    assert _said_after(playing, lambda: playing._on_toggle_accessibility_shortcut(None)) == [
        tr.t("announce_accessibility_enabled")]


# ---------------------------------------------------------------- التقديم

def test_relative_seek_stays_inside_the_file(playing):
    playing._seek_relative(-600)
    assert playing.engine.position == 0
    playing._seek_relative(99999)
    assert playing.engine.position == 3600


def test_small_jumps_are_quiet_when_a_minimum_is_set(playing):
    """أصغر قفزة يُعلَن بعدها الموضع: القفزات الأصغر صامتة، وأرقام لوحة الأرقام تُعلَن دائمًا."""
    playing.settings.set_announce_seek_min_seconds(60)
    assert _said_after(playing, lambda: playing._seek_relative(10)) == []
    assert _said_after(playing, lambda: playing._seek_relative(300)) == [
        playing.tr.t("announce_seek_position", time=format_time(400))]
    assert _said_after(playing, lambda: playing._seek_to_percent(50)) == [
        playing.tr.t("announce_seek_position", time=format_time(1800))]


def test_numpad_end_and_home(playing):
    playing._seek_to_percent(30)
    assert playing.engine.position == pytest.approx(1080)
    playing._seek_to_near_end()
    assert playing.engine.position == pytest.approx(3595)
    playing._seek_to_start()
    assert playing.engine.position == 0


def test_jump_pressed_while_loading_runs_once_duration_is_known(main_window):
    """End أثناء تحميل الملف لا يضيع: يُنفَّذ حين تُعرف المدة."""
    main_window._is_loading_file = True
    main_window.engine.duration = 0
    main_window._seek_to_near_end()
    assert main_window.engine.seeks == []
    main_window._is_loading_file = False
    main_window.engine.duration = 200
    main_window._run_pending_seek()
    assert main_window.engine.position == pytest.approx(195)


# ---------------------------------------------------------------- الصوت والسرعة

def test_volume_steps_clamp_and_are_saved(main_window):
    main_window.volume_slider.SetValue(97)
    said = _said_after(main_window, lambda: main_window._volume_relative(5))
    assert main_window.volume_slider.GetValue() == 100
    assert main_window.engine.volume == pytest.approx(1.0)
    assert main_window.settings.get_volume() == 100
    assert said == [main_window.tr.t("announce_volume", percent=100)]
    main_window.volume_slider.SetValue(3)
    main_window._volume_relative(-20)
    assert main_window.volume_slider.GetValue() == 0


def test_mute_toggles_and_says_so(main_window):
    tr = main_window.tr
    assert _said_after(main_window, lambda: main_window._on_toggle_mute(None)) == [tr.t("announce_muted")]
    assert main_window.engine.is_muted
    assert _said_after(main_window, lambda: main_window._on_toggle_mute(None)) == [tr.t("announce_unmuted")]
    assert not main_window.engine.is_muted


def test_speed_is_clamped_reset_and_remembered_per_file(main_window, tmp_path):
    path = str(tmp_path / "book.mp3")
    main_window._current_file_path = path
    for _ in range(6):
        main_window._change_speed(0.25)
    assert main_window.engine.speed == 2.0
    assert main_window.settings.get_file_speed(path) == 2.0
    main_window._reset_speed()
    assert main_window.engine.speed == 1.0
    assert main_window.settings.get_file_speed(path) == 1.0


# ---------------------------------------------------------------- العلامات المرجعية

def test_bookmarks_add_jump_wrap_and_clear(playing, tmp_path):
    tr = playing.tr
    playing._current_file_path = str(tmp_path / "lecture.mp3")
    for position in (600, 60):
        playing.engine.position = position
        playing._add_bookmark()
    playing.engine.position = 0
    playing._jump_bookmark(forward=True)
    assert playing.engine.position == 60
    playing._jump_bookmark(forward=True)
    assert playing.engine.position == 600
    playing._jump_bookmark(forward=True)
    assert playing.engine.position == 60          # يرجع للأولى بعد الأخيرة
    playing._jump_bookmark(forward=False)
    assert playing.engine.position == 600         # ومن الأولى للخلف إلى الأخيرة

    playing.engine.position = 60
    assert _said_after(playing, playing._add_bookmark) == [tr.t("announce_bookmark_duplicate")]

    playing.settings.rename_bookmark(playing._current_file_path, 600, "الفصل الثاني")
    playing.engine.position = 100
    said = _said_after(playing, lambda: playing._jump_bookmark(forward=True))
    assert said == [tr.t("announce_bookmark_jumped_named", time=format_time(600), name="الفصل الثاني")]

    playing._clear_bookmarks()
    assert _said_after(playing, lambda: playing._jump_bookmark(forward=True)) == [tr.t("announce_bookmark_none")]


def test_bookmark_keys_do_nothing_without_a_file(main_window):
    assert _said_after(main_window, main_window._add_bookmark) == []
    assert main_window.settings.get_bookmarks("") == []


# ---------------------------------------------------------------- المعادل

def test_equalizer_keys_cycle_presets_and_back(main_window):
    start = main_window.settings.get_equalizer_mode()
    main_window._cycle_equalizer(1)
    moved = main_window.settings.get_equalizer_mode()
    assert moved != start
    assert main_window.announcer.said, "اسم النمط يُنطق"
    main_window._cycle_equalizer(-1)
    assert main_window.settings.get_equalizer_mode() == start


# ---------------------------------------------------------------- التنقل بين الملفات

def test_next_and_previous_move_through_the_folder(main_window, monkeypatch, tmp_path):
    files = []
    for name in ("01.mp3", "02.mp3", "03.mp3"):
        path = tmp_path / name
        path.write_bytes(b"")
        files.append(str(path))
    main_window.playlist.load_folder_of(files[1])
    opened = []
    monkeypatch.setattr(main_window, "_load_and_play", opened.append)

    main_window._on_next(None)
    assert opened == [files[2]]
    said = _said_after(main_window, lambda: main_window._on_next(None))
    assert said == [main_window.tr.t("announce_no_next_file")]
    assert opened == [files[2]]


def test_window_title_and_english_interface(make_main_window):
    window = make_main_window("en")
    assert window.tr.lang == "en"
    assert window.tr.t("app_title") in window.GetTitle()
    assert window.GetLayoutDirection() != wx.Layout_RightToLeft


def test_every_shortcut_written_in_the_menus_is_understood(main_window):
    """
    نص الاختصار بعد Tab في عنصر القائمة يجب أن يفهمه wx، وإلا لا يظهر بجانب
    العنصر. «Alt+Numpad 0» لم يكن مفهومًا (الصحيح Alt+KP_0).
    """
    def items(menu):
        for item in menu.GetMenuItems():
            if item.GetSubMenu():
                yield from items(item.GetSubMenu())
            else:
                yield item

    unknown = []
    menubar = main_window.GetMenuBar()
    for index in range(menubar.GetMenuCount()):
        for item in items(menubar.GetMenu(index)):
            if "\t" in item.GetItemLabel() and item.GetAccel() is None:
                unknown.append(item.GetItemLabel())
    assert unknown == []
