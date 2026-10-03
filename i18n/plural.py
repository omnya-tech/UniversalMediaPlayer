# -*- coding: utf-8 -*-
"""
تمييز العدد في العربية.

العربية بتغيّر المعدود حسب العدد، مش زي الإنجليزي (ملف واحد / ملفان / خمسة
ملفات / أحد عشر ملفًا). النصوص دي بينطقها قارئ الشاشة، فالخطأ النحوي
مسموع مش مقروء بس - "تمت إضافة 3 ملف" وحشة في الأذن قبل العين.

الفئات هي نفس فئات CLDR للعربية، علشان أي مترجم يشتغل على البرنامج بعدين
يلاقي أسماء يعرفها:

    zero   0            لا ملفات
    one    1            ملف واحد
    two    2            ملفان
    few    n%100 = 3-10   {n} ملفات
    many   n%100 = 11-99  {n} ملفًا
    other  الباقي         {n} ملف        (100، 200، 1000...)
"""

PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")


def arabic_plural_category(count: int) -> str:
    """يرجع فئة تمييز العدد المناسبة للعدد المعطى."""
    try:
        number = abs(int(count))
    except (TypeError, ValueError):
        return "other"

    if number == 0:
        return "zero"
    if number == 1:
        return "one"
    if number == 2:
        return "two"

    remainder = number % 100
    if 3 <= remainder <= 10:
        return "few"
    if 11 <= remainder <= 99:
        return "many"
    return "other"


def count_phrase(tr, key_base: str, count: int, **kwargs) -> str:
    """
    يختار الصيغة الصحيحة من مجموعة مفاتيح مثل:
        count_files_zero / _one / _two / _few / _many / _other

    لو اللغة مش عربية، أو الفئة مش موجودة في ملف النصوص، بيقع على
    "{key_base}_other" اللي بيشتغل صح للإنجليزية كمان.
    """
    category = arabic_plural_category(count)
    full_key = f"{key_base}_{category}"
    text = tr.t(full_key, count=count, **kwargs)
    # المترجم يرجع المفتاح نفسه لما ما يلاقيهوش، فنقع على "_other"
    if text == full_key:
        text = tr.t(f"{key_base}_other", count=count, **kwargs)
    return text
