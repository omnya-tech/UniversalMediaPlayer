# -*- coding: utf-8 -*-
"""
التقديم بالسهمين: الضغطة الواحدة بالمقدار المضبوط بالضبط، والضغط المطوّل يتسارع.

الدوال تُنادى على كائن بديل للنافذة، فلا تُفتح نافذة ولا يُشغَّل ملف.
"""

import pytest

wx = pytest.importorskip("wx")

from gui.main_window import MainWindow


class _Engine:
    duration = 3600.0

    def __init__(self, position):
        self.position = position
        self.sought = None
        self.muted = False

    def get_effective_position(self):
        return self.position

    def set_muted(self, muted):
        self.muted = muted

    def seek(self, position):
        self.sought = position


class _Stub:
    """أقل ما تحتاجه دوال التقديم من النافذة."""

    def __init__(self, position=600.0):
        self.engine = _Engine(position)
        self._is_holding_seek = False
        self._holding_key = None
        self._seek_speed_multiplier = 1.0
        self._hold_target_position = None
        self._hold_start_position = None
        self._last_seek_time = 0.0
        self.announced = []
        self.seek_slider = type("Slider", (), {"SetValue": lambda self, value: None})()
        self._hold_seek_timer = type("Timer", (), {"Start": lambda self, ms: None,
                                                   "Stop": lambda self: None})()

    def _update_info_labels(self, **kwargs):
        pass

    def _announce_seek(self, target, seek_type="seconds", jump_seconds=None):
        self.announced.append(jump_seconds)

    _step_hold_seek = MainWindow._step_hold_seek
    _start_hold_seek = MainWindow._start_hold_seek
    _stop_hold_seek = MainWindow._stop_hold_seek


@pytest.mark.parametrize("step", [10, 5, 30, -10])
def test_single_tap_moves_exactly_the_set_amount(step):
    """كانت الضغطة الواحدة تقفز 12.5 ثانية بدل 10: المعامل يكبر قبل الخطوة الأولى."""
    window = _Stub(position=600.0)
    window._start_hold_seek(wx.WXK_RIGHT, step)
    window._stop_hold_seek()
    assert window.engine.sought == pytest.approx(600.0 + step)
    assert window.announced == [pytest.approx(step)]
    assert window.engine.muted is False


def test_holding_still_speeds_up():
    """كل خطوة من خطوات الضغط المطوّل أكبر من التي قبلها."""
    window = _Stub(position=600.0)
    window._start_hold_seek(wx.WXK_RIGHT, 10)
    positions = [window._hold_target_position]
    for _ in range(6):
        window._step_hold_seek(1.5)
        positions.append(window._hold_target_position)
    steps = [b - a for a, b in zip(positions, positions[1:])]
    assert all(later > earlier for earlier, later in zip(steps, steps[1:]))
    assert positions[0] == pytest.approx(610.0)
