# -*- coding: utf-8 -*-
"""그룹/탭 전환 단축키 지원 믹스인.

일반 탭 위젯에서 Ctrl+Tab 은 "다음 탭"으로 넘어가지만, 그룹탭에서는
탭이 아니라 **그룹 단위**로 넘어가는 것이 자연스럽다. 그래서 기본값으로

- ``Ctrl+Tab`` / ``Ctrl+Shift+Tab`` -> 다음/이전 **그룹**으로 전환
  (그 그룹에서 마지막으로 보던 탭으로 복귀)
- ``F1`` / ``Shift+F1``            -> **같은 그룹 안에서** 다음/이전 탭으로 순환

이 두 벌의 단축키를 등록한다. GroupTabBar / GroupTabWidget 이 함께 쓴다.

QTabWidget 은 자체적으로 Ctrl+Tab 을 "다음 탭"으로 처리하지만, QShortcut 은
키 이벤트가 위젯에 전달되기 전에 먼저 처리되므로 여기서 등록한 그룹 전환이
우선한다.
"""

from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

try:  # Qt6 에서는 QShortcut 이 QtGui 로 옮겨졌다.
    from qtpy.QtGui import QShortcut
except ImportError:  # pragma: no cover - Qt5 경로
    from qtpy.QtWidgets import QShortcut


class SwitchShortcutMixin(object):
    """그룹/탭 전환 단축키를 붙여 주는 믹스인.

    이 믹스인을 쓰는 클래스는 ``nextGroup()`` / ``previousGroup()`` /
    ``nextTabInGroup()`` / ``previousTabInGroup()`` 를 제공해야 한다.
    """

    # 기본 단축키
    DEFAULT_GROUP_KEYS = ("Ctrl+Tab", "Ctrl+Shift+Tab")   # 다음/이전 그룹
    DEFAULT_TAB_KEYS = ("F1", "Shift+F1")                 # 그룹 내 다음/이전 탭

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #
    def _init_switch_shortcuts(self, group_enabled=True, tab_enabled=True):
        """단축키 상태를 초기화하고 등록한다. (생성자에서 한 번 호출)"""
        self._group_keys = tuple(self.DEFAULT_GROUP_KEYS)
        self._tab_keys = tuple(self.DEFAULT_TAB_KEYS)
        # 기본 문맥: 이 위젯이나 그 자식에 포커스가 있을 때만 동작.
        # (창 전체에서 받으려면 Qt.WindowShortcut 으로 바꾼다)
        self._shortcut_context = Qt.WidgetWithChildrenShortcut
        self._group_shortcut_on = bool(group_enabled)
        self._tab_shortcut_on = bool(tab_enabled)
        self._switch_shortcuts = []
        self._rebuild_switch_shortcuts()

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def setGroupSwitchShortcutEnabled(self, enabled):
        """그룹 전환 단축키(기본 Ctrl+Tab / Ctrl+Shift+Tab)를 켜고 끈다."""
        enabled = bool(enabled)
        if enabled != self._group_shortcut_on:
            self._group_shortcut_on = enabled
            self._rebuild_switch_shortcuts()

    def groupSwitchShortcutEnabled(self):
        """그룹 전환 단축키가 켜져 있는지 반환한다."""
        return self._group_shortcut_on

    def setTabSwitchShortcutEnabled(self, enabled):
        """그룹 내 탭 전환 단축키(기본 F1 / Shift+F1)를 켜고 끈다."""
        enabled = bool(enabled)
        if enabled != self._tab_shortcut_on:
            self._tab_shortcut_on = enabled
            self._rebuild_switch_shortcuts()

    def tabSwitchShortcutEnabled(self):
        """그룹 내 탭 전환 단축키가 켜져 있는지 반환한다."""
        return self._tab_shortcut_on

    def setGroupSwitchKeys(self, next_key, prev_key=None):
        """그룹 전환 단축키를 바꾼다. (문자열 또는 QKeySequence)

        예: ``setGroupSwitchKeys("Ctrl+PgDown", "Ctrl+PgUp")``
        ``None`` 을 주면 그 방향의 단축키는 등록하지 않는다.
        """
        self._group_keys = (next_key, prev_key)
        self._rebuild_switch_shortcuts()

    def groupSwitchKeys(self):
        """현재 그룹 전환 단축키 (next, prev) 를 반환한다."""
        return self._group_keys

    def setTabSwitchKeys(self, next_key, prev_key=None):
        """그룹 내 탭 전환 단축키를 바꾼다. (문자열 또는 QKeySequence)"""
        self._tab_keys = (next_key, prev_key)
        self._rebuild_switch_shortcuts()

    def tabSwitchKeys(self):
        """현재 그룹 내 탭 전환 단축키 (next, prev) 를 반환한다."""
        return self._tab_keys

    def setSwitchShortcutContext(self, context):
        """단축키가 동작하는 범위를 정한다.

        Args:
            context: ``Qt.WidgetWithChildrenShortcut``(기본, 이 위젯과 그
                자식에 포커스가 있을 때) / ``Qt.WindowShortcut``(창 전체) /
                ``Qt.ApplicationShortcut``(앱 전체).
        """
        if context != self._shortcut_context:
            self._shortcut_context = context
            self._rebuild_switch_shortcuts()

    def switchShortcutContext(self):
        """단축키 동작 범위를 반환한다."""
        return self._shortcut_context

    # ------------------------------------------------------------------ #
    # 내부 구현
    # ------------------------------------------------------------------ #
    @staticmethod
    def _key_variants(key):
        """키 시퀀스와, Tab 계열이면 Backtab 변형까지 함께 돌려준다.

        Shift+Tab 은 플랫폼/바인딩에 따라 Key_Backtab 으로 들어오는 경우가
        있어, 둘 다 등록해 두면 안전하다.
        """
        if key is None:
            return []
        seq = key if isinstance(key, QKeySequence) else QKeySequence(key)
        if seq.isEmpty():
            return []
        out = [seq]
        text = seq.toString()
        if text.endswith("Tab") and not text.endswith("Backtab"):
            alt = QKeySequence(text[:-len("Tab")] + "Backtab")
            if not alt.isEmpty():
                out.append(alt)
        return out

    def _rebuild_switch_shortcuts(self):
        """등록된 단축키를 모두 지우고 현재 설정대로 다시 만든다."""
        for sc in self._switch_shortcuts:
            sc.setParent(None)
            sc.deleteLater()
        self._switch_shortcuts = []

        specs = []
        if self._group_shortcut_on:
            specs.append((self._group_keys[0], self._on_shortcut_next_group))
            specs.append((self._group_keys[1], self._on_shortcut_prev_group))
        if self._tab_shortcut_on:
            specs.append((self._tab_keys[0], self._on_shortcut_next_tab))
            specs.append((self._tab_keys[1], self._on_shortcut_prev_tab))

        for key, slot in specs:
            for seq in self._key_variants(key):
                sc = QShortcut(seq, self)
                sc.setContext(self._shortcut_context)
                sc.activated.connect(slot)
                self._switch_shortcuts.append(sc)

    # 단축키 슬롯: 인자 없이 호출되도록 감싼다.
    def _on_shortcut_next_group(self):
        self.nextGroup()

    def _on_shortcut_prev_group(self):
        self.previousGroup()

    def _on_shortcut_next_tab(self):
        self.nextTabInGroup()

    def _on_shortcut_prev_tab(self):
        self.previousTabInGroup()
