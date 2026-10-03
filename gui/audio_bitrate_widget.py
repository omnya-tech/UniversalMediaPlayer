# -*- coding: utf-8 -*-
"""
منطق مشترك لملء عنصر wx.Choice بمعدلات البت الحقيقية المسموح بها فعليًا
لترميز صيغة صوت هدف معيّنة (شوف core/converter.py: AUDIO_BITRATE_OPTIONS
للتفاصيل الكاملة عن مصدر كل قيمة).

مستخدَم في 3 أماكن بنفس المنطق بالظبط: نافذة محول الصيغ، نافذة مسجل
الصوت، وتبويب "المسجل" في صفحة الخيارات - فبقى في وحدة واحدة بدل تكراره
3 مرات (DRY).
"""

import wx

from core.formats import (
    HIGHEST_AUDIO_BITRATE,
    get_audio_bitrate_options,
    get_audio_codec_for_extension,
    pick_closest_audio_bitrate,
)


def refresh_audio_bitrate_choice(choice_ctrl, note_ctrl, tr, target_ext, is_video, preferred_bps):
    """بيملأ choice_ctrl بالقيم الحقيقية المسموح بها لترميز target_ext
    (كل عنصر بيحمل القيمة الفعلية بالبت في الثانية كـ ClientData)، مع
    اختيار أقرب قيمة لـ preferred_bps بدل أول قيمة تعسفيًا. لو الصيغة
    غير مضغوطة (مفيش معدل بت ينطبق أصلًا) بيخفي choice_ctrl ويظهر
    note_ctrl (لو موجود) بدله.

    أول عنصر دايمًا "أعلى جودة متاحة": بيحمل HIGHEST_AUDIO_BITRATE بدل
    رقم ثابت، فبيفضل يعني الأعلى مهما اتغيّرت الصيغة - 320 كيلوبت في
    MP3، و510 في Opus، و12.2 في AMR. رقم محفوظ واحد ما كانش يعرف يعمل
    كده: كان بيتحوّل لأقرب قيمة في كل صيغة.

    بترجع القيمة المختارة فعليًا (بالبت في الثانية)، أو
    HIGHEST_AUDIO_BITRATE لو المختار هو الوضع التلقائي، أو None لو
    الصيغة غير مضغوطة."""
    codec = get_audio_codec_for_extension(target_ext, is_video) if target_ext else None
    options = get_audio_bitrate_options(codec) if codec else None

    is_applicable = bool(options)
    choice_ctrl.Show(is_applicable)
    if note_ctrl is not None:
        note_ctrl.Show(not is_applicable)
    if not is_applicable:
        return None

    # Set دفعة واحدة بدل Clear ثم Append لكل عنصر: قارئ الشاشة كان
    # بيعلن كل إضافة، والقائمة بتتملي من جديد مع كل تغيير صيغة
    labels = [tr.t("audio_bitrate_highest_choice", value=options[-1] // 1000)]
    labels.extend(tr.t("converter_bitrate_kbps_choice", value=bps // 1000)
                  for bps in options)

    choice_ctrl.Set(labels)
    choice_ctrl.SetClientData(0, HIGHEST_AUDIO_BITRATE)
    for index, bps in enumerate(options):
        choice_ctrl.SetClientData(index + 1, bps)

    if not preferred_bps:
        choice_ctrl.SetSelection(0)
        return HIGHEST_AUDIO_BITRATE

    target_bps = pick_closest_audio_bitrate(options, preferred_bps)
    for index in range(choice_ctrl.GetCount()):
        if choice_ctrl.GetClientData(index) == target_bps:
            choice_ctrl.SetSelection(index)
            break
    return target_bps


def current_audio_bitrate_bps(choice_ctrl, fallback_bps: int) -> int:
    """القيمة المختارة حاليًا في choice_ctrl (بالبت في الثانية)، أو
    fallback_bps لو القائمة لسه فاضية (مفيش أي عنصر اتحدد لحد دلوقتي)."""
    selection = choice_ctrl.GetSelection()
    if selection != wx.NOT_FOUND:
        return choice_ctrl.GetClientData(selection)
    return fallback_bps
