# -*- coding: utf-8 -*-
"""اختبارات لتنسيق الوقت (gui/format_utils.py)."""

import pytest

from gui.format_utils import format_time


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0:00"),
        (5, "0:05"),
        (59, "0:59"),
        (60, "1:00"),
        (125, "2:05"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3665, "1:01:05"),
        (-5, "0:00"),  # قيم سالبة (لو حصل خطأ حسابي) لازم تتقص لصفر مش تكسر
    ],
)
def test_format_time(seconds, expected):
    assert format_time(seconds) == expected
