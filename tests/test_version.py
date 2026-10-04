# -*- coding: utf-8 -*-
"""رقم الإصدار لازم يكون واحد في البرنامج وفي المثبّت."""

import os
import re

from core.version import APP_VERSION

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_app_version_is_three_numeric_parts():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)


def test_installer_version_matches_app_version():
    """Inno Setup ما بيقراش من بايثون، فرقم المثبّت مكتوب بإيده - الاختبار
    ده بيمسك نسيانه وقت تحديث core/version.py."""
    with open(os.path.join(_ROOT, "omnya_player_installer.iss"), encoding="utf-8-sig") as f:
        match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', f.read())
    assert match, "MyAppVersion مش موجود في ملف المثبّت"
    assert match.group(1) == APP_VERSION
