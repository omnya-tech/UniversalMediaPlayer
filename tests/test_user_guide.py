# -*- coding: utf-8 -*-
"""اختبارات دليل المستخدم ودليل الاختصارات المصدَّر."""

from gui.user_guide import (
    _sections,
    build_shortcuts_text,
    build_user_guide_html,
    get_shortcuts_list,
)
from i18n.strings import Translator

_STEPS = {"normal": 10, "ctrl": 60, "shift": 300, "alt": 600, "ctrl_shift": 1800}


def test_arabic_and_english_guides_match_point_for_point():
    """النسختان بالمحتوى نفسه: الإنجليزية كانت قد صارت ملخصًا للعربية."""
    arabic = _sections("ar", _STEPS)
    english = _sections("en", _STEPS)
    assert [sid for sid, _t, _i in arabic] == [sid for sid, _t, _i in english]
    for (sid, _ta, items_ar), (_sid, _te, items_en) in zip(arabic, english):
        assert len(items_ar) == len(items_en), sid


def test_shortcut_lists_match_line_for_line():
    """كل اختصار في القائمتين، وفي المكان نفسه، والمفتاح بعد النقطتين."""
    arabic = get_shortcuts_list("ar")
    english = get_shortcuts_list("en")
    assert len(arabic) == len(english)
    for line_ar, line_en in zip(arabic, english):
        assert bool(line_ar) == bool(line_en)
        assert line_ar.startswith("===") == line_en.startswith("===")
        if line_ar and not line_ar.startswith("==="):
            assert ":" in line_ar and ":" in line_en


def test_export_shows_the_users_own_settings():
    """مقادير التقديم والاختصارات الشبحية كما ضبطها المستخدم."""
    for lang, seek_text in (("ar", "تقديم أو إرجاع 5 ثوانٍ"), ("en", "Seek 5 seconds")):
        text = build_shortcuts_text(
            Translator(lang),
            seek_steps={"normal": 5},
            ghost_hotkeys={"toggle": ("ctrl+alt", "G")},
        )
        assert seek_text in text
        assert "Ctrl + Alt + G" in text
        assert "Ctrl + Alt + Shift + G" not in text
        assert "1.5" in text.splitlines()[1]


def test_export_has_numbered_sections_and_one_line_per_shortcut():
    text = build_shortcuts_text(Translator("ar"))
    lines = text.splitlines()
    headings = [line for line in lines if line[:1].isdigit() and ". " in line]
    shortcuts = [line for line in lines if line.startswith("• ")]
    sections = sum(1 for line in get_shortcuts_list("ar") if line.startswith("==="))
    assert len(headings) == sections
    assert len(shortcuts) == sum(1 for line in get_shortcuts_list("ar")
                                 if line and not line.startswith("==="))
    # تحت كل عنوان خط بطوله
    for heading in headings:
        assert lines[lines.index(heading) + 1] == "-" * len(heading)


def test_guide_page_lists_every_section_in_its_table_of_contents():
    html = build_user_guide_html(Translator("ar"))
    for sid, _title, _items in _sections("ar", _STEPS):
        assert f'href="#{sid}"' in html
        assert f'id="{sid}"' in html
    # الاختصار المركّب من اليسار لليمين في الصفحة العربية
    assert '<span class="combo" dir="ltr"><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>X</kbd></span>' in html
