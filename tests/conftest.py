# -*- coding: utf-8 -*-
"""إعدادات مشتركة لكل الاختبارات."""

import os
import tempfile

import pytest

# مجلد بيانات البرنامج (السجل والإعدادات) في مجلد مؤقت، وقبل أي استيراد من
# core: السجل يُفتح عند استيراد الوحدات. كانت الاختبارات تكتب في سجل
# المستخدم الحقيقي، فيختلط تشغيلها بتشغيله في التقرير التشخيصي
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="omnya_tests_")


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
