# -*- coding: utf-8 -*-
"""
نظام الترجمة الخاص بالواجهة.
النصوص نفسها في strings_ar.py وstrings_en.py.
"""

from i18n.strings_ar import AR
from i18n.strings_en import EN


class Translator:
    def __init__(self, lang="ar"):
        self.lang = lang if lang in STRINGS else "ar"

    def set_language(self, lang):
        if lang in STRINGS:
            self.lang = lang

    def t(self, key, **kwargs):
        lang_dict = STRINGS.get(self.lang, STRINGS["ar"])
        text = lang_dict.get(key, STRINGS["ar"].get(key, key))
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


STRINGS = {"ar": AR, "en": EN}
