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
from qtpy.QtWidgets import QLabel

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
