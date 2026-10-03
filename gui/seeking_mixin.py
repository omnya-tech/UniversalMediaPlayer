# -*- coding: utf-8 -*-
"""
القفز داخل الملف: المطلق، والنسبي، والمؤجَّل.

اتفصل عن gui/main_window.py لما الملف عدّى حدّه المرسوم. المجموعة دي
متماسكة بذاتها: كلها بتحسب موضعًا وتوديه للمحرك وتعلنه.
"""

import time

from core.engine import PlaybackState


class SeekingMixin:

    def _perform_seek(self, target: float):
        if self.engine.state in (PlaybackState.ENDED, PlaybackState.STOPPED):
            self.engine.play_and_seek(target)
        else:
            self.engine.seek(target)

    def _defer_until_duration_known(self, action):
        """
        يأجّل قفزة محتاجة المدة لحد ما الملف يجهّز.

        القفزات دي (End وHome وأرقام النم باد) بتحسب هدفها من طول الملف.
        لو المستخدم ضغطها والملف لسه بيتحمّل - وده بيحصل كتير بعد
        PageDown أو بعد ما ملف يخلص وينتقل للي بعده - المدة لسه مش
        معروفة، وقبل كده كانت الضغطة بتترمي في صمت. المستخدم بيسمع ولا
        بيشوف، فالصمت عنده معناه "الاختصار باظ".

        الحفظ أقرب لنيّته: هو طالب آخر الملف الجديد، فبنوصّله له أول ما
        يبقى ممكن. والطلب الأحدث بيلغي اللي قبله.
        """
        # يرجع True لو اتأجّلت، فالمستدعي يخرج ويسيبها تتنفّذ بعدين
        if not self._is_loading_file and self.engine.duration:
            return False
        self._pending_seek_action = action
        return True

    def _run_pending_seek(self):
        action = getattr(self, "_pending_seek_action", None)
        if action is None:
            return
        self._pending_seek_action = None
        if self.engine.duration:
            action()

    def _seek_to_start(self):
        self._perform_seek(0)
        self._announce_seek(0, seek_type="numpad")

    def _seek_to_near_end(self):
        if self._defer_until_duration_known(self._seek_to_near_end):
            return
        target = max(0.0, self.engine.duration - 5.0)
        self._perform_seek(target)
        self._announce_seek(target, seek_type="numpad")

    def _seek_to_percent(self, percent: int):
        if self._defer_until_duration_known(lambda: self._seek_to_percent(percent)):
            return
        target = self.engine.duration * (percent / 100.0)
        self._perform_seek(target)
        self._announce_seek(target, seek_type="numpad")

    def _seek_relative(self, delta_seconds):
        # المدة تُقرأ مرة واحدة: قراءتها من المحرك أكثر من مرة قد تعطي
        # قيمًا مختلفة لو تغيّر الملف في الأثناء
        duration = self.engine.duration
        current = self.engine.get_effective_position()
        target = current + delta_seconds
        clamped = max(0.0, min(target, duration)) if duration else max(0.0, target)
        self.engine.seek(clamped)
        self._last_seek_time = time.time()
        if duration > 0:
            self.seek_slider.SetValue(int(clamped))
        self._update_info_labels(is_seeking=True, seek_target=clamped)
        seek_type = "seconds" if abs(delta_seconds) <= self.SEEK_NORMAL_SECONDS else "minutes"
        self._announce_seek(clamped, seek_type=seek_type, jump_seconds=delta_seconds)
