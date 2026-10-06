# -*- coding: utf-8 -*-
"""
الاختصارات الشبحية لمحرر الوسائط.

اختصارات عامة (RegisterHotKey) تعمل من أي مكان، حتى والمشغّل في الخلفية
والمستخدم في برنامج آخر: وهو يسمع يحدد نقطة القص، أو بداية مقطع ونهايته،
أو يضيف الملف لقائمة، من غير أن يفتح المحرر. الموضع يؤخذ من المشغّل.

الافتراضي Ctrl+Alt+Shift مع حرف: تركيبة نادرًا ما يستخدمها برنامج آخر،
ولا يستخدمها NVDA في وضعه الافتراضي. والمستخدم يغيّر أي اختصار من
الخيارات (تبويب محرر الوسائط) باختيار المفاتيح المساعدة والمفتاح من
قائمتين. مفتاح التشغيل والإيقاف مسجّل دائمًا ليبقى الوصول إليه ممكنًا
والبقية معطلة؛ والبقية تُسجَّل فقط وهي مفعّلة، فلا تحجز مفاتيح عن
البرامج الأخرى بلا داعٍ.
"""

import logging

import wx

logger = logging.getLogger(__name__)

# (الاسم المحفوظ، القيمة لـ RegisterHotKey، النص المعروض)
# كلها فيها مفتاحان مساعدان على الأقل: مساعد واحد (مثل Ctrl+S) يخطف
# اختصارات البرامج الأخرى الشائعة في كل مكان
MODIFIER_CHOICES = (
    ("ctrl+alt+shift", wx.MOD_CONTROL | wx.MOD_ALT | wx.MOD_SHIFT, "Ctrl+Alt+Shift"),
    ("ctrl+alt", wx.MOD_CONTROL | wx.MOD_ALT, "Ctrl+Alt"),
    ("ctrl+shift", wx.MOD_CONTROL | wx.MOD_SHIFT, "Ctrl+Shift"),
    ("alt+shift", wx.MOD_ALT | wx.MOD_SHIFT, "Alt+Shift"),
    ("ctrl+win", wx.MOD_CONTROL | wx.MOD_WIN, "Ctrl+Win"),
    ("alt+win", wx.MOD_ALT | wx.MOD_WIN, "Alt+Win"),
)


def _key_choices():
    keys = [(chr(c), ord(chr(c))) for c in range(ord("A"), ord("Z") + 1)]
    keys += [(str(d), ord(str(d))) for d in range(10)]
    keys += [(f"F{n}", getattr(wx, f"WXK_F{n}")) for n in range(1, 13)]
    keys += [("Enter", wx.WXK_RETURN), ("Space", wx.WXK_SPACE), ("Backspace", wx.WXK_BACK),
             ("Insert", wx.WXK_INSERT), ("Delete", wx.WXK_DELETE), ("Home", wx.WXK_HOME),
             ("End", wx.WXK_END), ("PageUp", wx.WXK_PAGEUP), ("PageDown", wx.WXK_PAGEDOWN)]
    return tuple(keys)


# (الاسم المحفوظ والمعروض، القيمة لـ RegisterHotKey)
KEY_CHOICES = _key_choices()
_MODIFIERS = {name: (code, label) for name, code, label in MODIFIER_CHOICES}
_KEYS = dict(KEY_CHOICES)

# الأفعال بترتيب عرضها، واختصار كل منها الافتراضي
DEFAULT_HOTKEYS = (
    ("toggle", ("ctrl+alt+shift", "G")),
    ("open", ("ctrl+alt+shift", "O")),
    ("split", ("ctrl+alt+shift", "S")),
    ("start", ("ctrl+alt+shift", "B")),
    ("end", ("ctrl+alt+shift", "E")),
    ("undo", ("ctrl+alt+shift", "Z")),
    ("split_many", ("ctrl+alt+shift", "L")),
    ("merge", ("ctrl+alt+shift", "M")),
    ("status", ("ctrl+alt+shift", "I")),
    ("run", ("ctrl+alt+shift", "Enter")),
    ("cancel", ("ctrl+alt+shift", "C")),
)
ACTIONS = tuple(action for action, _combo in DEFAULT_HOTKEYS)
_DEFAULTS = dict(DEFAULT_HOTKEYS)

_ID_BASE = 0xB320
_IDS = {action: _ID_BASE + index for index, action in enumerate(ACTIONS)}
_ACTIONS = {hotkey_id: action for action, hotkey_id in _IDS.items()}


def current_hotkeys(settings):
    """{الفعل: (المساعدة، المفتاح)} من الإعدادات، والافتراضي لما لا يصلح."""
    mapping = {}
    for action in ACTIONS:
        combo = settings.get_editor_hotkey(action) if settings is not None else None
        if not combo or combo[0] not in _MODIFIERS or combo[1] not in _KEYS:
            combo = _DEFAULTS[action]
        mapping[action] = tuple(combo)
    return mapping


def combo_text(combo):
    """النص المعروض لاختصار، مثل Ctrl+Alt+Shift+G."""
    modifiers, key = combo
    return f"{_MODIFIERS[modifiers][1]}+{key}"


def find_duplicates(mapping):
    """قائمة أزواج الأفعال التي تشترك في نفس الاختصار."""
    seen, duplicates = {}, []
    for action in ACTIONS:
        combo = tuple(mapping[action])
        if combo in seen:
            duplicates.append((seen[combo], action))
        else:
            seen[combo] = action
    return duplicates


def hotkeys_help_text(tr, mapping=None):
    """قائمة الاختصارات للعرض، سطر لكل اختصار."""
    mapping = mapping or dict(DEFAULT_HOTKEYS)
    return "\n".join(
        tr.t("ghost_help_line", keys=combo_text(mapping[action]), action=tr.t(f"ghost_action_{action}"))
        for action in ACTIONS
    )


class EditorHotkeysMixin:
    """
    تسجيل الاختصارات الشبحية في النافذة الرئيسية وتنفيذها.

    يعتمد على ToolsMixin._ensure_media_editor لإنشاء المحرر (مخفيًّا لو
    لم يكن مفتوحًا)، وعلى self._announce للإعلان.
    """

    def _init_editor_hotkeys(self):
        self._editor_hotkey_ids = set()
        self._register_editor_hotkeys()

    def editor_hotkey_text(self, action):
        return combo_text(current_hotkeys(self.settings)[action])

    def _register_editor_hotkeys(self):
        enabled = self.settings.get_enable_editor_hotkeys()
        mapping = current_hotkeys(self.settings)
        failed = []
        for action in ACTIONS:
            if action != "toggle" and not enabled:
                continue
            hotkey_id = _IDS[action]
            if hotkey_id in self._editor_hotkey_ids:
                continue
            modifiers, key = mapping[action]
            try:
                registered = self.RegisterHotKey(hotkey_id, _MODIFIERS[modifiers][0], _KEYS[key])
            except Exception:
                registered = False
            if registered:
                self._editor_hotkey_ids.add(hotkey_id)
            else:
                failed.append(combo_text(mapping[action]))
        if failed:
            # برنامج آخر حجز التركيبة؛ المستخدم يعرف أيها لا يعمل
            logger.warning("Editor hotkeys already taken: %s", ", ".join(failed))
        return failed

    def _unregister_editor_hotkeys(self, keep_toggle=False):
        for hotkey_id in list(self._editor_hotkey_ids):
            if keep_toggle and hotkey_id == _IDS["toggle"]:
                continue
            try:
                self.UnregisterHotKey(hotkey_id)
            except Exception:
                pass
            self._editor_hotkey_ids.discard(hotkey_id)

    def reload_editor_hotkeys(self):
        """بعد تغيير الاختصارات في الخيارات: يسجّلها من جديد ويحدّث ما يعرضها."""
        self._unregister_editor_hotkeys()
        failed = self._register_editor_hotkeys()
        self._refresh_editor_hotkeys_ui()
        if failed:
            self._announce(self.tr.t("ghost_failed", keys="، ".join(failed)), force=True)

    def _refresh_editor_hotkeys_ui(self):
        enabled = self.settings.get_enable_editor_hotkeys()
        item = getattr(self, "_editor_hotkeys_menu_item", None)
        if item:
            item.SetItemLabel(self.tr.t("menu_editor_hotkeys", keys=self.editor_hotkey_text("toggle")))
            item.Check(enabled)
        editor = getattr(self, "_media_editor_dialog", None)
        if editor:
            editor.set_hotkeys_checkbox(enabled)

    def is_editor_hotkey(self, hotkey_id):
        return hotkey_id in _ACTIONS

    def set_editor_hotkeys_enabled(self, enabled):
        """من القائمة، أو خانة المحرر، أو مفتاح التشغيل والإيقاف."""
        self.settings.set_enable_editor_hotkeys(enabled)
        if enabled:
            failed = self._register_editor_hotkeys()
        else:
            self._unregister_editor_hotkeys(keep_toggle=True)
            failed = []
        self._refresh_editor_hotkeys_ui()
        if enabled:
            message = self.tr.t("ghost_on")
        else:
            message = self.tr.t("ghost_off", keys=self.editor_hotkey_text("toggle"))
        if failed:
            message += " " + self.tr.t("ghost_failed", keys="، ".join(failed))
        self._announce(message, force=True)

    def _on_editor_hotkeys_menu(self, event):
        self.set_editor_hotkeys_enabled(event.IsChecked())

    def _player_file_position(self):
        """(ملف المشغّل، موضعه) أو None لو لا ملف محلي مفتوح."""
        from core.streams import is_stream_url

        path = self._current_file_path
        if not path or is_stream_url(path):
            return None
        return path, self.engine.get_effective_position()

    def _on_editor_hotkey(self, hotkey_id):
        action = _ACTIONS.get(hotkey_id)
        if action == "toggle":
            self.set_editor_hotkeys_enabled(not self.settings.get_enable_editor_hotkeys())
            return
        if action == "open":
            self._on_media_editor(None)
            return

        # المحرر الذي تنشئه الاختصارات يبدأ فارغًا: لا يُضاف ملف المشغّل
        # لقوائمه إلا بطلب صريح
        editor = self._ensure_media_editor(load_current=False)
        if action in ("status", "run", "cancel", "undo"):
            message = {
                "status": editor.ghost_status,
                "run": editor.ghost_run,
                "cancel": editor.ghost_cancel,
                "undo": editor.ghost_undo_segment,
            }[action]()
            self._announce(message, force=True)
            return

        current = self._player_file_position()
        if current is None:
            self._announce(self.tr.t("ghost_no_file"), force=True)
            return
        path, position = current
        from gui.media_editor_dialog import PAGE_MERGE, PAGE_SPLIT_MANY

        if action == "split":
            message = editor.ghost_set_split(path, position)
        elif action == "start":
            message = editor.ghost_segment_start(path, position)
        elif action == "end":
            message = editor.ghost_segment_end(path, position)
        elif action == "split_many":
            message = editor.ghost_add_to_list(PAGE_SPLIT_MANY, path)
        else:
            message = editor.ghost_add_to_list(PAGE_MERGE, path)
        self._announce(message, force=True)
