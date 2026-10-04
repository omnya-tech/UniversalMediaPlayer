# -*- coding: utf-8 -*-
"""كل نص في الواجهة لازم يكون موجود باللغتين."""

from i18n.strings import STRINGS


def test_arabic_and_english_have_the_same_keys():
    arabic, english = set(STRINGS["ar"]), set(STRINGS["en"])
    assert sorted(arabic - english) == []
    assert sorted(english - arabic) == []
