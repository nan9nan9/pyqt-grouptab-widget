# -*- coding: utf-8 -*-
"""그룹/탭 전환 단축키 지원 믹스인.

일반 탭 위젯에서 Ctrl+Tab 은 "다음 탭"으로 넘어가지만, 그룹탭에서는
탭이 아니라 **그룹 단위**로 넘어가는 것이 자연스럽다. 그래서 기본값으로

- ``Ctrl+Tab`` / ``Ctrl+Shift+Tab`` -> 다음/이전 **그룹**으로 전환
  (그 그룹에서 마지막으로 보던 탭으로 복귀)
- ``F1`` / ``Shift+F1``            -> **같은 그룹 안에서** 다음/이전 탭으로 순환

이 두 벌의 단축키를 등록한다. GroupTabBar / GroupTabWidget 이 함께 쓴다.

처리 방식(중요)
---------------
기본값(``Qt.WidgetWithChildrenShortcut``)에서는 QShortcut 을 만들지 않고
**키 이벤트(keyPressEvent)** 로 처리한다. QShortcut 으로 등록하면 앱이 이미
같은 키(예: F1)를 쓰고 있을 때 Qt 가 "ambiguous shortcut" 으로 보고 어느 쪽도
실행하지 않아(누를 때마다 대상이 번갈아 잡혀 한 번 걸러 한 번 동작) 그 키가
사실상 먹통이 되기 때문이다.

키 이벤트 방식에서는 Qt 가 단축키를 키 이벤트보다 먼저 처리하므로,

- 앱이 이미 그 키를 단축키(QShortcut/QAction)로 쓰고 있으면 → **앱 것이 그대로
  동작**하고 여기 기본 동작은 조용히 비켜선다. (충돌로 먹통이 되지 않는다)
- 아무도 쓰지 않으면 → 포커스가 이 위젯이나 그 자식(페이지 안쪽 포함)에 있을 때
  여기서 처리한다.

``setSwitchShortcutContext()`` 로 ``Qt.WindowShortcut`` / ``Qt.ApplicationShortcut``
을 지정하면(창/앱 전체에서 받고 싶을 때) 그때는 QShortcut 으로 등록한다.
"""

from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

try:  # Qt6 에서는 QShortcut 이 QtGui 로 옮겨졌다.
    from qtpy.QtGui import QShortcut
except ImportError:  # pragma: no cover - Qt5 경로
    from qtpy.QtWidgets import QShortcut


def _to_int(value):
    """Qt5/Qt6, PyQt/PySide 어디서든 Qt 열거형/플래그를 순수 int 로 바꾼다.

    PyQt5 의 열거형은 int 파생 타입이라 그대로 두면 ``|`` / ``&`` 결과가 다시
    Qt 플래그 객체가 되어 버리므로, 반드시 순수 int 로 만들어 쓴다.
    PyQt6 의 열거형은 int() 가 안 되므로 ``.value`` 로 받는다.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value.value)


# 키 조합 비교에 쓸 상수 (바인딩에 상관없이 int 로 다룬다)
_KEY_TAB = _to_int(Qt.Key_Tab)
_KEY_BACKTAB = _to_int(Qt.Key_Backtab)
_MOD_SHIFT = _to_int(Qt.ShiftModifier)
# 비교에 쓰는 수식키 (Keypad/GroupSwitch 등 잡음은 제외한다)
_MOD_MASK = (_MOD_SHIFT | _to_int(Qt.ControlModifier)
             | _to_int(Qt.AltModifier) | _to_int(Qt.MetaModifier))


def _normalize(key, mods):
    """(키, 수식키)를 비교 가능한 형태로 정규화한다.

    Shift+Tab 은 플랫폼/바인딩에 따라 Key_Backtab 으로 들어오므로,
    Shift 가 붙은 Key_Tab 으로 통일한다.
    """
    key = _to_int(key)
    mods = _to_int(mods) & _MOD_MASK
    if key == _KEY_BACKTAB:
        key = _KEY_TAB
        mods |= _MOD_SHIFT
    return key, mods


class SwitchShortcutMixin(object):
    """그룹/탭 전환 단축키를 붙여 주는 믹스인.

    이 믹스인을 쓰는 클래스는 ``nextGroup()`` / ``previousGroup()`` /
    ``nextTabInGroup()`` / ``previousTabInGroup()`` 를 제공해야 하고,
    ``keyPressEvent`` 에서 ``handleSwitchKey(event)`` 를 호출해 줘야 한다.
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
        # 기본 문맥: 이 위젯이나 그 자식에 포커스가 있을 때만, 키 이벤트로 처리.
        # (창 전체에서 받으려면 Qt.WindowShortcut 으로 바꾼다 → QShortcut 등록)
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
            context: ``Qt.WidgetWithChildrenShortcut``(기본) 이면 이 위젯과 그
                자식에 포커스가 있을 때 **키 이벤트**로 처리한다. 앱이 같은
                키를 이미 단축키로 쓰고 있으면 앱 쪽이 우선한다.
                ``Qt.WindowShortcut``(창 전체) / ``Qt.ApplicationShortcut``
                (앱 전체) 을 주면 QShortcut 으로 등록한다. 이때는 같은 키를
                쓰는 다른 단축키와 충돌(ambiguous)할 수 있으니 주의한다.
        """
        if context != self._shortcut_context:
            self._shortcut_context = context
            self._rebuild_switch_shortcuts()

    def switchShortcutContext(self):
        """단축키 동작 범위를 반환한다."""
        return self._shortcut_context

    def handleSwitchKey(self, event):
        """키 이벤트가 전환 단축키면 전환을 수행하고 True 를 반환한다.

        ``keyPressEvent`` 등에서 호출한다. 처리하지 않았으면 False 를 돌려주므로
        호출한 쪽에서 기본 처리(super)를 이어가면 된다.
        """
        # QShortcut 으로 등록한 문맥에서는 그쪽이 처리하므로 여기선 손대지 않는다.
        if self._shortcut_context != Qt.WidgetWithChildrenShortcut:
            return False
        target = _normalize(event.key(), event.modifiers())
        for combo, slot in self._switch_key_specs():
            if combo == target:
                # 전환할 대상이 없으면(예: 그룹에 탭이 1개뿐) 키를 삼키지 않고
                # 그대로 흘려보내, 앱이 그 키를 쓰고 있다면 그쪽이 받게 한다.
                return bool(slot())
        return False

    # ------------------------------------------------------------------ #
    # 내부 구현
    # ------------------------------------------------------------------ #
    @staticmethod
    def _key_variants(key):
        """키 시퀀스를 (비어 있지 않으면) 리스트로 돌려준다."""
        if key is None:
            return []
        seq = key if isinstance(key, QKeySequence) else QKeySequence(key)
        if seq.isEmpty():
            return []
        return [seq]

    @staticmethod
    def _sequence_combo(seq):
        """QKeySequence 의 첫 조합을 정규화된 (키, 수식키) 로 바꾼다."""
        combo = seq[0]
        if hasattr(combo, "key"):          # Qt6: QKeyCombination
            return _normalize(combo.key(), combo.keyboardModifiers())
        combo = _to_int(combo)             # Qt5: 키 | 수식키 가 합쳐진 int
        return _normalize(combo & ~_MOD_MASK, combo & _MOD_MASK)

    def _switch_specs(self):
        """켜져 있는 (키, 동작) 목록을 만든다."""
        specs = []
        if self._group_shortcut_on:
            specs.append((self._group_keys[0], self._on_shortcut_next_group))
            specs.append((self._group_keys[1], self._on_shortcut_prev_group))
        if self._tab_shortcut_on:
            specs.append((self._tab_keys[0], self._on_shortcut_next_tab))
            specs.append((self._tab_keys[1], self._on_shortcut_prev_tab))
        return specs

    def _switch_key_specs(self):
        """키 이벤트 비교용 (정규화된 조합, 동작) 목록."""
        out = []
        for key, slot in self._switch_specs():
            for seq in self._key_variants(key):
                out.append((self._sequence_combo(seq), slot))
        return out

    def _rebuild_switch_shortcuts(self):
        """등록된 QShortcut 을 정리하고, 필요한 문맥에서만 다시 만든다."""
        for sc in self._switch_shortcuts:
            sc.setParent(None)
            sc.deleteLater()
        self._switch_shortcuts = []

        # 기본 문맥은 키 이벤트(handleSwitchKey)로 처리한다. QShortcut 을 만들면
        # 앱의 같은 키와 ambiguous 충돌이 나서 양쪽 다 먹통이 되기 때문이다.
        if self._shortcut_context == Qt.WidgetWithChildrenShortcut:
            return

        for key, slot in self._switch_specs():
            for seq in self._key_variants(key):
                sc = QShortcut(seq, self)
                sc.setContext(self._shortcut_context)
                sc.activated.connect(slot)
                self._switch_shortcuts.append(sc)

    # 전환 동작 슬롯.
    # 인자 없이 호출되게 감싸고, 실제로 전환할 대상이 있었는지를 bool 로
    # 돌려준다. (키 이벤트 처리에서 키를 소비할지 판단하는 데 쓴다)
    def _on_shortcut_next_group(self):
        if not self.groupOrder():
            return False
        self.nextGroup()
        return True

    def _on_shortcut_prev_group(self):
        if not self.groupOrder():
            return False
        self.previousGroup()
        return True

    def _on_shortcut_next_tab(self):
        return bool(self.nextTabInGroup())

    def _on_shortcut_prev_tab(self):
        return bool(self.previousTabInGroup())
