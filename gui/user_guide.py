# -*- coding: utf-8 -*-
"""
دليل المستخدم ودليل الاختصارات، بالعربية والإنجليزية.

الدليل صفحة HTML تُفتح في المتصفح (F1): فهرس بروابط، وكل قسم عنوان
وقائمة نقاط حقيقية، فيتنقل قارئ الشاشة بالعناوين (H) والقوائم (L)
والروابط. والنسختان بالمحتوى نفسه نقطة بنقطة.

دليل الاختصارات يُعرض في آخر الدليل، ويُصدَّر مستندًا نصيًا منسقًا
(Ctrl+Shift+H). وفي الاثنين ما غيّره المستخدم من مقادير التقديم
والاختصارات الشبحية.
"""

import re
from html import escape

from core.version import APP_VERSION

# سطور التقديم بمفاتيحها في القائمة، ونوع كل منها في الإعدادات
_SEEK_LINE_KEYS = {
    "ar": (("normal", "السهم الأيمن / الأيسر"), ("ctrl", "Ctrl + السهم الأيمن / الأيسر"),
           ("shift", "Shift + السهم الأيمن / الأيسر"), ("alt", "Alt + السهم الأيمن / الأيسر"),
           ("ctrl_shift", "Ctrl + Shift + السهم الأيمن / الأيسر")),
    "en": (("normal", "Right / Left Arrow"), ("ctrl", "Ctrl + Right / Left Arrow"),
           ("shift", "Shift + Right / Left Arrow"), ("alt", "Alt + Right / Left Arrow"),
           ("ctrl_shift", "Ctrl + Shift + Right / Left Arrow")),
}

_SEEK_DEFAULTS = {"normal": 10, "ctrl": 60, "shift": 300, "alt": 600, "ctrl_shift": 1800}


def get_shortcuts_list(lang: str = "ar", seek_steps: dict = None, ghost_hotkeys: dict = None) -> list:
    """
    قائمة الاختصارات مصنفة: سطر «=== القسم ===» ثم «الوصف: المفاتيح».

    seek_steps ({النوع: ثوانٍ}) وghost_hotkeys ({الفعل: (المساعدة، المفتاح)})
    يضعان ما ضبطه المستخدم في الخيارات مكان القيم الافتراضية.
    """
    lines = _default_shortcuts_list(lang)
    if seek_steps:
        lines = _apply_seek_steps(lines, lang, seek_steps)
    if ghost_hotkeys:
        lines = _apply_ghost_hotkeys(lines, ghost_hotkeys)
    return lines


def _amount_text(lang, seconds):
    from i18n.plural import count_phrase
    from i18n.strings import Translator

    tr = Translator(lang)
    if seconds >= 60 and seconds % 60 == 0:
        return count_phrase(tr, "count_minutes", seconds // 60)
    return count_phrase(tr, "count_seconds", seconds)


def _seek_line(lang, amount, key_text):
    return (f"تقديم أو إرجاع {amount}: {key_text}" if lang == "ar"
            else f"Seek {amount}: {key_text}")


def _apply_seek_steps(lines, lang, seek_steps):
    keys = _SEEK_LINE_KEYS["ar" if lang == "ar" else "en"]
    result = []
    for line in lines:
        for kind, key_text in keys:
            if line.endswith(": " + key_text) and kind in seek_steps:
                line = _seek_line(lang, _amount_text(lang, seek_steps[kind]), key_text)
                break
        result.append(line)
    return result


def _apply_ghost_hotkeys(lines, ghost_hotkeys):
    from gui.editor_hotkeys import DEFAULT_HOTKEYS, combo_text

    replacements = {}
    for action, default in DEFAULT_HOTKEYS:
        if action in ghost_hotkeys:
            replacements[": " + combo_text(default).replace("+", " + ")] = \
                ": " + combo_text(ghost_hotkeys[action]).replace("+", " + ")
    result = []
    for line in lines:
        for old, new in replacements.items():
            if line.endswith(old):
                line = line[: -len(old)] + new
                break
        result.append(line)
    return result


def _default_shortcuts_list(lang: str) -> list:
    """
    الاختصارات بأقسامها: سطر «=== القسم ===» ثم «الوصف: المفاتيح».

    النقطتان الأوليان تفصلان الوصف عن المفاتيح، فلا نقطتان في الوصف.
    وسطور التقديم والاختصارات الشبحية تبقى بصيغتها هذه بالضبط:
    _apply_seek_steps و_apply_ghost_hotkeys يعرفانها من آخرها.
    """
    seek = {kind: _amount_text(lang, seconds) for kind, seconds in _SEEK_DEFAULTS.items()}
    keys = dict(_SEEK_LINE_KEYS["ar" if lang == "ar" else "en"])
    seek_lines = [_seek_line(lang, seek[kind], keys[kind])
                  for kind in ("normal", "ctrl", "shift", "alt", "ctrl_shift")]

    if lang == "ar":
        return [
            "=== التشغيل الأساسي ===",
            "تشغيل أو إيقاف مؤقت: Space",
            "إيقاف التشغيل والعودة إلى البداية: Ctrl + Space",
            "كتم الصوت أو إلغاء الكتم: M",
            "رفع الصوت أو خفضه بمقدار 5%: السهم العلوي / السفلي",
            "رفع الصوت أو خفضه بمقدار 20%: Ctrl + السهم العلوي / السفلي",
            "ملء الشاشة للفيديو: F11",
            "الخروج من ملء الشاشة: Escape",
            "التشغيل والإيقاف والتنقل بين الملفات والبرنامج في الخلفية: مفاتيح الوسائط في لوحة المفاتيح",
            "",
            "=== التقديم والإرجاع ===",
            *seek_lines,
            "تقديم أو إرجاع متواصل يتسارع كلما طال الضغط، والصوت مكتوم حتى تُفلت المفتاح: اضغط مطولًا على السهم الأيمن / الأيسر",
            "القفز إلى نسبة من الملف (من 10% إلى 90%): Numpad 1 إلى 9",
            "القفز إلى بداية الملف: Numpad 0 أو Home",
            "القفز إلى آخر 5 ثوانٍ من الملف: End",
            "الانتقال إلى وقت محدد: Ctrl + G",
            "",
            "=== السرعة والعلامات المرجعية ===",
            "زيادة السرعة أو تقليلها بمقدار 0.25: Alt + السهم العلوي / السفلي",
            "إعادة السرعة الطبيعية: Alt + Numpad 0",
            "إضافة علامة عند الموضع الحالي: Ctrl + B",
            "تسمية أقرب علامة: Ctrl + Alt + B",
            "الانتقال إلى العلامة التالية: F2",
            "الانتقال إلى العلامة السابقة: Shift + F2",
            "حذف كل علامات الملف الحالي: Ctrl + Shift + B",
            "",
            "=== إعلانات الوقت وقارئ الشاشة ===",
            "الوقت الحالي: T",
            "الوقت المتبقي وحده: R",
            "مدة الملف كاملة: E",
            "ما يُذاع الآن في الراديو: N",
            "إيقاف كل الإعلانات أو إعادتها: Ctrl + Alt + A",
            "",
            "=== الملفات والمجلدات والروابط ===",
            "فتح ملف: Ctrl + O",
            "فتح مجلد كامل: Ctrl + Shift + O",
            "فتح رابط (راديو أو بث مباشر أو ملف على الإنترنت): Ctrl + U",
            "الملف التالي في المجلد أو القائمة: Page Down",
            "الملف السابق في المجلد أو القائمة: Page Up",
            "",
            "=== قوائم التشغيل ===",
            "نافذة قائمة التشغيل: Ctrl + L",
            "حفظ قائمة التشغيل بصيغة M3U8: Ctrl + S",
            "داخل النافذة، تشغيل الملف المحدد: Enter",
            "داخل النافذة، حذف الملف المحدد من القائمة: Delete",
            "داخل النافذة، تحريك الملف لأعلى أو لأسفل: Alt + السهم العلوي / السفلي",
            "داخل النافذة، فتح قائمة محفوظة: Ctrl + O",
            "",
            "=== المعادل الصوتي ===",
            "نافذة المعادل الصوتي: Ctrl + E",
            "النمط التالي أو السابق: Q / Shift + Q",
            "داخل النافذة، رفع النطاق المحدد أو خفضه: السهم العلوي / السفلي",
            "",
            "=== مسجّل الصوت ===",
            "نافذة مسجّل الصوت: Ctrl + Shift + R",
            "بدء التسجيل فورًا، والضغطة الثانية توقفه وتحفظه (من النافذة الرئيسية أو نافذة المسجّل): Ctrl + R",
            "سماع المستوى أثناء التسجيل (داخل نافذة المسجّل): Ctrl + L",
            "تغيير مستوى المايكروفون درجةً واحدة على شريط «مستوى المايكروفون»، حتى أثناء التسجيل: السهم العلوي / السفلي",
            "تغيير مستوى المايكروفون عشر درجات: Page Up / Page Down",
            "",
            "=== محرر الوسائط ===",
            "نافذة محرر الوسائط: Ctrl + Shift + X",
            "",
            "=== الاختصارات الشبحية لمحرر الوسائط (تعمل من أي مكان) ===",
            "تشغيل الاختصارات الشبحية أو إيقافها: Ctrl + Alt + Shift + G",
            "فتح محرر الوسائط: Ctrl + Alt + Shift + O",
            "تحديد نقطة القص عند الموضع الحالي: Ctrl + Alt + Shift + S",
            "تحديد بداية مقطع عند الموضع الحالي: Ctrl + Alt + Shift + B",
            "تحديد نهاية المقطع وإضافته: Ctrl + Alt + Shift + E",
            "التراجع عن آخر مقطع أو بداية: Ctrl + Alt + Shift + Z",
            "إضافة الملف الحالي إلى قائمة «قص عدة ملفات»: Ctrl + Alt + Shift + L",
            "إضافة الملف الحالي إلى قائمة الدمج: Ctrl + Alt + Shift + M",
            "سماع ما حُدِّد في المحرر: Ctrl + Alt + Shift + I",
            "بدء العمل: Ctrl + Alt + Shift + Enter",
            "إلغاء العمل الجاري: Ctrl + Alt + Shift + C",
            "",
            "=== النوافذ والخيارات والمساعدة ===",
            "إغلاق أي نافذة من نوافذ الأدوات: Escape",
            "الخيارات: Ctrl + Shift + P",
            "التنقل بين تبويبات الخيارات: Ctrl + Tab، أو Ctrl + 1 إلى Ctrl + 6",
            "محول الصيغ ومؤقت النوم وتصدير الإعدادات واستيرادها: من قائمة «أدوات»",
            "دليل الاستخدام: F1",
            "تصدير دليل الاختصارات: Ctrl + Shift + H",
            "حفظ تقرير تشخيصي على سطح المكتب (بلا معلومات شخصية): Ctrl + Shift + D",
            "الخروج من البرنامج: Ctrl + Q",
        ]
    return [
        "=== Basic Playback ===",
        "Play or pause: Space",
        "Stop and return to the start: Ctrl + Space",
        "Mute or unmute: M",
        "Volume up or down by 5%: Up / Down Arrow",
        "Volume up or down by 20%: Ctrl + Up / Down Arrow",
        "Video fullscreen: F11",
        "Leave fullscreen: Escape",
        "Play, stop and move between files with the program in the background: your keyboard's media keys",
        "",
        "=== Seeking ===",
        *seek_lines,
        "Continuous seeking that speeds up the longer you hold, muted until you let go: hold Right / Left Arrow",
        "Jump to a percentage of the file (10% to 90%): Numpad 1 to 9",
        "Jump to the start of the file: Numpad 0 or Home",
        "Jump to the last 5 seconds of the file: End",
        "Go to a specific time: Ctrl + G",
        "",
        "=== Speed & Bookmarks ===",
        "Speed up or slow down by 0.25: Alt + Up / Down Arrow",
        "Normal speed: Alt + Numpad 0",
        "Add a bookmark at the current position: Ctrl + B",
        "Name the nearest bookmark: Ctrl + Alt + B",
        "Next bookmark: F2",
        "Previous bookmark: Shift + F2",
        "Clear all bookmarks of the current file: Ctrl + Shift + B",
        "",
        "=== Time & Screen Reader Announcements ===",
        "Current time: T",
        "Remaining time only: R",
        "Total duration only: E",
        "Radio now playing: N",
        "Turn all announcements off or on: Ctrl + Alt + A",
        "",
        "=== Files, Folders & Links ===",
        "Open a file: Ctrl + O",
        "Open a whole folder: Ctrl + Shift + O",
        "Open a link (radio, live stream or online file): Ctrl + U",
        "Next file in the folder or playlist: Page Down",
        "Previous file in the folder or playlist: Page Up",
        "",
        "=== Playlists ===",
        "Playlist window: Ctrl + L",
        "Save the playlist as M3U8: Ctrl + S",
        "In the window, play the selected file: Enter",
        "In the window, remove the selected file from the list: Delete",
        "In the window, move the file up or down: Alt + Up / Down Arrow",
        "In the window, open a saved playlist: Ctrl + O",
        "",
        "=== Equalizer ===",
        "Equalizer window: Ctrl + E",
        "Next or previous preset: Q / Shift + Q",
        "In the window, raise or lower the selected band: Up / Down Arrow",
        "",
        "=== Audio Recorder ===",
        "Audio Recorder window: Ctrl + Shift + R",
        "Start recording right away; press again to stop and save (from the main or Recorder window): Ctrl + R",
        "Hear the level while recording (in the Recorder window): Ctrl + L",
        "Change the microphone level one step on the “Microphone level” slider, even while recording: Up / Down Arrow",
        "Change the microphone level ten steps: Page Up / Page Down",
        "",
        "=== Media Editor ===",
        "Media Editor window: Ctrl + Shift + X",
        "",
        "=== Media Editor Ghost Shortcuts (work from anywhere) ===",
        "Turn ghost shortcuts on or off: Ctrl + Alt + Shift + G",
        "Open the Media Editor: Ctrl + Alt + Shift + O",
        "Set the split point at the current position: Ctrl + Alt + Shift + S",
        "Set a part start at the current position: Ctrl + Alt + Shift + B",
        "Set the part end and add the part: Ctrl + Alt + Shift + E",
        "Undo the last part or start: Ctrl + Alt + Shift + Z",
        "Add the current file to the “Split several files” list: Ctrl + Alt + Shift + L",
        "Add the current file to the merge list: Ctrl + Alt + Shift + M",
        "Hear what is set in the editor: Ctrl + Alt + Shift + I",
        "Start the work: Ctrl + Alt + Shift + Enter",
        "Cancel the running work: Ctrl + Alt + Shift + C",
        "",
        "=== Windows, Options & Help ===",
        "Close any tool window: Escape",
        "Options: Ctrl + Shift + P",
        "Switch Options tabs: Ctrl + Tab, or Ctrl + 1 to Ctrl + 6",
        "Format converter, sleep timer, export and import settings: from the Tools menu",
        "User guide: F1",
        "Export the shortcuts guide: Ctrl + Shift + H",
        "Save a diagnostic report to the Desktop (no personal data): Ctrl + Shift + D",
        "Exit the program: Ctrl + Q",
    ]


def build_shortcuts_text(tr, seek_steps: dict = None, ghost_hotkeys: dict = None) -> str:
    """
    دليل الاختصارات مستندًا نصيًا منسقًا (Ctrl+Shift+H).

    عنوان ومقدمة، ثم الأقسام مرقّمة تحت كل منها خط، وكل اختصار في سطر
    «• الوصف: المفاتيح» يقرؤه قارئ الشاشة سطرًا سطرًا. والخاتمة تدل على
    الدليل الكامل.
    """
    lang = "ar" if getattr(tr, "lang", "ar") == "ar" else "en"
    is_ar = lang == "ar"
    app_name = tr.t("app_title")
    rule = "=" * 56

    if is_ar:
        title = "دليل اختصارات لوحة المفاتيح"
        subtitle = f"{app_name}، الإصدار {APP_VERSION}"
        intro = [
            "كل ما في البرنامج يعمل من لوحة المفاتيح. الاختصارات هنا مجمّعة بحسب ما تؤديه،",
            "وكل سطر يبدأ بالمهمة، وبعد النقطتين المفاتيح التي تؤديها.",
            "مقادير التقديم والإرجاع والاختصارات الشبحية مكتوبة كما ضبطتها أنت في الخيارات.",
        ]
        closing = [
            "لشرح كل ميزة بالتفصيل افتح دليل الاستخدام بالمفتاح F1.",
            "ويمكنك تغيير مقادير التقديم والإرجاع والاختصارات الشبحية من الخيارات: Ctrl + Shift + P.",
        ]
    else:
        title = "Keyboard Shortcuts Guide"
        subtitle = f"{app_name}, version {APP_VERSION}"
        intro = [
            "Everything in the program works from the keyboard. Shortcuts are grouped by what they do,",
            "and each line starts with the task, followed after the colon by the keys that do it.",
            "Seek amounts and ghost shortcuts are shown as you set them in Options.",
        ]
        closing = [
            "For a full explanation of every feature, open the user guide with F1.",
            "Seek amounts and ghost shortcuts can be changed in Options: Ctrl + Shift + P.",
        ]

    out = [title, subtitle, rule, "", *intro]
    number = 0
    for line in get_shortcuts_list(lang, seek_steps, ghost_hotkeys):
        if not line:
            continue
        if line.startswith("==="):
            number += 1
            heading = f"{number}. {line.strip('= ').strip()}"
            out += ["", heading, "-" * len(heading)]
        else:
            out.append(f"• {line}")
    out += ["", rule, *closing, ""]
    return "\n".join(out)


def _k(keys):
    """
    مفاتيح داخل النص: كل مفتاح في <kbd> والعلامة + بينها.

    الاختصار كله من اليسار لليمين: في الصفحة العربية كانت المفاتيح تُرتَّب
    من اليمين فيظهر Ctrl+Shift+X كأنه X+Shift+Ctrl.
    """
    joined = "+".join(f"<kbd>{escape(part.strip())}</kbd>" for part in keys.split("+"))
    return f'<span class="combo" dir="ltr">{joined}</span>'


def _sections(lang, steps):
    """
    أقسام الدليل: (معرّف، عنوان، [نقاط]). النقطة نص HTML يبدأ بعنوان
    فرعي بين <b>.

    steps: مقادير التقديم الحالية بالثواني، ليطابق الدليل ما ضبطه المستخدم.
    """
    amount = {kind: _amount_text(lang, seconds) for kind, seconds in steps.items()}
    k = _k

    if lang == "ar":
        return [
            ("new", "ما الجديد في الإصدار " + APP_VERSION, [
                f"<b>محرر الوسائط:</b> قص الصوت والفيديو ودمجهما داخل البرنامج، مع اختصارات «شبحية» تعمل وأنت تستمع في المشغّل ({k('Ctrl+Shift+X')}).",
                f"<b>الراديو والبث المباشر:</b> افتح أي رابط بـ {k('Ctrl+U')}، ويُعلَن اسم ما يُذاع كلما تغيّر.",
                f"<b>قوائم تشغيل محفوظة:</b> اجمع ملفاتك ورتّبها في نافذة القائمة ({k('Ctrl+L')})، واحفظها بـ {k('Ctrl+S')}.",
                f"<b>المعادل الصوتي:</b> ثمانية عشر نمطًا جاهزًا تتنقل بينها بـ {k('Q')}، وعشرة نطاقات تضبطها بنفسك ({k('Ctrl+E')}).",
                "<b>تسجيل أنقى:</b> شريط لمستوى المايكروفون داخل المسجّل، وتقليل للضوضاء يعمل فعلًا مع أي مايكروفون، ووضع حصري يعمل مع مايكروفونات USB، ودمج صوتك مع صوت الجهاز بلا انقطاع.",
                "<b>محول أذكى:</b> «أعلى جودة» لا تضخّم الملف بلا فائدة، والصيغ التي كانت تفشل مع معدلات العيّنة العالية صارت تنجح.",
                "<b>مظهر داكن حقيقي</b> يشمل البرنامج كله، وواجهة عربية تُقرأ من اليمين إلى اليسار.",
                "<b>مقادير تقديم تختارها بنفسك</b> لكل مفتاح مساعد، ومجلدات حفظ ثابتة ومرتبة في «المستندات».",
            ]),
            ("start", "البداية", [
                f"<b>فتح الملفات:</b> {k('Ctrl+O')} لفتح ملف، و{k('Ctrl+Shift+O')} لمجلد كامل، و{k('Ctrl+U')} لرابط. وفي قائمة «ملف» تجد «الملفات الأخيرة».",
                "<b>من مستكشف ويندوز:</b> انقر بزر الفأرة الأيمن على ملف صوت أو فيديو تجد أمرَي «تشغيل» و«تحويل» بالبرنامج، وعلى مجلد تجد «تحويل» لكل ما فيه. ويظهر البرنامج أيضًا في قائمة «فتح باستخدام».",
                "<b>الاستئناف:</b> يتذكر البرنامج أين توقفت في كل ملف فيكمل من عنده إذا فتحته مرة أخرى، ويتذكر سرعة التشغيل لكل ملف على حدة.",
                f"<b>التنقل في المجلد:</b> فتح ملف يضم إليه بقية ملفات مجلده، فتنتقل بينها بـ {k('Page Down')} و{k('Page Up')}. ومن الخيارات تختار ما يحدث عند انتهاء الملف: لا شيء، أو الانتقال إلى التالي.",
                "<b>مفاتيح الوسائط:</b> أزرار التشغيل والإيقاف والتالي والسابق في لوحة المفاتيح تتحكم في البرنامج حتى وهو في الخلفية، ويمكنك إطفاؤها من الخيارات.",
            ]),
            ("playback", "التشغيل والتنقل داخل الملف", [
                f"<b>التشغيل:</b> {k('Space')} للتشغيل والإيقاف المؤقت، و{k('Ctrl+Space')} للإيقاف والعودة إلى البداية، و{k('M')} لكتم الصوت.",
                f"<b>مستوى الصوت:</b> السهمان العلوي والسفلي يغيّرانه بخطوة 5%، ومع {k('Ctrl')} بخطوة 20%.",
                f"<b>التقديم والإرجاع:</b> السهمان الأيمن والأيسر يقدّمان ويرجعان {amount['normal']}، ومع {k('Ctrl')} {amount['ctrl']}، ومع {k('Shift')} {amount['shift']}، ومع {k('Alt')} {amount['alt']}، ومع {k('Ctrl+Shift')} {amount['ctrl_shift']}. وتغيّر أيًّا من هذه المقادير من تبويب «التشغيل والتنقل» في الخيارات.",
                "<b>التقديم المتواصل:</b> اضغط مطولًا على السهم الأيمن أو الأيسر فيتقدم الموضع أو يرجع متسارعًا كلما طال الضغط، والصوت مكتوم حتى تُفلت المفتاح، ثم يُعلَن الموضع الجديد.",
                f"<b>القفز المباشر:</b> أرقام لوحة الأرقام من 1 إلى 9 تنقلك إلى 10% حتى 90% من الملف، و{k('Numpad 0')} أو {k('Home')} إلى بدايته، و{k('End')} إلى آخر خمس ثوانٍ منه.",
                f"<b>الذهاب إلى وقت محدد:</b> اضغط {k('Ctrl+G')} واكتب الوقت: <code>90</code> أو <code>1:30</code> أو <code>1:02:03</code>. وإن كان الوقت بعد نهاية الملف أخبرك البرنامج بدل أن ينقلك إلى مكان خاطئ.",
                f"<b>السرعة:</b> {k('Alt')} مع السهم العلوي أو السفلي يغيّرها بمقدار 0.25، و{k('Alt+Numpad 0')} يعيدها طبيعية، ولا تتغير نبرة الصوت.",
                f"<b>ملء الشاشة:</b> {k('F11')} لعرض الفيديو بملء الشاشة، و{k('Escape')} للخروج منه.",
            ]),
            ("announce", "الإعلانات الصوتية والوقت", [
                f"<b>الوقت عند الطلب:</b> {k('T')} للوقت الحالي، و{k('R')} للوقت المتبقي، و{k('E')} لمدة الملف كاملة.",
                f"<b>المفتاح الرئيسي:</b> {k('Ctrl+Alt+A')} يوقف كل إعلانات البرنامج دفعة واحدة، ويعيدها.",
                "<b>لكل إعلان خياره:</b> في تبويب «إمكانية الوصول» صندوق اختيار لكل إعلان: اسم الملف وترتيبه في القائمة، والاستئناف، وحالة التشغيل، والصوت والكتم، والسرعة، والعلامات، ومؤقت النوم، ونمط المعادل، وما يُذاع في الراديو، وغيرها. أبقِ ما ينفعك وأسكت الباقي.",
                "<b>تقديم بلا ثرثرة:</b> اختر أصغر قفزة يُعلَن بعدها الموضع الجديد: كل القفزات، أو ما بلغ دقيقة أو 5 أو 10 أو 30 دقيقة فأكثر. أما أرقام لوحة الأرقام والذهاب إلى وقت محدد فتُعلَن دائمًا.",
                "<b>معلومات الملف:</b> يمكن أن يعلن البرنامج صيغة الملف وجودته ومدته عند فتحه، ويعلن حالة التحميل إذا تأخر الملف في الفتح.",
            ]),
            ("bookmarks", "العلامات المرجعية", [
                f"<b>ضع علامة</b> عند أي موضع بـ {k('Ctrl+B')}، وتنقّل بين العلامات بـ {k('F2')} و{k('Shift+F2')}، واحذف كل علامات الملف بـ {k('Ctrl+Shift+B')}.",
                f"<b>سمِّ العلامة</b> بـ {k('Ctrl+Alt+B')}، فتسمع «بداية الفصل الثالث» بدل «علامة عند 12 دقيقة». واترك الاسم فارغًا لإزالته.",
                "<b>العلامات تخدم المحرر أيضًا:</b> في محرر الوسائط تختار الأوقات «من العلامات» بدل كتابتها؛ انظر قسم محرر الوسائط.",
            ]),
            ("streams", "الراديو والروابط وقوائم التشغيل", [
                f"<b>الروابط:</b> {k('Ctrl+U')} يفتح خانة الرابط، وإن كنت قد نسخت رابطًا وجدته مكتوبًا فيها. يشغّل البرنامج الراديو والبث المباشر والملفات على الإنترنت، ويعيد الاتصال وحده إذا انقطع البث.",
                f"<b>ما يُذاع الآن:</b> في المحطات التي ترسل اسم الأغنية أو البرنامج يُعلَن الاسم كلما تغيّر، و{k('N')} يعيده متى شئت.",
                f"<b>نافذة القائمة:</b> {k('Ctrl+L')} يفتح قائمة التشغيل الحالية: أضف ملفات أو مجلدات أو روابط محطات، وشغّل الملف المحدد بـ {k('Enter')}، واحذفه بـ {k('Delete')}، وحرّكه بـ {k('Alt')} مع السهمين العلوي والسفلي.",
                f"<b>حفظ القوائم وفتحها:</b> {k('Ctrl+S')} يحفظ القائمة بصيغة M3U8 التي تفتحها معظم المشغلات، وإن كانت الملفات داخل مجلد القائمة بقيت صالحة إذا نقلت المجلد كله. وتُفتح أي قائمة M3U أو M3U8 أو PLS مثل أي ملف بـ {k('Ctrl+O')}، أو من داخل نافذة القائمة.",
            ]),
            ("eq", "المعادل الصوتي", [
                f"<b>الأنماط الجاهزة:</b> {k('Q')} و{k('Shift+Q')} يتنقلان بين ثمانية عشر نمطًا، منها «سماعات الرأس» و«جهير كامل» و«قاعة كبيرة»، ويُنطق اسم كل نمط.",
                f"<b>الضبط اليدوي:</b> {k('Ctrl+E')} يفتح نافذة فيها التضخيم المسبق وعشرة نطاقات تعدّلها بالسهمين العلوي والسفلي وتسمع النتيجة فورًا. تعديل أي نطاق يجعل النمط «مخصص»، و«إلغاء» يعيد ما كان قبل فتح النافذة.",
                "<b>يبقى محفوظًا:</b> اختيارك يسري على كل الملفات، ويبقى بعد إغلاق البرنامج.",
            ]),
            ("recorder", "مسجّل الصوت", [
                f"<b>الفتح والتسجيل السريع:</b> {k('Ctrl+Shift+R')} يفتح نافذة المسجّل. و{k('Ctrl+R')} من النافذة الرئيسية أو نافذة المسجّل يبدأ التسجيل فورًا بآخر إعداداتك، والضغطة الثانية توقفه وتحفظه. وإذا أغلقت النافذة والتسجيل جارٍ اختفت النافذة واستمر التسجيل في الخلفية.",
                "<b>قائمة أجهزة نظيفة:</b> يظهر كل مايكروفون مرة واحدة باسم مفهوم، ويختار له البرنامج أفضل طريقة اتصال وأنسب الإعدادات، ويحفظ لكل جهاز إعداداته على حدة.",
                f"<b>مستوى المايكروفون:</b> شريط «مستوى المايكروفون» تحت اختيار الجهاز هو نفسه مستوى المايكروفون في إعدادات الصوت بويندوز. والتشوّه يحدث داخل المايكروفون قبل أن يصل الصوت إلى البرنامج، فخفض هذا المستوى هو العلاج الحقيقي. حرّكه بالأسهم درجةً درجة، أو بـ {k('Page Up')} و{k('Page Down')} عشر درجات، ويمكنك تغييره أثناء التسجيل. ابدأ من نحو 70%. وإذا كان الجهاز لا يسمح بالتحكم في مستواه تعطّل الشريط وظهر تحته السبب.",
                "<b>اختبار المايكروفون:</b> زر يسجّل عشر ثوانٍ، ثم يخبرك بنص يقرؤه قارئ الشاشة: هل المستوى جيد أم مرتفع أم منخفض أم لا يصل صوت أصلًا، ومعه خطوات الإصلاح.",
                f"<b>المستوى أثناء التسجيل:</b> {k('Ctrl+L')} ينطق المستوى الحالي وأعلى قمة، وعند الطلب فقط حتى لا يُسجَّل صوت قارئ الشاشة في الملف. وإذا ارتفع المستوى حتى التشوّه ظهر تنبيه في النافذة، وأخبرك البرنامج عند الحفظ بعدد المواضع المتأثرة.",
                "<b>تحسين صوت المايكروفون:</b> «بلا معالجة» يحفظ الصوت كما خرج من كرت الصوت. و«تنقية» تزيل الطنين المنخفض (اهتزاز المكتب، ومروحة الجهاز، ولمس المايكروفون) وتمنع قص القمم دون أن تمس الكلام. و«تنقية وتقليل الضوضاء الثابتة» تخفض معها الوشيش وصوت التكييف والمروحة وطنين الكهرباء: يقيس البرنامج ضوضاء مايكروفونك وغرفتك بنفسه أثناء التسجيل، فيخفضها نحو أربع مرات في سكتات الكلام دون أن يصير الصوت معدنيًا. والتحسين للمايكروفون وحده، ولا يمس صوت الجهاز.",
                "<b>الوضع الحصري (وصول مباشر إلى كرت الصوت):</b> يأخذ البرنامج الصوت من الكرت مباشرة دون معالجة ويندوز، فلا تحسينات خفية ولا خلط مع البرامج الأخرى، لكن لا يستطيع برنامج آخر استعمال المايكروفون أثناء التسجيل. بعض المايكروفونات لا تقبل هذا الوضع إلا بدقتها الأصلية (192000 مثلًا)، فيلتقط البرنامج بها ثم يحوّل الصوت إلى الدقة التي اخترتها، ويبقى الملف بحجمه المعتاد. وإذا رفض الكرت الوضع الحصري تمامًا أخبرك البرنامج وسجّل بالوضع العادي.",
                "<b>صوتك مع صوت الجهاز:</b> فعّل «دمج جهاز إدخال ثانٍ» فيختار البرنامج صوت النظام (الستيريو ميكس) تلقائيًا. يُدمج المصدران عيّنةً بعيّنة ويُوازَن مستواهما، فلا يضيع صوتك تحت الموسيقى ولا يتقطع التسجيل.",
                "<b>الجودة والصيغة:</b> معدل العيّنة (48000 تكفي لكل ما تسمعه الأذن)، وأحادي أو ستيريو، وعمق 16 أو 24 أو 32 بت، ثم الصيغة: WAV بلا ضغط، أو MP3 وM4A وغيرهما بملفات أصغر بكثير تُكتب مباشرة أثناء التسجيل. ويبدأ «معدل البت» عند «أعلى جودة متاحة» التي تعرف سقف كل صيغة.",
            ]),
            ("editor", "محرر الوسائط", [
                f"<b>أربع عمليات</b> من قائمة «أدوات» أو بـ {k('Ctrl+Shift+X')}: «قص ملف» إلى جزأين، و«قص عدة ملفات» عند الوقت نفسه دفعة واحدة، و«مقاطع من ملف» تُضم بالترتيب في ملف واحد، و«دمج ملفات» بالترتيب الذي تختاره.",
                "<b>بلا فقد في الجودة:</b> يخرج الناتج بصيغة الأصل نفسها، ويُنسخ الصوت كما هو دون إعادة ترميز. وملفات الصوت المختلفة الصيغ تُدمج بعد إعادة ترميزها، أما ملفات الفيديو المدموجة فيجب أن تتطابق في الصيغة والمقاس، وإلا أخبرك المحرر بالسبب.",
                "<b>طريقتان للفيديو:</b> «سريع بنفس الجودة» يبدأ القص من أقرب إطار مفتاحي (صورة كاملة كل بضع ثوانٍ) ويخبرك أين قص بالضبط، و«دقيق بالثانية» يقص عند الوقت المطلوب لكنه أبطأ.",
                f"<b>الأوقات بلا كتابة:</b> زر «الموضع الحالي» يأخذ الوقت من المشغّل وأنت تستمع. أو ضع علامة بـ {k('Ctrl+B')} عند كل موضع، ثم اختر الوقت «من العلامات»، أو اضغط «مقاطع من العلامات» فتصير كل علامتين متتاليتين بداية مقطع ونهايته. وتقبل خانة الوقت أجزاء الثانية، مثل <code>1:30.5</code>.",
                f"<b>الاختصارات الشبحية:</b> تعمل من أي مكان، والمشغّل في المقدمة أو في الخلفية: تحدد بها نقطة القص وبداية المقطع ونهايته، وتضيف الملف الحالي إلى قائمتَي القص والدمج، وتسمع ما حدّدته، وتبدأ العمل أو تلغيه، دون أن تفتح نافذة المحرر. تشغّلها وتوقفها بـ {k('Ctrl+Alt+Shift+G')} أو من قائمة «أدوات»، وتجدها كلها في آخر هذا الدليل. وإغلاق المحرر يخفيه فقط، فلا يضيع ما حددته.",
                "<b>إعدادات المحرر:</b> في تبويب «محرر الوسائط» بالخيارات: طريقة قص الفيديو الافتراضية، والإعلان عن التقدم كل نسبة تختارها، وتغيير أي اختصار شبحي، ويرفض البرنامج الاختصار المكرر.",
            ]),
            ("converter", "محول الصيغ", [
                "<b>الفتح:</b> من قائمة «أدوات»، أو بزر الفأرة الأيمن على ملف أو مجلد في مستكشف ويندوز. يحوّل ملفًا واحدًا أو مجلدًا كاملًا دفعة واحدة، ويعلن تقدم كل ملف ونتيجته.",
                "<b>معلومات المصدر الحقيقية:</b> الترميز والدقة ومعدل البت الفعلي ومعدل العيّنة والقنوات، لتعرف ما تحوّله قبل أن تبدأ.",
                "<b>أعلى جودة بذكاء:</b> «أعلى جودة متاحة» تعرف سقف كل صيغة (320 كيلوبت لـ MP3، و640 لـ AC3، و256 لـ Opus الأحادي)، ولا تتجاوز جودة المصدر المضغوط، فلا يكبر الملف بلا فائدة. وإن اخترت رقمًا فوق ما تحتمله الصيغة استعمل البرنامج أقصاها بدل أن يفشل التحويل، وكذلك مع معدلات العيّنة غير المدعومة.",
                "<b>إعدادات متقدمة:</b> للصوت معدل العيّنة والقنوات، وللفيديو الجودة الثابتة (CRF) أو معدل البت الثابت، والدقة ومعدل الإطارات. وقيمها الافتراضية في تبويب «المحول» بالخيارات.",
            ]),
            ("folders", "أين تُحفظ ملفاتك", [
                "في «المستندات» مجلد باسم البرنامج، فيه: «التسجيلات»، و«الملفات المحولة»، و«محرر الوسائط» وبداخله «صوت» و«فيديو».",
                "تُسمّى هذه المجلدات مرة واحدة بلغة البرنامج عند أول تشغيل، ولا تتغير أسماؤها بعد ذلك، وإن كان الاسم مستعملًا أُضيف إليه رقم. وتُضم إليها مجلدات الإصدارات السابقة تلقائيًا.",
                "وعند حفظ تسجيل يخبرك البرنامج بمدته والمكان الذي حُفظ فيه.",
            ]),
            ("options", "الخيارات والتخصيص", [
                f"<b>الخيارات</b> بـ {k('Ctrl+Shift+P')}، وفيها ستة تبويبات تتنقل بينها بـ {k('Ctrl+Tab')} أو من {k('Ctrl+1')} إلى {k('Ctrl+6')}: «عام»، و«التشغيل والتنقل»، و«إمكانية الوصول»، و«المحول»، و«المسجّل»، و«محرر الوسائط».",
                "<b>المظهر:</b> «يتبع ويندوز» أو «فاتح» أو «داكن». الداكن يشمل القوائم وشريط العنوان وكل النوافذ، ويسري بعد إعادة فتح البرنامج. وفي وضع التباين العالي يستعمل البرنامج ألوان ويندوز دائمًا.",
                "<b>اللغة:</b> العربية بواجهة من اليمين إلى اليسار، أو الإنجليزية، وتسري بعد إعادة التشغيل.",
                "<b>وفي «عام» أيضًا:</b> عدد الملفات الأخيرة، ونغمة هادئة عند انتهاء التحويل أو التسجيل، ومفاتيح الوسائط، وزرّان يفتحان إعدادات «البرامج الافتراضية» و«خصوصية المايكروفون» في ويندوز.",
                "<b>مؤقت النوم:</b> من قائمة «أدوات»، يوقف التشغيل بعد عدد من الدقائق تحدده، أو عند نهاية الملف الحالي. واختر صفرًا لإلغائه.",
                "<b>نقل إعداداتك:</b> «تصدير الإعدادات» و«استيراد الإعدادات» من قائمة «أدوات»، لجهاز جديد أو لنسخة احتياطية.",
                f"<b>النوافذ:</b> {k('Escape')} يغلق أي نافذة من نوافذ الأدوات، والنافذة الرئيسية تفتح بحجمها وموضعها كما تركتها.",
            ]),
            ("help", "عند مواجهة مشكلة", [
                f"<b>تقرير تشخيصي:</b> {k('Ctrl+Shift+D')} يحفظ على سطح المكتب ملفًا نصيًا فيه معلومات النظام وسجل البرنامج، <b>بلا أي معلومات شخصية</b>: لا اسم جهازك ولا اسم المستخدم ولا مسارات ملفاتك، فيمكنك نشره في مجموعة عامة مطمئنًا.",
                "<b>تفاصيل اختبار المايكروفون:</b> في نتيجة الاختبار زر «نسخ التفاصيل التقنية» ينسخ سطرًا واحدًا خاليًا من أي بيانات تعرّفك، جاهزًا للصق في رسالة الدعم.",
                "<b>لا يصل صوت من المايكروفون:</b> تأكد أن ويندوز يسمح للتطبيقات باستعمال المايكروفون؛ زر «خصوصية المايكروفون» في تبويب «عام» يفتح هذا الإعداد مباشرة. وإن كان برنامج آخر يحجز المايكروفون في الوضع الحصري فأغلقه وحاول مرة أخرى.",
            ]),
            ("license", "الترخيص", [
                "البرنامج حر تحت رخصة GNU GPL الإصدار الثالث: لك أن تستعمله وتنسخه وتعدّله وتوزّعه وفق شروطها، وهو مقدَّم بلا أي ضمان.",
                "نص الرخصة وتراخيص المكتبات المضمَّنة في الملفين LICENSE وTHIRD-PARTY.md وفي مجلد licenses بجانب البرنامج.",
            ]),
        ]

    return [
        ("new", "What's New in Version " + APP_VERSION, [
            f"<b>Media Editor:</b> cut and merge audio and video inside the program, with “ghost” shortcuts that work while you listen in the player ({k('Ctrl+Shift+X')}).",
            f"<b>Radio and live streams:</b> open any link with {k('Ctrl+U')}, and what is on air is announced whenever it changes.",
            f"<b>Saved playlists:</b> gather and arrange your files in the playlist window ({k('Ctrl+L')}) and save them with {k('Ctrl+S')}.",
            f"<b>Equalizer:</b> eighteen presets you cycle with {k('Q')}, and ten bands you can adjust yourself ({k('Ctrl+E')}).",
            "<b>Cleaner recordings:</b> a microphone level slider inside the recorder, noise reduction that really works with any microphone, exclusive mode that works with USB microphones, and your voice mixed with system audio without dropouts.",
            "<b>A smarter converter:</b> “Highest quality” no longer inflates files for nothing, and formats that used to fail at high sample rates now succeed.",
            "<b>A real dark mode</b> across the whole program, and an Arabic interface that reads right to left.",
            "<b>Seek amounts you choose</b> for each modifier key, and fixed, tidy output folders in Documents.",
        ]),
        ("start", "Getting Started", [
            f"<b>Opening files:</b> {k('Ctrl+O')} opens a file, {k('Ctrl+Shift+O')} a whole folder and {k('Ctrl+U')} a link. The File menu also has “Recent Files”.",
            "<b>From Windows Explorer:</b> right-click an audio or video file for “Play” and “Convert” with the program, or a folder to convert everything in it. The program also appears in “Open with”.",
            "<b>Resume:</b> the program remembers where you stopped in each file and picks up from there when you open it again. It also remembers each file's playback speed.",
            f"<b>Folder navigation:</b> opening a file brings in the rest of its folder, so you can move between them with {k('Page Down')} and {k('Page Up')}. In Options you choose what happens when a file ends: nothing, or move on to the next one.",
            "<b>Media keys:</b> the play, stop, next and previous keys on your keyboard control the program even when it is in the background; you can turn this off in Options.",
        ]),
        ("playback", "Playback and Moving Within a File", [
            f"<b>Playback:</b> {k('Space')} plays and pauses, {k('Ctrl+Space')} stops and returns to the start, and {k('M')} mutes.",
            f"<b>Volume:</b> Up and Down Arrow change it in 5% steps, or 20% steps with {k('Ctrl')}.",
            f"<b>Seeking:</b> Right and Left Arrow move {amount['normal']}, with {k('Ctrl')} {amount['ctrl']}, with {k('Shift')} {amount['shift']}, with {k('Alt')} {amount['alt']} and with {k('Ctrl+Shift')} {amount['ctrl_shift']}. You can change any of these amounts in the Playback &amp; Navigation tab of Options.",
            "<b>Continuous seeking:</b> hold Right or Left Arrow and the position keeps moving, faster the longer you hold. The sound is muted until you let go, and then the new position is announced.",
            f"<b>Direct jumps:</b> Numpad 1 to 9 take you to 10% through 90% of the file, {k('Numpad 0')} or {k('Home')} to its start, and {k('End')} to its last five seconds.",
            f"<b>Go to a time:</b> press {k('Ctrl+G')} and type the time: <code>90</code>, <code>1:30</code> or <code>1:02:03</code>. If the time is past the end of the file, you are told instead of being taken to the wrong place.",
            f"<b>Speed:</b> {k('Alt')} with Up or Down Arrow changes it by 0.25, and {k('Alt+Numpad 0')} returns it to normal, without changing the pitch.",
            f"<b>Fullscreen:</b> {k('F11')} shows video fullscreen, and {k('Escape')} leaves it.",
        ]),
        ("announce", "Spoken Announcements and Time", [
            f"<b>Time on demand:</b> {k('T')} gives the current time, {k('R')} the remaining time, and {k('E')} the full duration.",
            f"<b>Master switch:</b> {k('Ctrl+Alt+A')} silences all of the program's announcements at once, and brings them back.",
            "<b>A choice for every announcement:</b> the Accessibility tab has a checkbox for each one: file name and playlist position, resume, playback state, volume and mute, speed, bookmarks, sleep timer, equalizer preset, radio now playing and more. Keep what helps you and silence the rest.",
            "<b>Seeking without chatter:</b> choose the smallest jump after which the new position is announced: every jump, or only jumps of 1, 5, 10 or 30 minutes and more. Numpad jumps and Go to time are always announced.",
            "<b>File information:</b> the program can announce a file's format, quality and duration when it opens, and the loading state if a file is slow to open.",
        ]),
        ("bookmarks", "Bookmarks", [
            f"<b>Add a bookmark</b> anywhere with {k('Ctrl+B')}, move between bookmarks with {k('F2')} and {k('Shift+F2')}, and clear all of a file's bookmarks with {k('Ctrl+Shift+B')}.",
            f"<b>Name a bookmark</b> with {k('Ctrl+Alt+B')}, so you hear “Start of chapter three” instead of “Bookmark at 12 minutes”. Leave the name empty to remove it.",
            "<b>Bookmarks serve the editor too:</b> in the Media Editor you pick times “From Bookmarks” instead of typing them; see the Media Editor section.",
        ]),
        ("streams", "Radio, Links and Playlists", [
            f"<b>Links:</b> {k('Ctrl+U')} opens the link box, already filled in if you have copied a link. The program plays radio, live streams and online files, and reconnects by itself if the stream drops.",
            f"<b>Now playing:</b> on stations that send the song or show name, it is announced whenever it changes, and {k('N')} repeats it whenever you like.",
            f"<b>The playlist window:</b> {k('Ctrl+L')} opens the current playlist: add files, folders or station links, play the selected file with {k('Enter')}, remove it with {k('Delete')}, and move it with {k('Alt')} and Up or Down Arrow.",
            f"<b>Saving and opening playlists:</b> {k('Ctrl+S')} saves the playlist as M3U8, which most players open; if the files are inside the playlist's folder, it keeps working when you move the whole folder. Any M3U, M3U8 or PLS playlist opens like a file with {k('Ctrl+O')}, or from inside the playlist window.",
        ]),
        ("eq", "Equalizer", [
            f"<b>Presets:</b> {k('Q')} and {k('Shift+Q')} cycle eighteen presets, including “Headphones”, “Full Bass” and “Large Hall”, and each name is spoken.",
            f"<b>Manual adjustment:</b> {k('Ctrl+E')} opens a window with a preamp and ten bands that you adjust with Up and Down Arrow, hearing the result immediately. Changing any band makes the preset “Custom”, and “Cancel” restores what you had before opening the window.",
            "<b>It stays:</b> your choice applies to every file and is kept after you close the program.",
        ]),
        ("recorder", "Audio Recorder", [
            f"<b>Opening and quick recording:</b> {k('Ctrl+Shift+R')} opens the recorder. {k('Ctrl+R')} in the main or Recorder window starts recording right away with your last settings, and pressing it again stops and saves. If you close the window while recording, it hides and the recording carries on in the background.",
            "<b>A clean device list:</b> each microphone appears once, with a readable name; the program picks the best connection and settings for it, and keeps each device's settings separately.",
            f"<b>Microphone level:</b> the “Microphone level” slider under the device choice is the same microphone level as in Windows sound settings. Distortion happens inside the microphone before the sound reaches the program, so lowering this level is the real cure. Move it one step at a time with the arrows, or ten steps with {k('Page Up')} and {k('Page Down')}; you can change it while recording. Start at about 70%. If a device doesn't allow its level to be changed, the slider is disabled and the reason appears under it.",
            "<b>Microphone test:</b> a button that records ten seconds, then tells you in text your screen reader can read whether the level is good, too high, too low or silent, along with steps to fix it.",
            f"<b>Level while recording:</b> {k('Ctrl+L')} speaks the current level and highest peak, only when you ask, so the screen reader's voice isn't recorded into the file. If the level is high enough to distort, a warning appears in the window, and when you save you are told how many spots were affected.",
            "<b>Microphone enhancement:</b> “None” keeps the sound exactly as the sound card delivers it. “Clean up” removes low hum (desk bumps, computer fans, handling noise) and prevents clipped peaks without touching speech. “Clean up and reduce steady noise” also lowers hiss, air conditioning, fans and electrical hum: the program measures your own microphone and room while recording and lowers the noise about four times in the pauses, without making your voice sound metallic. Enhancement applies to the microphone only, never to system audio.",
            "<b>Exclusive mode (direct access to the sound card):</b> the program takes the sound straight from the card, bypassing Windows processing, so there are no hidden effects and no mixing with other programs; in return, no other program can use the microphone while you record. Some microphones accept this mode only at their native rate (192000, for example), so the program captures at that rate and converts to the one you chose, and the file keeps its usual size. If the card refuses exclusive mode altogether, you are told and recording continues in normal mode.",
            "<b>Your voice with system audio:</b> turn on “Merge a second input device” and the program picks system audio (Stereo Mix) automatically. The two sources are mixed sample by sample with balanced levels, so your voice doesn't get lost under the music and the recording doesn't break up.",
            "<b>Quality and format:</b> sample rate (48000 covers everything the ear can hear), mono or stereo, 16, 24 or 32 bit, and the format: uncompressed WAV, or much smaller MP3, M4A and others written directly while recording. “Bitrate” starts at “Highest available quality”, which knows each format's ceiling.",
        ]),
        ("editor", "Media Editor", [
            f"<b>Four tasks</b> from the Tools menu or {k('Ctrl+Shift+X')}: “Split a file” in two, “Split several files” at the same time in one go, “Parts of a file” joined in order into one file, and “Merge files” in the order you choose.",
            "<b>No quality loss:</b> the result keeps the source format, and audio is copied as is, without re-encoding. Audio files in different formats are merged by re-encoding them; video files must share the same format and size to be merged, otherwise the editor tells you why.",
            "<b>Two modes for video:</b> “Fast, same quality” starts the cut at the nearest keyframe (a full picture every few seconds) and tells you exactly where it cut; “Exact to the second” cuts at the requested time but takes longer.",
            f"<b>Times without typing:</b> the “Current Position” button takes the time from the player while you listen. Or press {k('Ctrl+B')} at each spot, then pick a time “From Bookmarks”, or press “Parts from Bookmarks” so that every two bookmarks in a row become a part's start and end. Time boxes accept fractions of a second, like <code>1:30.5</code>.",
            f"<b>Ghost shortcuts:</b> they work from anywhere, with the player in front or in the background: set the split point and a part's start and end, add the current file to the split and merge lists, hear what you have set, and start or cancel the work, all without opening the editor window. Turn them on or off with {k('Ctrl+Alt+Shift+G')} or from the Tools menu; you will find them all at the end of this guide. Closing the editor only hides it, so nothing you have set is lost.",
            "<b>Editor settings:</b> in the Media Editor tab of Options: the default video cut mode, how often progress is announced, and any ghost shortcut you want to change; duplicates are refused.",
        ]),
        ("converter", "Format Converter", [
            "<b>Opening:</b> from the Tools menu, or by right-clicking a file or folder in Windows Explorer. It converts a single file or a whole folder in one go, announcing each file's progress and result.",
            "<b>Real source information:</b> codec, resolution, actual bitrate, sample rate and channels, so you know what you are converting before you start.",
            "<b>Highest quality, done wisely:</b> “Highest available quality” knows each format's ceiling (320 kbps for MP3, 640 for AC3, 256 for mono Opus) and never exceeds the quality of a compressed source, so files don't grow for nothing. If you pick a number above what a format allows, the program uses its maximum instead of failing, and it does the same with unsupported sample rates.",
            "<b>Advanced settings:</b> sample rate and channels for audio; constant quality (CRF) or constant bitrate, resolution and frame rate for video. Their defaults are in the Converter tab of Options.",
        ]),
        ("folders", "Where Your Files Are Saved", [
            "In Documents, a folder named after the program holds “Recordings”, “Converted Files” and “Media Editor”, which contains “Audio” and “Video”.",
            "These folders are named once, in the program's language, the first time it runs, and are never renamed afterwards; if a name is already taken, a number is added. Folders from previous versions are merged into them automatically.",
            "When a recording is saved, the program tells you its length and where it was saved.",
        ]),
        ("options", "Options and Customization", [
            f"<b>Options</b> open with {k('Ctrl+Shift+P')} and have six tabs, which you switch with {k('Ctrl+Tab')} or {k('Ctrl+1')} to {k('Ctrl+6')}: General, Playback &amp; Navigation, Accessibility, Converter, Recorder and Media Editor.",
            "<b>Appearance:</b> Follow Windows, Light or Dark. Dark covers menus, title bars and every window, and takes effect after you reopen the program. In high contrast mode the program always uses Windows' colours.",
            "<b>Language:</b> Arabic, with a right-to-left interface, or English; it takes effect after a restart.",
            "<b>Also in General:</b> the number of recent files, a gentle chime when a conversion or recording finishes, media keys, and two buttons that open Windows' Default Apps and Microphone Privacy settings.",
            "<b>Sleep timer:</b> from the Tools menu, stops playback after a number of minutes you set, or at the end of the current file. Choose zero to cancel it.",
            "<b>Moving your settings:</b> “Export Settings” and “Import Settings” in the Tools menu, for a new computer or a backup.",
            f"<b>Windows:</b> {k('Escape')} closes any tool window, and the main window opens with the size and position you left it in.",
        ]),
        ("help", "When Something Goes Wrong", [
            f"<b>Diagnostic report:</b> {k('Ctrl+Shift+D')} saves a text file to your Desktop with system information and the program log, and <b>no personal information</b>: no computer name, user name or file paths, so you can post it in a public group with peace of mind.",
            "<b>Microphone test details:</b> the test result has a “Copy technical details” button that copies a single line free of anything that identifies you, ready to paste into a support message.",
            "<b>No sound from the microphone:</b> make sure Windows allows apps to use the microphone; the “Microphone Privacy” button in the General tab opens that setting directly. If another program is holding the microphone in exclusive mode, close it and try again.",
        ]),
        ("license", "License", [
            "The program is free software under the GNU GPL version 3: you may use, copy, modify and distribute it under its terms, and it comes with no warranty.",
            "The license text and the licenses of the bundled libraries are in the LICENSE and THIRD-PARTY.md files and the licenses folder next to the program.",
        ]),
    ]


# تسلسل مفاتيح لاتيني داخل سطر عربي: «Ctrl + Tab» و«Numpad 1» و«F11»
_KEY_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 +./]*[A-Za-z0-9]|[A-Za-z0-9]")
# وداخل سطر إنجليزي فيه كلام («hold Right / Left Arrow»): كلمات بحرف كبير
# أو أرقام، بينها + أو / أو مسافة
_EN_KEY_RUN = re.compile(
    r"(?:[A-Z][A-Za-z0-9]*|\d+)(?:\s*[+/]\s*(?:[A-Z][A-Za-z0-9]*|\d+)|\s+(?=[A-Z0-9])(?:[A-Z][A-Za-z0-9]*|\d+))*")


def _has_arabic(text):
    return any("؀" <= ch <= "ۿ" for ch in text)


def _keys_html(keys):
    """
    خانة المفاتيح في جدول الاختصارات.

    مفاتيح وحدها: <kbd> واحد من اليسار لليمين. ومعها كلام عربي («أو»
    و«إلى» و«من قائمة أدوات»): الكلام بخطه العادي من اليمين، وكل تسلسل
    مفاتيح في <kbd> وحده؛ بخط الأكواد كانت الحروف العربية مفكّكة.
    """
    arabic = _has_arabic(keys)
    if not arabic and not re.search(r"\b[a-z]{3,}\b", keys):
        return f'<kbd dir="ltr">{escape(keys)}</kbd>'
    parts, last = [], 0
    for match in (_KEY_RUN if arabic else _EN_KEY_RUN).finditer(keys):
        parts.append(escape(keys[last:match.start()]))
        parts.append(f'<kbd dir="ltr">{escape(match.group())}</kbd>')
        last = match.end()
    parts.append(escape(keys[last:]))
    direction = "rtl" if arabic else "ltr"
    return f'<span class="mixed-keys" dir="{direction}">{"".join(parts)}</span>'


def _shortcuts_html(lines):
    """جدول الاختصارات: عنوان فرعي لكل قسم، وسطر لكل اختصار."""
    html = []
    open_list = False
    for line in lines:
        if not line:
            continue
        if line.startswith("==="):
            if open_list:
                html.append("</ul>")
            html.append(f"<h3>{escape(line.strip('= ').strip())}</h3>")
            html.append('<ul class="keys">')
            open_list = True
            continue
        if not open_list:
            html.append('<ul class="keys">')
            open_list = True
        if ":" in line:
            desc, keys = line.split(":", 1)
            html.append(f"<li><span>{escape(desc.strip())}</span> {_keys_html(keys.strip())}</li>")
        else:
            html.append(f"<li>{escape(line)}</li>")
    if open_list:
        html.append("</ul>")
    return "\n".join(html)


def build_user_guide_html(tr, seek_kwargs: dict = None, shortcuts_kwargs: dict = None) -> str:
    """
    صفحة الدليل كاملة.

    seek_kwargs بقي للتوافق مع من يناديها؛ مقادير التقديم تؤخذ من
    shortcuts_kwargs["seek_steps"] (ما ضبطه المستخدم)، وإلا فالافتراضية.
    """
    lang = "ar" if getattr(tr, "lang", "ar") == "ar" else "en"
    is_ar = lang == "ar"
    shortcuts_kwargs = shortcuts_kwargs or {}
    steps = dict(_SEEK_DEFAULTS)
    steps.update(shortcuts_kwargs.get("seek_steps") or {})

    app_name = tr.t("app_title")
    title = f"{tr.t('menu_user_guide')} — {app_name}"
    sections = _sections(lang, steps)
    shortcuts_id = "shortcuts"
    shortcuts_title = "خريطة اختصارات لوحة المفاتيح" if is_ar else "Keyboard Shortcuts Map"
    toc_title = "المحتويات" if is_ar else "Contents"
    version_label = (f"الإصدار {APP_VERSION}" if is_ar else f"Version {APP_VERSION}")
    intro = (
        f"{escape(app_name)} مشغّل للصوت والفيديو صُمّم ليُستعمل كله من لوحة المفاتيح ومع قارئ الشاشة، "
        "ومعه مسجّل للصوت ومحول للصيغ ومحرر للقص والدمج. كل ما يُرى في البرنامج يُسمع أيضًا، وأنت من "
        "يقرر متى يُقال. في هذا الدليل شرح كل ميزة وكل اختصار، وتساعدك العناوين على التنقل بالمفتاح H في قارئ الشاشة."
        if is_ar else
        f"{escape(app_name)} is an audio and video player designed to be used entirely from the keyboard and with a "
        "screen reader, together with an audio recorder, a format converter and an editor for cutting and merging. "
        "Everything you can see in the program can also be heard, and you decide when it is said. This guide explains "
        "every feature and every shortcut, and its headings let you move around with H in your screen reader."
    )

    toc = "\n".join(
        f'<li><a href="#{sid}">{escape(stitle)}</a></li>' for sid, stitle, _items in sections
    ) + f'\n<li><a href="#{shortcuts_id}">{escape(shortcuts_title)}</a></li>'

    body = []
    for sid, stitle, items in sections:
        css = ' class="whats-new"' if sid == "new" else ""
        body.append(f'<section id="{sid}"{css}>')
        body.append(f"<h2>{escape(stitle)}</h2>")
        body.append("<ul>")
        body.extend(f"<li>{item}</li>" for item in items)
        body.append("</ul>")
        body.append("</section>")

    raw_shortcuts = get_shortcuts_list(lang, **shortcuts_kwargs)

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
    :root {{
        --bg: #f3f5f8;
        --card: #ffffff;
        --text: #1f2933;
        --muted: #52606d;
        --accent: #1f6fb2;
        --accent-soft: #e6f0fa;
        --border: #dde3ea;
        --kbd-bg: #eef3f8;
        --kbd-border: #b8c6d6;
        --new-bg: #f0f7ef;
        --new-border: #3d8b40;
    }}
    @media (prefers-color-scheme: dark) {{
        :root {{
            --bg: #15181d;
            --card: #1e232a;
            --text: #e4e8ee;
            --muted: #a3adb9;
            --accent: #6fb3f2;
            --accent-soft: #23303d;
            --border: #333b45;
            --kbd-bg: #29313b;
            --kbd-border: #4a5665;
            --new-bg: #1f2c22;
            --new-border: #6cc070;
        }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        padding: 32px 16px;
        background: var(--bg);
        color: var(--text);
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
        font-size: 16px;
        line-height: 1.85;
    }}
    main {{
        max-width: 920px;
        margin: 0 auto;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 36px 40px;
    }}
    header {{ border-bottom: 3px solid var(--accent); margin-bottom: 24px; padding-bottom: 12px; }}
    h1 {{ margin: 0; font-size: 28px; color: var(--accent); }}
    .version {{ color: var(--muted); margin: 4px 0 0; }}
    .intro {{ font-size: 17px; }}
    nav {{ background: var(--accent-soft); border-radius: 8px; padding: 14px 22px; margin: 24px 0; }}
    nav h2 {{ margin: 0 0 6px; font-size: 18px; border: none; padding: 0; }}
    nav ol {{ margin: 0; padding-inline-start: 22px; columns: 2; column-gap: 32px; }}
    nav a {{ color: var(--accent); text-decoration: none; }}
    nav a:hover, nav a:focus {{ text-decoration: underline; }}
    h2 {{
        font-size: 21px;
        margin: 36px 0 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border);
        color: var(--accent);
    }}
    h3 {{ font-size: 17px; margin: 22px 0 6px; color: var(--text); }}
    section ul {{ padding-inline-start: 22px; margin: 0; }}
    section li {{ margin-bottom: 10px; }}
    .whats-new {{
        background: var(--new-bg);
        border-inline-start: 5px solid var(--new-border);
        border-radius: 8px;
        padding: 4px 22px 10px;
    }}
    .whats-new h2 {{ border: none; color: var(--new-border); }}
    ul.keys {{ list-style: none; padding: 0; margin: 0; border: 1px solid var(--border); border-radius: 8px; }}
    ul.keys li {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        padding: 8px 14px;
        margin: 0;
        border-bottom: 1px solid var(--border);
    }}
    ul.keys li:last-child {{ border-bottom: none; }}
    kbd {{
        background: var(--kbd-bg);
        border: 1px solid var(--kbd-border);
        border-radius: 4px;
        padding: 1px 7px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 14px;
        white-space: nowrap;
        direction: ltr;
        unicode-bidi: isolate;
    }}
    .combo {{ unicode-bidi: isolate; white-space: nowrap; }}
    ul.keys kbd {{ white-space: normal; text-align: end; }}
    .mixed-keys {{ text-align: end; }}
    .mixed-keys kbd {{ white-space: nowrap; }}
    code {{ font-family: Consolas, monospace; direction: ltr; unicode-bidi: isolate; }}
    @media (max-width: 640px) {{
        main {{ padding: 22px 18px; }}
        nav ol {{ columns: 1; }}
        ul.keys li {{ flex-direction: column; gap: 2px; }}
    }}
</style>
</head>
<body>
<main>
<header>
    <h1>{escape(title)}</h1>
    <p class="version">{escape(version_label)}</p>
</header>
<p class="intro">{intro}</p>
<nav aria-labelledby="toc-title">
    <h2 id="toc-title">{toc_title}</h2>
    <ol>
{toc}
    </ol>
</nav>
{chr(10).join(body)}
<section id="{shortcuts_id}">
<h2>{escape(shortcuts_title)}</h2>
{_shortcuts_html(raw_shortcuts)}
</section>
</main>
</body>
</html>"""
