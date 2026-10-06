# -*- coding: utf-8 -*-
"""إعدادات مشتركة لكل الاختبارات."""

import pytest


@pytest.fixture(autouse=True)
def _documents_in_temp(tmp_path_factory, monkeypatch):
    """
    مجلد المستندات في مجلد مؤقت لكل اختبار.

    الإعدادات تصنع مجلدات الحفظ في المستندات أول ما تُطلب؛ اختبارات قديمة
    كانت تصنعها في مستندات المستخدم الحقيقية.
    """
    # مجلد مستقل لا داخل tmp_path: بعض الاختبارات تعدّ محتويات tmp_path
    documents = tmp_path_factory.mktemp("Documents")
    monkeypatch.setattr("core.settings.get_documents_dir", lambda: str(documents))
    return documents
