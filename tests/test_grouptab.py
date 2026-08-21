# -*- coding: utf-8 -*-
"""GroupTabBar / GroupTabWidget 회귀 테스트.

핵심 불변식(같은 그룹 탭의 인접성, 재정렬 정확성), 시그널 계약, 그리고
과거에 잡았던 버그(슬라이드 애니메이션 중 닫기 X 히트 테스트)를 검증한다.

PyQt5 / PyQt6 / PySide2 / PySide6 어디서 돌려도 동일하게 통과해야 한다.
"""
import random
import warnings

import pytest

from qtpy.QtCore import Qt, QEvent, QPoint
from qtpy.QtGui import QMouseEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from grouptab.grouptabbar import GroupTabBar
from grouptab.grouptabwidget import GroupTabWidget

try:
    from qtpy.QtCore import QPointF
except ImportError:  # 매우 오래된 바인딩 방어
    QPointF = None


# ------------------------------------------------------------------ #
# 헬퍼
# ------------------------------------------------------------------ #
def make_bar(spec):
    """spec = [(group, tab_count), ...] 로 GroupTabBar 를 만든다."""
    bar = GroupTabBar()
    bar.resize(4000, 40)
    for group, cnt in spec:
        for k in range(cnt):
            bar.addGroupTab("%s-%d" % (group, k), group)
    return bar


def group_runs(bar):
    """표시 순서대로 그룹이 바뀌는 지점을 묶어 [group, ...] 런 목록으로."""
    runs = []
    for i in range(bar.count()):
        g = bar.tabGroup(i)
        if not runs or runs[-1] != g:
            runs.append(g)
    return runs


def is_contiguous(bar):
    """같은 그룹 탭이 항상 인접(연속)한다는 핵심 불변식."""
    runs = group_runs(bar)
    return len(runs) == len(set(runs))


def uid_order(bar):
    return [bar._uid(i) for i in range(bar.count())]


def mouse_event(kind, x, y):
    # 일부 바인딩에서 QPointF 오버로드가 deprecated 경고를 내지만 동작은
    # 정상이므로, 테스트 출력을 깨끗이 유지하려 해당 경고만 억제한다.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        if QPointF is not None:
            try:
                return QMouseEvent(kind, QPointF(x, y), Qt.LeftButton,
                                   Qt.LeftButton, Qt.NoModifier)
            except (TypeError, ValueError):
                pass
        return QMouseEvent(kind, QPoint(x, y), Qt.LeftButton,
                           Qt.LeftButton, Qt.NoModifier)


# ------------------------------------------------------------------ #
# 기본 불변식
# ------------------------------------------------------------------ #
def test_creation_contiguous_and_unique(qapp):
    bar = make_bar([("A", 3), ("B", 1), ("C", 4)])
    assert bar.count() == 8
    assert is_contiguous(bar)
    order = bar.groupOrder()
    assert order == ["A", "B", "C"]
    assert len(order) == len(set(order))
    uids = uid_order(bar)
    assert len(uids) == len(set(uids)) and None not in uids


def test_add_to_existing_group_keeps_block(qapp):
    bar = make_bar([("A", 2), ("B", 2)])
    # 이미 있는 그룹 A 에 추가하면 A 블록 끝(인덱스 2)에 삽입되어야 한다.
    idx = bar.addGroupTab("A-new", "A")
    assert idx == 2
    assert is_contiguous(bar)
    assert bar.groupOrder() == ["A", "B"]


# ------------------------------------------------------------------ #
# 그룹 이동(재정렬) 정확성
# ------------------------------------------------------------------ #
def test_move_group_preserves_invariants_fuzz(qapp):
    random.seed(1234)
    bar = make_bar([(g, random.randint(1, 6)) for g in range(12)])
    total = bar.count()
    for _ in range(400):
        order = bar.groupOrder()
        g = random.choice(order)
        before = {gr: [bar._uid(i) for i in bar.groupTabIndices(gr)] for gr in order}
        bar._move_group(g, random.randint(0, len(order) - 1))
        assert is_contiguous(bar)
        assert bar.count() == total
        after = {gr: [bar._uid(i) for i in bar.groupTabIndices(gr)]
                 for gr in bar.groupOrder()}
        # 각 그룹 내부의 상대 순서는 보존되어야 한다.
        for gr in order:
            assert before[gr] == after[gr]


def test_move_group_exact_order(qapp):
    bar = make_bar([("A", 2), ("B", 2), ("C", 2)])
    bar._move_group("A", 2)
    assert bar.groupOrder() == ["B", "C", "A"]
    bar._move_group("A", 0)
    assert bar.groupOrder() == ["A", "B", "C"]


def test_animation_on_off_same_final_order(qapp):
    """애니메이션 유무와 무관하게 최종 탭 배치는 동일해야 한다."""
    random.seed(7)
    on = make_bar([(g, 3) for g in range(8)])
    off = make_bar([(g, 3) for g in range(8)])
    off.setGroupMoveAnimationEnabled(False)
    for _ in range(50):
        g = random.randint(0, 7)
        tgt = random.randint(0, 7)
        on._move_group(g, tgt)
        off._move_group(g, tgt)
        on._slide_anim.stop()
        on._on_slide_anim_done()
    assert uid_order(on) == uid_order(off)
    assert on._anim_offsets == {} and on._anim_base == {}


# ------------------------------------------------------------------ #
# 시그널 계약
# ------------------------------------------------------------------ #
def test_current_group_changed_only_on_group_change(qapp):
    bar = make_bar([("A", 3), ("B", 3)])
    seen = []
    bar.currentGroupChanged.connect(seen.append)

    bar.setCurrentIndex(0)          # 그룹 A
    seen.clear()
    bar.setCurrentIndex(1)          # 여전히 A → 방출 없음
    bar.setCurrentIndex(2)          # 여전히 A → 방출 없음
    assert seen == []
    bar.setCurrentIndex(3)          # B → 정확히 1회
    assert seen == ["B"]


def test_group_moved_signal(qapp):
    bar = make_bar([("A", 2), ("B", 2), ("C", 2)])
    moved = []
    bar.groupMoved.connect(lambda g, o, n: moved.append((g, o, n)))

    # 제자리 이동은 no-op → 방출 없음
    bar._move_group("A", 0)
    assert moved == []

    # 실제 이동은 (group, old_index, new_index) 로 1회
    bar._move_group("A", 2)
    assert moved == [("A", 0, 2)]
    assert bar.groupOrder() == ["B", "C", "A"]


# ------------------------------------------------------------------ #
# 닫기 X
# ------------------------------------------------------------------ #
def test_close_click_emits_correct_index(qapp):
    bar = make_bar([("A", 3), ("B", 3)])
    bar.setTabsClosable(True)
    bar.show()
    qapp.processEvents()
    closed = []
    bar.tabCloseRequested.connect(closed.append)

    tgt = 2
    c = bar._close_rect(bar._draw_rect(tgt)).center()
    bar.mousePressEvent(mouse_event(QEvent.MouseButtonPress, c.x(), c.y()))
    bar.mouseReleaseEvent(mouse_event(QEvent.MouseButtonRelease, c.x(), c.y()))
    assert closed == [tgt]

    # 누른 뒤 X 밖에서 떼면 방출되지 않아야 한다.
    closed.clear()
    br = bar.rect().bottomRight()
    bar.mousePressEvent(mouse_event(QEvent.MouseButtonPress, c.x(), c.y()))
    bar.mouseReleaseEvent(mouse_event(QEvent.MouseButtonRelease, br.x(), br.y()))
    assert closed == []


def test_close_hittest_tracks_visual_position_during_animation(qapp):
    """과거 버그 회귀: 슬라이드 애니메이션 중 X 히트 테스트가 그려진(시각)
    위치를 따라가야 한다. 논리 위치가 아니라."""
    bar = make_bar([("A", 2), ("B", 2), ("C", 2)])
    bar.setTabsClosable(True)
    bar.show()
    qapp.processEvents()

    # 그룹 A 탭들에 오프셋을 강제로 걸어 '이동 중' 상태를 만든다.
    off = 120
    bar._start_slide({bar._uid(i): off for i in bar.groupTabIndices("A")})
    bar._on_slide_anim(1.0)  # 오프셋 = base

    i = 0
    visual = bar._close_rect(bar._paint_rect(i)).center()
    logical = bar._close_rect(bar._draw_rect(i)).center()
    # 시각 위치는 논리 위치보다 off 만큼 오른쪽에 있어야 한다.
    assert visual.x() - logical.x() == off
    # 시각 위치를 클릭하면 해당 탭이 잡혀야 한다.
    assert bar._close_index_at(visual) == i

    # 정착(오프셋 정리) 후에는 논리 위치가 다시 잡혀야 한다.
    bar._on_slide_anim_done()
    assert bar._close_index_at(bar._close_rect(bar._draw_rect(i)).center()) == i


# ------------------------------------------------------------------ #
# 렌더링(스타일 3종) — 예외 없이 그려져야 한다
# ------------------------------------------------------------------ #
@pytest.mark.parametrize("style", [
    GroupTabBar.STYLE_ROUNDED,
    GroupTabBar.STYLE_LEFT_COLOR,
    GroupTabBar.STYLE_PLAIN,
])
def test_paint_all_styles(qapp, style):
    bar = make_bar([("A", 2), ("B", 3), ("C", 1)])
    bar.setTabsClosable(True)
    bar.setCurrentIndex(2)
    bar.setGroupStyle(style)
    bar.grab()  # 예외 없이 완료되면 성공


def test_next_tab_in_group_cycles(qapp):
    """같은 그룹 안에서만 1→2→3→1 순환 전환한다."""
    # 그룹 A: 탭 3개(idx 0,1,2), 그룹 B: 탭 2개(idx 3,4)
    bar = make_bar([("A", 3), ("B", 2)])

    # 그룹 A 정방향 순환: 0→1→2→0
    bar.setCurrentIndex(0)
    seq = [bar.currentIndex()]
    for _ in range(3):
        assert bar.nextTabInGroup() is True
        seq.append(bar.currentIndex())
    assert seq == [0, 1, 2, 0]

    # 그룹 A 역방향 순환: 0→2→1→0
    seq = [bar.currentIndex()]
    for _ in range(3):
        assert bar.previousTabInGroup() is True
        seq.append(bar.currentIndex())
    assert seq == [0, 2, 1, 0]

    # 그룹 경계를 넘지 않는다: 그룹 B(2개)는 3↔4 만 오간다.
    bar.setCurrentIndex(3)
    bar.nextTabInGroup()
    assert bar.currentIndex() == 4
    bar.nextTabInGroup()
    assert bar.currentIndex() == 3


def test_next_tab_in_group_single_or_empty(qapp):
    """탭이 하나뿐이거나 선택이 없으면 순환하지 않고 False 를 반환한다."""
    single = make_bar([("A", 1)])
    single.setCurrentIndex(0)
    assert single.nextTabInGroup() is False
    assert single.currentIndex() == 0

    empty = GroupTabBar()
    assert empty.nextTabInGroup() is False
    assert empty.previousTabInGroup() is False


def test_tab_tooltip(qapp):
    """탭별 툴팁: 생성 시 tooltip 파라미터 + setTabToolTip 로 지정/변경."""
    bar = GroupTabBar()
    # 생성 시 tooltip 지정
    i0 = bar.addGroupTab("A", 1, tooltip="탭 A 설명")
    i1 = bar.addGroupTab("B", 1)                       # 툴팁 없음
    i2 = bar.insertGroupTab(bar.count(), "C", 1, tooltip="탭 C 설명")
    assert bar.tabToolTip(i0) == "탭 A 설명"
    assert bar.tabToolTip(i1) == ""                    # 미지정이면 빈 문자열
    assert bar.tabToolTip(i2) == "탭 C 설명"

    # 나중에 setTabToolTip 으로 지정/변경
    bar.setTabToolTip(i1, "나중에 지정")
    assert bar.tabToolTip(i1) == "나중에 지정"

    # 드래그로 순서가 바뀌어도 툴팁이 해당 탭을 따라간다(uid 기준 tabData 와 별개로
    # QTabBar 가 탭 이동 시 툴팁도 함께 옮긴다).
    bar.moveTab(i0, i2)
    idx_a = next(k for k in range(bar.count()) if bar.tabText(k) == "A")
    assert bar.tabToolTip(idx_a) == "탭 A 설명"


def test_paint_empty_and_single(qapp):
    empty = GroupTabBar()
    empty.grab()
    assert empty.currentGroup() is None
    assert empty.setCurrentGroup("nope") is False
    empty.nextGroup()  # 빈 상태에서 순환해도 안전
    single = make_bar([("only", 1)])
    single._move_group("only", 0)  # 단일 그룹 이동(무의미) 안전
    single.grab()
    assert is_contiguous(single)


# ------------------------------------------------------------------ #
# GroupTabWidget: 페이지-탭 동기화
# ------------------------------------------------------------------ #
def test_widget_page_tab_sync_after_moves(qapp):
    w = GroupTabWidget()
    w.resize(900, 300)
    for g in range(6):
        for k in range(random.Random(g).randint(1, 4)):
            label = "G%d-%d" % (g, k)
            page = QLabel(label)
            page.setProperty("tag", label)
            w.addGroupTab(page, label, g)

    def synced():
        return all(w.widget(i).property("tag") == w.tabText(i)
                   for i in range(w.count()))

    assert synced()
    bar = w.tabBar()
    rnd = random.Random(99)
    for _ in range(100):
        order = bar.groupOrder()
        bar._move_group(rnd.choice(order), rnd.randint(0, len(order) - 1))
        assert synced()


def test_icon_types(qapp):
    """타입 기반 아이콘 API: 정적/애니메이션/해제 + GIF 자동 해제."""
    bar = make_bar([("A", 3)])
    assert bar.tabIcon(0).isNull()

    # 정적: 진행(초록 세모), 색상 점
    bar.setTabIconType(0, GroupTabBar.ICON_PROGRESS)
    assert not bar.tabIcon(0).isNull()
    bar.setTabIconType(0, GroupTabBar.ICON_COLOR, color="#ff0000")
    assert not bar.tabIcon(0).isNull()

    # 애니메이션(GIF): loading → tabMovie 존재
    bar.setTabIconType(1, GroupTabBar.ICON_LOADING)
    assert bar.tabMovie(1) is not None
    # 진행으로 바꾸면 GIF 가 해제되어야 한다
    bar.setTabIconType(1, GroupTabBar.ICON_PROGRESS)
    assert bar.tabMovie(1) is None and not bar.tabIcon(1).isNull()

    # 해제(none)
    bar.setTabIconType(1, GroupTabBar.ICON_NONE)
    assert bar.tabIcon(1).isNull()

    # 알 수 없는 타입은 에러
    with pytest.raises(ValueError):
        bar.setTabIconType(0, "does-not-exist")


def test_register_custom_icon_type(qapp):
    """registerIconType 로 새 타입을 추가할 수 있다."""
    from qtpy.QtGui import QIcon, QPixmap
    def star_factory(bar, index, **kw):
        pm = QPixmap(16, 16); pm.fill(Qt.red)
        return QIcon(pm)
    GroupTabBar.registerIconType("star", star_factory)
    try:
        bar = make_bar([("A", 1)])
        bar.setTabIconType(0, "star")
        assert not bar.tabIcon(0).isNull()
        # 위젯에서도 공유 레지스트리로 사용 가능
        from qtpy.QtWidgets import QLabel
        w = GroupTabWidget()
        w.addGroupTab(QLabel("s"), "s", "A")
        w.setTabIconType(0, "star")
        assert not w.tabBar().tabIcon(0).isNull()
    finally:
        GroupTabBar._ICON_FACTORIES.pop("star", None)


def test_icon_type_via_widget(qapp):
    from qtpy.QtWidgets import QLabel
    w = GroupTabWidget()
    w.addGroupTab(QLabel("p"), "p", "A")
    w.setTabIconType(0, GroupTabWidget.ICON_PROGRESS)
    assert not w.tabBar().tabIcon(0).isNull()


def test_expanding_off_by_default(qapp):
    """확장 모드가 기본으로 꺼져 있어야 한다(수동 setExpanding 불필요).

    확장되면 탭 폭이 바 너비에 맞춰 늘어나 그룹 블록/드래그 좌표가 어긋난다.
    QTabWidget.setTabBar() 가 확장을 되살리므로 위젯 쪽도 확인한다.
    """
    bar = make_bar([("A", 2), ("B", 2)])
    bar.show()
    qapp.processEvents()
    assert bar.expanding() is False
    # 실제 탭 폭이 선호 폭(tabSizeHint)과 같아야 한다(늘어나지 않음).
    for i in range(bar.count()):
        assert bar.tabRect(i).width() == bar.tabSizeHint(i).width()

    w = GroupTabWidget()
    from qtpy.QtWidgets import QLabel
    w.addGroupTab(QLabel("A0"), "A0", "A")
    w.addGroupTab(QLabel("B0"), "B0", "B")
    assert w.tabBar().expanding() is False


def test_widget_signals_exposed(qapp):
    w = GroupTabWidget()
    assert hasattr(w, "groupMoved")
    assert hasattr(w, "currentGroupChanged")
    assert w.STYLE_ROUNDED == GroupTabBar.STYLE_ROUNDED


# ------------------------------------------------------------------ #
# 그룹 우회 방지: 그룹 관리는 전용 API 로만
# ------------------------------------------------------------------ #
def test_widget_raw_add_insert_blocked(qapp):
    from qtpy.QtWidgets import QWidget
    w = GroupTabWidget()
    # 전용 API 는 가드가 있어도 정상 동작해야 한다(내부는 super 경로).
    w.addGroupTab(QLabel("A0"), "A0", "A")
    w.insertGroupTab(0, QLabel("A1"), "A1", "A")
    assert w.count() == 2 and w.tabGroup(0) == "A"
    # 네이티브 addTab/insertTab 직접 호출은 막혀야 한다.
    with pytest.raises(RuntimeError):
        w.addTab(QWidget(), "raw")
    with pytest.raises(RuntimeError):
        w.insertTab(0, QWidget(), "raw")


def test_bar_raw_add_insert_blocked(qapp):
    bar = GroupTabBar()
    bar.addGroupTab("x", 1)
    assert bar.count() == 1
    with pytest.raises(RuntimeError):
        bar.addTab("raw")
    with pytest.raises(RuntimeError):
        bar.insertTab(0, "raw")


def test_remove_group_and_group_tab(qapp):
    w = GroupTabWidget()
    for g in ("A", "B", "C"):
        for k in range(2):
            page = QLabel("%s%d" % (g, k))
            page.setProperty("tag", "%s%d" % (g, k))
            w.addGroupTab(page, "%s%d" % (g, k), g)
    assert w.count() == 6
    # removeGroup: 그룹 전체 제거 + 페이지 동기화 유지
    removed = w.removeGroup("B")
    assert removed == 2
    assert w.count() == 4
    assert "B" not in w.groupOrder()
    assert all(w.widget(i).property("tag") == w.tabText(i) for i in range(w.count()))
    # removeGroupTab: 단일 탭 제거
    before = w.count()
    w.removeGroupTab(0)
    assert w.count() == before - 1

    # 바 단독 removeGroup
    bar = GroupTabBar()
    bar.addGroupTab("a", 1); bar.addGroupTab("b", 1); bar.addGroupTab("c", 2)
    assert bar.removeGroup(1) == 2
    assert bar.count() == 1 and bar.groupOrder() == [2]


# ------------------------------------------------------------------ #
# 탭별 닫기 버튼 표시/숨김
# ------------------------------------------------------------------ #
def test_per_tab_close_button_visibility(qapp):
    bar = make_bar([("A", 3), ("B", 3)])

    # 전역 off → 어떤 탭도 X 안 보임
    assert not any(bar.isTabCloseButtonVisible(i) for i in range(bar.count()))

    bar.setTabsClosable(True)
    # 전역 on → 기본 모두 표시
    assert all(bar.isTabCloseButtonVisible(i) for i in range(bar.count()))

    # 탭 2 숨김: 해당 탭만 숨겨지고 폭(예약)이 줄어든다.
    w_before = bar.tabSizeHint(2).width()
    bar.setTabCloseButtonVisible(2, False)
    assert not bar.isTabCloseButtonVisible(2)
    assert all(bar.isTabCloseButtonVisible(i) for i in (0, 1, 3, 4, 5))
    assert bar.tabSizeHint(2).width() < w_before

    # 히트 테스트: 숨긴 탭의 X 위치는 잡히지 않고, 보이는 탭은 잡힌다.
    assert bar._close_index_at(bar._close_rect(bar._draw_rect(2)).center()) == -1
    assert bar._close_index_at(bar._close_rect(bar._draw_rect(1)).center()) == 1

    # 다시 표시
    bar.setTabCloseButtonVisible(2, True)
    assert bar.isTabCloseButtonVisible(2)


def test_per_tab_close_hidden_survives_move(qapp):
    """탭별 숨김 설정은 uid 로 추적되어 그룹 이동 후에도 유지된다."""
    bar = make_bar([("A", 2), ("B", 2)])
    bar.setTabsClosable(True)
    bar.setTabCloseButtonVisible(0, False)
    uid = bar._uid(0)
    bar._move_group("A", 1)  # A 를 뒤로 → 인덱스가 바뀐다
    new_index = bar._index_of_uid(uid)
    assert new_index != 0
    assert not bar.isTabCloseButtonVisible(new_index)


def test_per_tab_close_via_widget(qapp):
    from qtpy.QtWidgets import QLabel
    w = GroupTabWidget()
    w.addGroupTab(QLabel("A0"), "A0", "A")
    w.addGroupTab(QLabel("A1"), "A1", "A")
    w.setTabsClosable(True)
    w.setTabCloseButtonVisible(1, False)
    assert w.isTabCloseButtonVisible(0)
    assert not w.isTabCloseButtonVisible(1)


# ------------------------------------------------------------------ #
# 전환 단축키 (Ctrl+Tab = 그룹 전환 / F1 = 그룹 내 탭 전환)
# ------------------------------------------------------------------ #
def _activate(widget, qapp):
    """단축키가 동작하도록 위젯을 띄우고 활성 창으로 만든다."""
    widget.show()
    qapp.processEvents()
    QApplication.setActiveWindow(widget)
    widget.activateWindow()
    widget.setFocus()
    qapp.processEvents()


def _key(qapp, target, key, mod=Qt.NoModifier):
    QTest.keyClick(target, key, mod)
    qapp.processEvents()


def test_shortcut_group_switch_on_widget(qapp):
    """GroupTabWidget: Ctrl+Tab 은 탭이 아니라 그룹 단위로 넘어간다."""
    w = GroupTabWidget()
    for group in (1, 2, 3):
        for k in range(3):
            w.addGroupTab(QLabel("%d-%d" % (group, k)), "%d-%d" % (group, k), group)
    _activate(w, qapp)

    w.setCurrentIndex(0)
    # 다음 그룹: 인접 탭(1)이 아니라 그룹 2 의 첫 탭(3)으로 간다.
    _key(qapp, w, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 2
    assert w.currentIndex() == 3
    _key(qapp, w, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 3
    # 마지막 그룹에서 한 번 더 누르면 처음 그룹으로 순환한다.
    _key(qapp, w, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 1

    # 역방향(Ctrl+Shift+Tab): 바인딩에 따라 Backtab 으로 들어와도 동작한다.
    _key(qapp, w, Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
    assert w.currentGroup() == 3


def test_shortcut_tab_switch_in_group(qapp):
    """F1 / Shift+F1 은 같은 그룹 안에서만 탭을 순환한다."""
    w = GroupTabWidget()
    for group in (1, 2):
        for k in range(3):
            w.addGroupTab(QLabel("%d-%d" % (group, k)), "%d-%d" % (group, k), group)
    _activate(w, qapp)

    w.setCurrentIndex(0)
    for expected in (1, 2, 0):          # 1→2→3→1 순환
        _key(qapp, w, Qt.Key_F1)
        assert w.currentIndex() == expected
        assert w.currentGroup() == 1    # 그룹 경계를 넘지 않는다

    _key(qapp, w, Qt.Key_F1, Qt.ShiftModifier)
    assert w.currentIndex() == 2


def test_shortcut_group_switch_from_page_child(qapp):
    """페이지 안쪽 위젯에 포커스가 있어도 단축키가 동작한다."""
    w = GroupTabWidget()
    for group in (1, 2):
        page = QLabel("page %d" % group)
        page.setFocusPolicy(Qt.StrongFocus)
        w.addGroupTab(page, "t%d" % group, group)
    _activate(w, qapp)

    w.setCurrentIndex(0)
    page = w.currentWidget()
    page.setFocus()
    qapp.processEvents()
    _key(qapp, page, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 2


def test_shortcut_on_bar_and_toggle(qapp):
    """GroupTabBar 단독 사용에서도 동작하고, 끄면 동작하지 않는다."""
    bar = make_bar([("A", 2), ("B", 2)])
    _activate(bar, qapp)

    bar.setCurrentIndex(0)
    assert bar.groupSwitchShortcutEnabled() is True
    _key(qapp, bar, Qt.Key_Tab, Qt.ControlModifier)
    assert bar.currentIndex() == 2       # 그룹 B 첫 탭
    _key(qapp, bar, Qt.Key_F1)
    assert bar.currentIndex() == 3       # 그룹 B 안에서 다음 탭

    # 끄면 반응하지 않는다.
    bar.setGroupSwitchShortcutEnabled(False)
    bar.setTabSwitchShortcutEnabled(False)
    _key(qapp, bar, Qt.Key_Tab, Qt.ControlModifier)
    _key(qapp, bar, Qt.Key_F1)
    assert bar.currentIndex() == 3


def test_shortcut_custom_keys(qapp):
    """단축키 조합을 바꿀 수 있다."""
    bar = make_bar([("A", 2), ("B", 2)])
    bar.setGroupSwitchKeys("Ctrl+PgDown", "Ctrl+PgUp")
    bar.setTabSwitchKeys("F2", "Shift+F2")
    _activate(bar, qapp)

    bar.setCurrentIndex(0)
    _key(qapp, bar, Qt.Key_Tab, Qt.ControlModifier)   # 이전 조합은 무효
    assert bar.currentIndex() == 0
    _key(qapp, bar, Qt.Key_PageDown, Qt.ControlModifier)
    assert bar.currentIndex() == 2
    _key(qapp, bar, Qt.Key_F2)
    assert bar.currentIndex() == 3
    _key(qapp, bar, Qt.Key_PageUp, Qt.ControlModifier)
    assert bar.currentIndex() == 0
    assert bar.groupSwitchKeys() == ("Ctrl+PgDown", "Ctrl+PgUp")
    assert bar.tabSwitchKeys() == ("F2", "Shift+F2")


def test_widget_does_not_duplicate_bar_shortcuts(qapp):
    """탭 위젯이 단축키를 맡고, 내부 탭 바의 단축키는 꺼져 있다.

    (둘 다 켜져 있으면 탭 바 포커스에서 ambiguous shortcut 이 되어 무시된다)
    """
    w = GroupTabWidget()
    for group in (1, 2):
        w.addGroupTab(QLabel("p%d" % group), "t%d" % group, group)
    bar = w.groupTabBar()
    assert bar.groupSwitchShortcutEnabled() is False
    assert bar.tabSwitchShortcutEnabled() is False
    assert w.groupSwitchShortcutEnabled() is True

    _activate(w, qapp)
    w.setCurrentIndex(0)
    bar.setFocus()
    qapp.processEvents()
    _key(qapp, bar, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 2


def test_shortcut_yields_to_app_shortcut(qapp):
    """앱이 같은 키를 이미 단축키로 쓰고 있으면 그쪽이 우선한다.

    QShortcut 으로 등록하면 Qt 가 ambiguous shortcut 으로 보고 어느 쪽도
    실행하지 않아 키가 먹통이 되므로, 기본 문맥에서는 키 이벤트로 처리한다.
    """
    from qtpy.QtGui import QKeySequence
    try:
        from qtpy.QtGui import QShortcut
    except ImportError:
        from qtpy.QtWidgets import QShortcut

    w = GroupTabWidget()
    for group in (1, 2):
        for k in range(3):
            w.addGroupTab(QLabel("%d-%d" % (group, k)), "%d-%d" % (group, k), group)

    hits = []
    sc = QShortcut(QKeySequence("F1"), w)
    sc.setContext(Qt.WindowShortcut)
    sc.activated.connect(lambda: hits.append("app"))

    _activate(w, qapp)
    w.setCurrentIndex(0)
    for n in range(3):
        _key(qapp, w, Qt.Key_F1)
        assert hits == ["app"] * (n + 1)   # 매번 앱 핸들러가 실행된다
        assert w.currentIndex() == 0       # 라이브러리 기본 동작은 비켜선다

    # 겹치지 않는 Ctrl+Tab 은 그대로 그룹 전환으로 동작한다.
    _key(qapp, w, Qt.Key_Tab, Qt.ControlModifier)
    assert w.currentGroup() == 2


def test_shortcut_window_context(qapp):
    """문맥을 WindowShortcut 으로 바꾸면 창 안 다른 위젯에 포커스가 있어도 동작한다."""
    from qtpy.QtWidgets import QVBoxLayout, QWidget, QLineEdit

    win = QWidget()
    lay = QVBoxLayout(win)
    tabs = GroupTabWidget()
    for group in (1, 2):
        tabs.addGroupTab(QLabel("p%d" % group), "t%d" % group, group)
    edit = QLineEdit()
    lay.addWidget(tabs)
    lay.addWidget(edit)
    tabs.setSwitchShortcutContext(Qt.WindowShortcut)
    assert tabs.switchShortcutContext() == Qt.WindowShortcut

    _activate(win, qapp)
    tabs.setCurrentIndex(0)
    edit.setFocus()
    qapp.processEvents()
    _key(qapp, edit, Qt.Key_Tab, Qt.ControlModifier)
    assert tabs.currentGroup() == 2


def test_shortcut_falls_through_when_nothing_to_switch(qapp):
    """전환할 대상이 없으면(그룹에 탭 1개) 키를 삼키지 않고 흘려보낸다.

    앱이 keyPressEvent 등으로 그 키를 쓰고 있으면 그쪽이 받을 수 있어야 한다.
    """
    seen = []

    class Host(QWidget):
        def keyPressEvent(self, event):
            seen.append(event.key())
            super().keyPressEvent(event)

    host = Host()
    lay = QVBoxLayout(host)
    tabs = GroupTabWidget()
    tabs.addGroupTab(QLabel("only"), "only", 1)   # 그룹 1개, 탭 1개
    lay.addWidget(tabs)

    _activate(host, qapp)
    tabs.setCurrentIndex(0)
    tabs.setFocus()
    qapp.processEvents()

    _key(qapp, tabs, Qt.Key_F1)          # 같은 그룹에 넘어갈 탭이 없다
    assert tabs.currentIndex() == 0
    assert Qt.Key_F1 in seen             # 부모(앱)까지 전달됐다


def _label_left_offset(bar, index):
    """탭 안에서 라벨(글자/아이콘)이 시작하는 x 를 탭 왼쪽 기준으로 잰다."""
    img = bar.grab().toImage()
    r = bar.tabRect(index)
    bg = img.pixelColor(r.left() + 2, r.center().y())
    ys = range(r.top() + r.height() // 3, r.bottom() - r.height() // 4)
    for x in range(r.left() + 1, r.right() - 1):
        for y in ys:
            c = img.pixelColor(x, y)
            if (abs(c.red() - bg.red()) + abs(c.green() - bg.green())
                    + abs(c.blue() - bg.blue())) > 90:
                return x - r.left()
    return None


def test_label_left_margin_same_when_selected_or_not(qapp):
    """선택/비선택(굵은 글씨 여부)에 따라 라벨 왼쪽 여백이 달라지지 않는다.

    탭 폭은 항상 굵은 글씨 기준으로 잡으므로, 라벨 배치도 같은 기준으로
    계산해야 얇은 글씨(비선택)일 때 왼쪽 여백이 밀리지 않는다.
    """
    bar = GroupTabBar()
    bar.addGroupTab("Dashboard", 1)
    bar.addGroupTab("Settings", 2)
    bar.resize(600, 40)

    bar.setCurrentIndex(0)
    sel0, unsel1 = _label_left_offset(bar, 0), _label_left_offset(bar, 1)
    bar.setCurrentIndex(1)
    unsel0, sel1 = _label_left_offset(bar, 0), _label_left_offset(bar, 1)

    assert None not in (sel0, unsel0, sel1, unsel1)
    # 라벨 시작 위치는 동일하다. (굵은 글씨의 글자 자체 여백 때문에 첫 글자
    # 픽셀이 1px 정도 달라질 수는 있다. 수정 전에는 5~6px 씩 밀렸다)
    assert abs(sel0 - unsel0) <= 1
    assert abs(sel1 - unsel1) <= 1
