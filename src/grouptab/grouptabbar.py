# -*- coding: utf-8 -*-
"""GroupTabBar - 그룹핑이 가능한 QTabBar 위젯.

QTabBar 의 모양을 유지하면서, 각 탭에 그룹 번호를 할당할 수 있다.
같은 그룹의 탭들은 항상 인접하여 하나의 블록을 이루며, 드래그 시
그룹 전체가 하나의 블록처럼 함께 이동한다. 선택된 탭이 속한 그룹은 살짝
올라오고 글씨가 굵어지며, 윗부분에 액센트 바로 강조된다. 그룹 구분 모양은
setGroupStyle() 으로 타입을 고를 수 있다: 양끝 라운딩 블록(STYLE_ROUNDED),
그룹 첫 탭 왼쪽 색상 마커(STYLE_LEFT_COLOR), 네이티브 탭(STYLE_PLAIN).

PyQt5 / PyQt6 / PySide2 / PySide6 모두 호환된다. (qtpy 사용)
"""

import os

from qtpy.QtCore import Qt, QRect, Signal, QVariantAnimation, QEasingCurve
from qtpy.QtGui import (
    QFont,
    QFontMetrics,
    QColor,
    QIcon,
    QMovie,
    QPalette,
    QPainter,
    QPainterPath,
    QPen,
)
from qtpy.QtWidgets import (
    QTabBar,
    QApplication,
    QStylePainter,
    QStyleOptionTab,
    QStyleOption,
    QStyle,
)


# 기본 제공 GIF 아이콘이 있는 디렉토리 (패키지 내 assets/)
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _event_pos(event):
    """바인딩에 상관없이 마우스 이벤트의 위치를 QPoint 로 반환한다.

    Qt6 에서는 position()(QPointF)을 권장하고 pos()는 deprecated 이므로,
    position()이 있으면 그것을 사용한다. (Qt5 에는 position()이 없다)
    """
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


class GroupTabBar(QTabBar):
    """그룹 단위로 동작하는 QTabBar.

    Signals:
        groupMoved(object, int, int): 그룹 블록이 드래그로 이동했을 때 방출.
            (group, oldOrderIndex, newOrderIndex)
        currentGroupChanged(object): 선택된 탭의 그룹이 바뀌었을 때 방출. (group)
    """

    groupMoved = Signal(object, int, int)
    currentGroupChanged = Signal(object)

    # --- 그룹탭 모양 타입 ---
    STYLE_ROUNDED = 0      # 타입1: 그룹 양끝을 둥근 블록으로 그림 (기본)
    STYLE_LEFT_COLOR = 1   # 타입2: 그룹 첫 탭 왼쪽 위에 그룹별 색상 삼각형 표시
    STYLE_PLAIN = 2        # 타입3: 아무 처리 없는 네이티브 탭

    # 타입2 에서 그룹 색을 따로 지정하지 않았을 때 순서대로 돌려 쓰는 기본 색.
    _DEFAULT_GROUP_COLORS = (
        "#e57373", "#64b5f6", "#81c784", "#ffb74d", "#ba68c8", "#4db6ac",
    )

    # --- 라벨 레이아웃 상수 (직접 그리기) ---
    _LABEL_HMARGIN = 7      # 아이콘과 좌우 가장자리 사이 여백(px)
    _ICON_TEXT_GAP = 5      # 아이콘과 텍스트 사이 간격(px)
    _TEXT_PAD = 6           # 글자 잘림(생략) 방지용 여유 폭(px)
    _TEXT_VOFFSET = -1      # 글꼴 비대칭 보정: 텍스트를 살짝 위로(px)
    _CLOSE_SIZE = 16        # 닫기 X 영역 크기(px)
    _CLOSE_MARGIN = 4       # 탭 우측 가장자리와 X 사이 여백(px)
    _CORNER_RADIUS = 10     # 그룹 블록 위쪽 양끝 모서리 둥글기 반경(px)
    _ANIM_DURATION = 160    # 그룹 이동 슬라이드 애니메이션 지속시간(ms)
    _LEFT_MARKER_SIZE = 12  # 타입2: 그룹 첫 탭 왼쪽 위 삼각형 마커 변 길이(px)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._uid_counter = 0          # 탭별 고유 식별자 발급용 카운터

        # 드래그 상태
        self._drag_group = None        # 현재 드래그 중인 그룹
        self._drag_active = False      # 드래그 임계 거리를 넘었는지 여부
        self._press_pos = None         # 마우스 누른 위치

        # 선택된 그룹의 탭을 기본 선택 효과보다 추가로 더 올리는 높이(px).
        # 이만큼 탭 바 높이를 키워 위쪽에 여백을 확보한다.
        self._group_raise = 3

        # 선택된 그룹의 탭 윗부분에 그리는 액센트 바 (옵션).
        self._top_accent = True          # 표시 여부
        self._accent_color = None        # None 이면 팔레트 highlight 색 사용
        self._accent_thickness = 3       # 두께(px)

        # 그룹 블록의 바깥 양끝(좌/우) 위쪽 모서리 둥글기 반경(px).
        # 그룹 내부의 인접 모서리는 각지게 두어 탭들이 이어 붙고, 그룹의
        # 위쪽 양끝만 둥글게 그려 그룹이 하나의 덩어리로 구분되게 한다.
        # 기본값은 클래스 상수 _CORNER_RADIUS 로 조절한다.
        self._corner_radius = self._CORNER_RADIUS

        # 그룹탭 모양 타입 (STYLE_ROUNDED / STYLE_LEFT_COLOR / STYLE_PLAIN).
        self._group_style = self.STYLE_ROUNDED
        # 타입2 에서 그룹별로 지정한 색. (없으면 _DEFAULT_GROUP_COLORS 순환)
        self._group_colors = {}   # group -> QColor

        # 드래그 중 잡은 그룹이 커서를 실시간으로 따라가는 가로 오프셋(px).
        # 잡은 그룹은 마우스에 1:1 로 붙어 움직인다.
        self._drag_offset = 0
        self._drag_anchor = 0   # 그룹 좌측에서 커서를 잡은 위치

        # 그룹 이동 슬라이드 애니메이션.
        # 잡은 그룹에 밀려나는 다른 그룹들(그리고 드롭 시 잡았던 그룹)이
        # 새 위치로 순간이동하지 않고 부드럽게 미끄러지도록, uid 별 가로
        # 오프셋을 애니메이션한다. (네이티브 QTabBar movable 과 유사)
        # 전적으로 _anim_enabled 로만 제어되며, Qt 전역 애니메이션 style hint
        # (SH_Widget_Animate)나 QTabWidget 기본 탭 애니메이션은 참조하지 않는다.
        # (QVariantAnimation 은 전역 설정과 무관하게 동작한다.)
        self._anim_enabled = True
        self._anim_base = {}       # uid -> 애니메이션 시작 시 오프셋(px)
        self._anim_offsets = {}    # uid -> 현재 프레임 오프셋(px)
        self._slide_anim = QVariantAnimation(self)
        self._slide_anim.setStartValue(1.0)
        self._slide_anim.setEndValue(0.0)
        self._slide_anim.setDuration(self._ANIM_DURATION)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._slide_anim.valueChanged.connect(self._on_slide_anim)
        self._slide_anim.finished.connect(self._on_slide_anim_done)

        # 닫기 버튼: 자식 위젯이 아니라 paintEvent 에서 직접 그린다.
        # (자식 위젯은 항상 부모 paint 위에 그려져, 드래그로 그룹을 띄울 때
        #  깔리는 탭의 X 가 위로 뚫고 나오는 z-order 충돌이 생긴다.)
        self._closable = False
        self._close_press_index = -1   # 닫기 X 를 누른 탭
        self._close_hover_index = -1   # 닫기 X 위에 커서가 있는 탭
        # 탭별로 닫기 X 를 숨긴 uid 집합. (전역 _closable 이 켜져 있어도 여기
        #  포함된 탭은 X 를 그리지 않는다. 기본은 모두 표시.)
        self._close_hidden_uids = set()

        # 그룹 전환 상태
        self._current_group = None
        self._last_uid_by_group = {}   # group -> 그 그룹에서 마지막으로 본 탭의 uid
        self.currentChanged.connect(self._on_current_changed)

        # 애니메이션(GIF) 아이콘: uid -> QMovie
        self._movies = {}

        # 드래그는 전부 우리가 직접(커서 추적) 처리하므로 네이티브 이동은 끈다.
        self.setMovable(False)
        self.setDrawBase(False)
        # 탭 폭을 바 너비에 맞춰 늘리는 확장 모드는 끈다. (기본값 True)
        # 우리는 tabSizeHint 의 자연 폭을 전제로 그룹 블록·라벨·닫기 X 위치와
        # 드래그 좌표를 계산하므로, 확장으로 폭이 늘어나면 그리기/드래그가
        # 어긋난다. 기본으로 꺼서 별도 설정 없이 정상 동작하게 한다.
        self.setExpanding(False)
        # 닫기 X hover 효과를 위해 마우스 추적을 켠다.
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def addGroupTab(self, text, group, icon=None):
        """주어진 그룹의 마지막 순서에 탭을 추가한다.

        그룹이 이미 존재하면 해당 그룹 블록의 끝에 삽입되고, 존재하지
        않으면 전체 탭의 맨 뒤에 새 그룹 블록으로 추가된다.

        icon 에 QIcon 을 주면 탭에 아이콘이 함께 표시된다.

        Returns:
            int: 새로 추가된 탭의 인덱스.
        """
        indices = self.groupTabIndices(group)
        if indices:
            pos = indices[-1] + 1
        else:
            pos = self.count()
        return self.insertGroupTab(pos, text, group, icon)

    def insertGroupTab(self, index, text, group, icon=None):
        """index 위치에 group 소속 탭을 삽입한다.

        주의: 그룹의 인접성(같은 그룹끼리 붙어있어야 함)을 깨뜨리는
        위치를 직접 지정하면 표시가 어긋날 수 있다. 일반적인 사용에는
        addGroupTab() 을 권장한다.

        Returns:
            int: 새로 추가된 탭의 인덱스.
        """
        # 그룹 태깅과 함께 추가해야 하므로 네이티브 insertTab(super)을 쓴다.
        # (self.insertTab 는 그룹 우회 방지용으로 막혀 있다 → _guard_native_tab)
        if icon is not None:
            idx = super().insertTab(index, icon, text)
        else:
            idx = super().insertTab(index, text)
        self.tagTab(idx, group)
        return idx

    def removeGroup(self, group):
        """해당 그룹에 속한 모든 탭을 제거한다.

        Returns:
            int: 제거된 탭 수.
        """
        indices = self.groupTabIndices(group)
        # 인덱스가 밀리지 않도록 뒤에서부터 제거한다.
        for i in reversed(indices):
            self.removeTab(i)
        return len(indices)

    # --- 그룹 우회 방지: 태그 없는 탭이 생기지 않도록 네이티브 추가 API를 막는다.
    def addTab(self, *args, **kwargs):
        """(막힘) 그룹 정보 없는 탭을 만들 수 있어 사용을 금지한다."""
        raise RuntimeError(
            "GroupTabBar 에서는 addTab() 을 직접 사용할 수 없습니다. "
            "그룹 태그 없는 탭이 생겨 그룹 무결성이 깨집니다. "
            "addGroupTab(text, group[, icon]) 을 사용하세요."
        )

    def insertTab(self, *args, **kwargs):
        """(막힘) 그룹 정보 없는 탭을 만들 수 있어 사용을 금지한다."""
        raise RuntimeError(
            "GroupTabBar 에서는 insertTab() 을 직접 사용할 수 없습니다. "
            "insertGroupTab(index, text, group[, icon]) 을 사용하세요."
        )

    def tagTab(self, index, group):
        """이미 존재하는 탭에 그룹/uid 를 부여한다.

        QTabWidget 처럼 외부에서 탭을 추가(insertTab)한 뒤 그룹 정보를
        붙일 때 사용한다. (GroupTabWidget 연동용)
        """
        self._uid_counter += 1
        self.setTabData(index, {"group": group, "uid": self._uid_counter})
        # insertTab 단계(태깅 전)에서 발생한 currentChanged 는 그룹 정보를
        # 읽지 못하므로, 태깅이 끝난 지금 현재 탭이면 그룹 추적을 재동기화한다.
        if index == self.currentIndex():
            self._on_current_changed(index)
        self.update()

    def tabGroup(self, index):
        """해당 탭의 그룹 번호를 반환한다. (없으면 None)"""
        data = self.tabData(index)
        if isinstance(data, dict):
            return data.get("group")
        return None

    def groupTabIndices(self, group):
        """해당 그룹에 속한 탭 인덱스 목록을 순서대로 반환한다."""
        return [i for i in range(self.count()) if self.tabGroup(i) == group]

    def groupOrder(self):
        """현재 표시 순서대로 그룹 번호의 고유 목록을 반환한다."""
        order = []
        for i in range(self.count()):
            g = self.tabGroup(i)
            if g not in order:
                order.append(g)
        return order

    # ------------------------------------------------------------------ #
    # 그룹 전환
    # ------------------------------------------------------------------ #
    def currentGroup(self):
        """현재 선택된 탭이 속한 그룹을 반환한다. (없으면 None)"""
        idx = self.currentIndex()
        return self.tabGroup(idx) if idx >= 0 else None

    def setCurrentGroup(self, group):
        """해당 그룹으로 전환한다.

        그 그룹에서 마지막으로 선택했던 탭으로 돌아가고, 기록이 없으면
        그룹의 첫 번째 탭을 선택한다.

        Returns:
            bool: 전환 성공 여부(그룹에 탭이 있으면 True).
        """
        indices = self.groupTabIndices(group)
        if not indices:
            return False
        uid = self._last_uid_by_group.get(group)
        target = self._index_of_uid(uid) if uid is not None else -1
        if target not in indices:
            target = indices[0]
        self.setCurrentIndex(target)
        return True

    def nextGroup(self, step=1):
        """그룹 순서상 다음(step=1)/이전(step=-1) 그룹으로 순환 전환한다."""
        order = self.groupOrder()
        if not order:
            return
        cur = self.currentGroup()
        i = (order.index(cur) + step) % len(order) if cur in order else 0
        self.setCurrentGroup(order[i])

    def previousGroup(self):
        """그룹 순서상 이전 그룹으로 순환 전환한다."""
        self.nextGroup(-1)

    def _on_current_changed(self, index):
        # insertTab 직후(아직 tagTab 전) 발생한 신호는 무시한다.
        # 태깅이 끝나면 tagTab 에서 다시 호출되어 올바르게 처리된다.
        if index >= 0 and self.tabData(index) is None:
            return
        group = self.tabGroup(index) if index >= 0 else None
        if group is not None:
            self._last_uid_by_group[group] = self._uid(index)
        if group != self._current_group:
            self._current_group = group
            self.currentGroupChanged.emit(group)

    # ------------------------------------------------------------------ #
    # 애니메이션(GIF) 아이콘
    # ------------------------------------------------------------------ #
    def setTabMovie(self, index, movie):
        """해당 탭에 애니메이션 아이콘(GIF 등)을 표시한다.

        Args:
            index: 탭 인덱스.
            movie: QMovie 인스턴스 또는 파일 경로(str). None 이면 해제한다.
        """
        uid = self._uid(index)
        if uid is None:
            return

        # 기존 무비가 있으면 정리한다.
        old = self._movies.pop(uid, None)
        if old is not None:
            self._discard_movie(old)

        if movie is None:
            self.setTabIcon(index, QIcon())
            return

        if isinstance(movie, str):
            movie = QMovie(movie)

        # 위젯에 부모로 묶어, 위젯 소멸 시 무비도 함께 정리되게 한다.
        movie.setParent(self)

        size = self.iconSize()
        if size.width() > 0 and size.height() > 0:
            movie.setScaledSize(size)

        self._movies[uid] = movie
        movie.frameChanged.connect(lambda _f, u=uid: self._update_movie_icon(u))
        movie.start()
        self._update_movie_icon(uid)

    def tabMovie(self, index):
        """해당 탭에 설정된 QMovie 를 반환한다. (없으면 None)"""
        return self._movies.get(self._uid(index))

    def _discard_movie(self, movie):
        """무비의 연결을 끊고 정지한 뒤, 부모를 해제해 정리되게 한다."""
        try:
            movie.frameChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
        movie.stop()
        movie.setParent(None)

    def _update_movie_icon(self, uid):
        movie = self._movies.get(uid)
        if movie is None:
            return
        idx = self._index_of_uid(uid)
        if idx < 0:   # 탭이 제거됨 → 정리
            self._movies.pop(uid, None)
            self._discard_movie(movie)
            return
        self.setTabIcon(idx, QIcon(movie.currentPixmap()))

    def setTabLoading(self, index):
        """기본 제공 로딩 스피너(GIF)를 탭 아이콘으로 표시한다."""
        self.setTabMovie(index, os.path.join(_ASSET_DIR, "loading.gif"))

    def setTabGear(self, index):
        """기본 제공 회전 톱니바퀴(GIF)를 탭 아이콘으로 표시한다."""
        self.setTabMovie(index, os.path.join(_ASSET_DIR, "gear.gif"))

    def setTabsClosable(self, closable):
        """닫기 버튼(X) 표시를 켜고 끈다.

        네이티브 자식 위젯 버튼을 만들지 않고, paintEvent 에서 직접 X 를
        그린다(드래그 시 z-order 충돌 방지). super 는 호출하지 않는다.
        """
        closable = bool(closable)
        if closable == self._closable:
            return
        self._closable = closable
        self.relayoutTabs()
        self.update()

    def tabsClosable(self):
        """닫기 버튼(X) 전역 표시 여부."""
        return self._closable

    def setTabCloseButtonVisible(self, index, visible):
        """특정 탭의 닫기 X 표시 여부를 설정한다.

        전역 setTabsClosable(True) 가 켜진 상태에서, 이 값으로 탭마다 X 를
        숨기거나 다시 보이게 할 수 있다. (기본: 모든 탭 표시)
        숨긴 탭은 X 용 여백도 확보하지 않아 라벨이 그만큼 넓게 쓰인다.
        """
        uid = self._uid(index)
        if uid is None:
            return
        if visible:
            self._close_hidden_uids.discard(uid)
        else:
            self._close_hidden_uids.add(uid)
        self.relayoutTabs()   # 폭(tabSizeHint)이 바뀌므로 레이아웃 재계산
        self.update()

    def isTabCloseButtonVisible(self, index):
        """해당 탭의 닫기 X 가 실제로 보이는지 반환한다. (전역+탭별 반영)"""
        return self._tab_close_visible(index)

    def relayoutTabs(self):
        """QTabBar 의 탭 레이아웃을 강제로 다시 계산하게 한다.

        닫기 표시를 켜고 끌 때 tabSizeHint(폭)가 즉시 반영되도록, 같은
        elideMode 를 재설정해 레이아웃을 다시 계산시킨다.
        """
        self.setElideMode(self.elideMode())

    def setTopAccentEnabled(self, enabled):
        """선택된 그룹 탭 윗부분의 액센트 바 표시 여부를 설정한다."""
        self._top_accent = bool(enabled)
        self.update()

    def topAccentEnabled(self):
        """액센트 바 표시 여부를 반환한다."""
        return self._top_accent

    def setTopAccentColor(self, color):
        """액센트 바 색상을 설정한다. (None 이면 팔레트 highlight 색 사용)"""
        self._accent_color = QColor(color) if color is not None else None
        self.update()

    def setTopAccentThickness(self, px):
        """액센트 바 두께(px)를 설정한다."""
        self._accent_thickness = int(px)
        self.update()

    def setGroupCornerRadius(self, px):
        """그룹 블록 양끝의 모서리 둥글기 반경(px)을 설정한다."""
        self._corner_radius = max(0, int(px))
        self.update()

    def groupCornerRadius(self):
        """그룹 블록 양끝의 모서리 둥글기 반경(px)을 반환한다."""
        return self._corner_radius

    def setGroupStyle(self, style):
        """그룹탭 모양 타입을 설정한다.

        Args:
            style: STYLE_ROUNDED(양끝 라운딩 블록) / STYLE_LEFT_COLOR(그룹
                첫 탭 왼쪽 색상 마커) / STYLE_PLAIN(네이티브 탭) 중 하나.
        """
        self._group_style = int(style)
        self.update()

    def groupStyle(self):
        """현재 그룹탭 모양 타입을 반환한다."""
        return self._group_style

    def setGroupColor(self, group, color):
        """타입2(STYLE_LEFT_COLOR)에서 특정 그룹의 마커 색을 지정한다.

        color 에 None 을 주면 지정을 해제하고 기본 색 순환으로 되돌린다.
        """
        if color is None:
            self._group_colors.pop(group, None)
        else:
            self._group_colors[group] = QColor(color)
        self.update()

    # ------------------------------------------------------------------ #
    # 내부 헬퍼
    # ------------------------------------------------------------------ #
    def _uid(self, index):
        data = self.tabData(index)
        if isinstance(data, dict):
            return data.get("uid")
        return None

    def _index_of_uid(self, uid):
        for i in range(self.count()):
            if self._uid(i) == uid:
                return i
        return -1

    def _bold_font(self):
        f = QFont(self.font())
        f.setBold(True)
        return f

    def _tab_close_visible(self, index):
        """해당 탭에 닫기 X 가 실제로 보이는지 (전역 스위치 + 탭별 설정)."""
        if not self._closable:
            return False
        return self._uid(index) not in self._close_hidden_uids

    def _close_reserve(self, index):
        """닫기 X 가 라벨 오른쪽에서 차지할 폭(px). (표시 안 하면 0)"""
        if not self._tab_close_visible(index):
            return 0
        return self._CLOSE_SIZE + self._ICON_TEXT_GAP

    def _close_rect(self, rect):
        """탭의 (시각적) 사각형 안에서 닫기 X 가 그려질 영역."""
        s = self._CLOSE_SIZE
        x = rect.right() - self._CLOSE_MARGIN - s + 1
        y = rect.center().y() - s // 2
        return QRect(x, y, s, s)

    def _draw_rect(self, index):
        """탭을 그릴 기준 사각형."""
        return self.tabRect(index)

    def _group_bounds(self):
        """한 번의 순회로 각 그룹의 가로 경계 [left, right] 를 구한다.

        드래그 목표 계산은 그룹의 x 중심/좌측만 필요하므로, 그룹마다
        groupTabIndices()(각 O(n))를 부르는 대신 전체를 한 번만 훑는다.
        반환 dict 는 삽입 순서(=그룹 표시 순서)를 유지한다.
        """
        bounds = {}
        for i in range(self.count()):
            g = self.tabGroup(i)
            r = self._draw_rect(i)
            b = bounds.get(g)
            if b is None:
                bounds[g] = [r.left(), r.right()]
            else:
                if r.left() < b[0]:
                    b[0] = r.left()
                if r.right() > b[1]:
                    b[1] = r.right()
        return bounds

    def _reorder_to_uids(self, desired_uids):
        """탭들을 desired_uids 의 순서가 되도록 재정렬한다.

        uid->현재 인덱스 맵을 유지하며 이동해, 매 이동마다 인덱스를 전체
        탐색(_index_of_uid, O(n))하던 O(n^2) 를 피한다. 또한 moveTab 마다
        발생하는 중간 repaint 를 억제해 원격 X 에서도 전송이 한 번만 일어난다.
        """
        self.setUpdatesEnabled(False)
        try:
            pos = {self._uid(i): i for i in range(self.count())}
            for target, uid in enumerate(desired_uids):
                cur = pos.get(uid, -1)
                if cur == -1 or cur == target:
                    continue
                # 앞쪽 prefix 는 이미 확정이므로 항상 cur > target 이다.
                # moveTab 으로 [target, cur-1] 구간이 한 칸씩 뒤로 밀린다.
                self.moveTab(cur, target)
                for u, p in pos.items():
                    if target <= p < cur:
                        pos[u] = p + 1
                pos[uid] = target
        finally:
            self.setUpdatesEnabled(True)
        self.update()

    def _move_group(self, group, target_order_index):
        """group 블록을 그룹 순서상 target_order_index 위치로 이동한다."""
        n = self.count()
        groups = [self.tabGroup(i) for i in range(n)]
        order = list(dict.fromkeys(groups))
        if group not in order:
            return
        old_index = order.index(group)
        order.remove(group)
        target_order_index = max(0, min(target_order_index, len(order)))
        if target_order_index == old_index:
            return
        order.insert(target_order_index, group)

        # 한 번의 순회로 그룹별 uid 목록을 모은 뒤, 새 그룹 순서대로 이어붙여
        # 전체 탭(uid) 순서를 구성한다. 각 그룹 내부의 상대 순서는 보존된다.
        uids_by_group = {}
        for i in range(n):
            uids_by_group.setdefault(groups[i], []).append(self._uid(i))
        desired = []
        for g in order:
            desired.extend(uids_by_group[g])

        # 재정렬 전 각 탭의 (애니메이션 포함) 시각 위치를 기억해 두고,
        # 재정렬 뒤 그 위치에서 새 슬롯으로 미끄러지도록 애니메이션한다.
        # 잡은 그룹은 커서를 직접 따라가므로 애니메이션에서 제외한다.
        old_visual = self._capture_visual_lefts()
        self._reorder_to_uids(desired)
        self._start_slide_from(old_visual, exclude_group=self._drag_group)
        self.groupMoved.emit(group, old_index, target_order_index)

    # ------------------------------------------------------------------ #
    # 그룹 이동 슬라이드 애니메이션
    # ------------------------------------------------------------------ #
    def _capture_visual_lefts(self):
        """현재 각 탭(uid)의 시각적 좌측 x 를 기록한다. (진행 중 오프셋 포함)"""
        lefts = {}
        for i in range(self.count()):
            uid = self._uid(i)
            if uid is not None:
                lefts[uid] = self.tabRect(i).left() + self._anim_offsets.get(uid, 0)
        return lefts

    def _start_slide_from(self, old_visual, exclude_group=None):
        """재정렬 후, 각 탭이 old_visual 위치에서 새 슬롯으로 미끄러지게 한다."""
        if not self._anim_enabled:
            return
        base = {}
        for i in range(self.count()):
            uid = self._uid(i)
            if uid is None:
                continue
            if exclude_group is not None and self.tabGroup(i) == exclude_group:
                continue
            delta = old_visual.get(uid, self.tabRect(i).left()) - self.tabRect(i).left()
            if delta:
                base[uid] = delta
        self._start_slide(base)

    def _start_slide(self, base):
        """base(uid->시작 오프셋)에서 0 으로 향하는 슬라이드 애니메이션 시작."""
        if not self._anim_enabled or not base:
            return
        # 진행 중이던 다른 탭의 잔여 오프셋도 이어서 0 으로 보낸다.
        merged = dict(self._anim_offsets)
        merged.update(base)
        self._anim_base = merged
        self._anim_offsets = dict(merged)   # 시작(progress=1.0) 프레임
        self._slide_anim.stop()
        self._slide_anim.start()
        self.update()

    def _on_slide_anim(self, value):
        """애니메이션 프레임마다 현재 오프셋 = 시작오프셋 * value 로 갱신."""
        self._anim_offsets = {uid: base * value
                              for uid, base in self._anim_base.items()}
        self.update()

    def _on_slide_anim_done(self):
        self._anim_base = {}
        self._anim_offsets = {}
        self.update()

    def setGroupMoveAnimationEnabled(self, enabled):
        """그룹 이동 슬라이드 애니메이션을 켜고 끈다.

        이 옵션 하나로만 제어된다. Qt 의 전역 위젯 애니메이션 style hint
        (SH_Widget_Animate)나 QTabWidget 의 기본 탭 이동 애니메이션과는
        무관하며, 그것들을 참조하지 않는다. (기본 켜짐)

        원격 X 등에서 프레임 전송 부담을 줄이려면 끌 수 있다.
        """
        self._anim_enabled = bool(enabled)
        if not self._anim_enabled:
            self._slide_anim.stop()
            self._on_slide_anim_done()

    def groupMoveAnimationEnabled(self):
        """그룹 이동 슬라이드 애니메이션 사용 여부."""
        return self._anim_enabled

    def _drag_target_index(self, bounds):
        """잡은 그룹의 현재 시각 중심 x 기준으로 목표 순서 인덱스를 구한다.

        bounds 는 _group_bounds() 결과(그룹 표시 순서 유지).
        """
        b = bounds[self._drag_group]
        center_x = (b[0] + b[1]) / 2.0 + self._drag_offset
        target = 0
        for g, gb in bounds.items():
            if g == self._drag_group:
                continue
            if center_x > (gb[0] + gb[1]) / 2.0:
                target += 1
            else:
                break
        return target

    # ------------------------------------------------------------------ #
    # 크기 힌트 (굵은 글씨 폭 확보 + 선택 그룹 상승 높이 확보)
    # ------------------------------------------------------------------ #
    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        # 폭은 우리가 직접 그리는 라벨(아이콘+텍스트)에 맞춰 다시 계산해서
        # 좌우 여백을 줄인다. 선택 시 굵은 글씨가 되어도 잘리지 않도록 항상
        # 굵은 글씨 기준으로 폭을 잡는다.
        fm = QFontMetrics(self._bold_font())
        text = self.tabText(index)
        if hasattr(fm, "horizontalAdvance"):
            tw = fm.horizontalAdvance(text)
        else:
            tw = fm.width(text)
        iw = self.iconSize().width() if not self.tabIcon(index).isNull() else 0
        gap = self._ICON_TEXT_GAP if iw else 0
        # 닫기 X 가 켜져 있으면 그만큼 폭을 더 확보한다. (탭별 표시 여부 반영)
        reserve = self._close_reserve(index)
        # 글자 폭에 약간의 여유(_TEXT_PAD)를 둬서 폰트/DPI 차이로 마지막
        # 글자가 잘려 '...' 로 생략되는 것을 막는다.
        size.setWidth(iw + gap + tw + self._TEXT_PAD + 2 * self._LABEL_HMARGIN + reserve)
        # 선택 그룹을 더 올릴 수 있도록 위쪽 여백만큼 바 높이를 키운다.
        size.setHeight(size.height() + self._group_raise)
        return size

    # NOTE: minimumTabSizeHint 는 일부러 오버라이드하지 않는다.
    # QTabBar 는 "탭이 최소 크기로도 안 들어가는가"를 minimumTabSizeHint 합으로
    # 판단하는데, 여기에 굵은 글씨 폭을 더하면 실제로는 들어가는 상황에서도
    # 스크롤 버튼이 생기는 오판이 발생한다. (선호 폭은 tabSizeHint 로 충분)

    # ------------------------------------------------------------------ #
    # 마우스 이벤트 (그룹 단위 드래그 이동)
    # ------------------------------------------------------------------ #
    def _close_index_at(self, pos):
        """pos 가 어느 탭의 닫기 X 영역 안이면 그 탭 인덱스를, 아니면 -1."""
        if not self._closable:
            return -1
        # 슬라이드 애니메이션/드래그로 탭이 시각적으로 이동 중이면, tabAt(논리
        # 위치)과 그려진 위치가 어긋난다. 이때는 그려진 위치(_paint_rect) 기준
        # 으로 히트 테스트해야 X 가 보이는 자리를 정확히 집는다. 오프셋이 없는
        # 일반 상황에서는 tabAt 로 O(1) 처리한다.
        if self._anim_offsets or (self._drag_active and self._drag_offset):
            for i in range(self.count()):
                if (self._tab_close_visible(i)
                        and self._close_rect(self._paint_rect(i)).contains(pos)):
                    return i
            return -1
        idx = self.tabAt(pos)
        if (idx != -1 and self._tab_close_visible(idx)
                and self._close_rect(self._draw_rect(idx)).contains(pos)):
            return idx
        return -1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = _event_pos(event)
            # 닫기 X 를 눌렀으면 드래그/선택을 시작하지 않는다.
            ci = self._close_index_at(pos)
            if ci != -1:
                self._close_press_index = ci
                return
            idx = self.tabAt(pos)
            if idx != -1:
                self._drag_group = self.tabGroup(idx)
                self._press_pos = pos
                self._drag_active = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_group is not None and (event.buttons() & Qt.LeftButton):
            pos = _event_pos(event)
            if not self._drag_active and self._press_pos is not None:
                if (pos - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                    self._drag_active = True
                    # 그룹 좌측에서 커서를 잡은 위치를 기억한다.
                    self._drag_anchor = self._press_pos.x() - self._group_bounds()[self._drag_group][0]
            if self._drag_active:
                # 그룹 경계를 한 번만 계산해 재사용한다. (마우스 이동은 잦으므로
                # 그룹마다 O(n) 을 반복하지 않도록 O(n) 한 번으로 끝낸다.)
                bounds = self._group_bounds()
                # 잡은 그룹이 커서를 1:1 로 따라오도록 오프셋을 갱신한다.
                self._drag_offset = pos.x() - self._drag_anchor - bounds[self._drag_group][0]
                # 다른 그룹의 중심을 넘어서면 순서를 바꾼다.
                target = self._drag_target_index(bounds)
                if list(bounds.keys()).index(self._drag_group) != target:
                    self._move_group(self._drag_group, target)
                    # 재정렬로 기준 위치가 바뀌었으니 오프셋을 다시 계산(점프 방지)
                    base_left = self._group_bounds()[self._drag_group][0]
                    self._drag_offset = pos.x() - self._drag_anchor - base_left
                self.update()
            # 그룹 드래그를 전담하므로, 네이티브 단일 탭 드래그가 시작되지
            # 않도록 super 로 넘기지 않는다.
            return
        # 드래그가 아니면 닫기 X hover 상태를 갱신한다.
        if self._closable:
            hover = self._close_index_at(_event_pos(event))
            if hover != self._close_hover_index:
                self._close_hover_index = hover
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 닫기 X 클릭 처리: 누른 곳에서 떼면 tabCloseRequested 방출.
        if self._close_press_index != -1:
            idx = self._close_press_index
            self._close_press_index = -1
            if (idx < self.count()
                    and self._close_rect(self._draw_rect(idx)).contains(_event_pos(event))):
                self.tabCloseRequested.emit(idx)
            return
        dg = self._drag_group
        doff = self._drag_offset
        self._drag_group = None
        self._drag_active = False
        self._press_pos = None
        self._drag_offset = 0
        if doff and dg is not None and self._anim_enabled:
            # 잡았던 그룹은 이미 올바른 슬롯에 있다. 커서를 놓은 위치(doff)에서
            # 슬롯(0)으로 부드럽게 미끄러져 안착하도록 애니메이션한다.
            base = {}
            for i in self.groupTabIndices(dg):
                uid = self._uid(i)
                if uid is not None:
                    base[uid] = doff
            self._start_slide(base)
        elif doff:
            # 애니메이션이 꺼져 있으면 오프셋만 0 으로 되돌린다.
            self.update()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._close_hover_index != -1:
            self._close_hover_index = -1
            self.update()
        super().leaveEvent(event)

    # ------------------------------------------------------------------ #
    # 그리기 (탭을 직접 그려서 선택 그룹 강조/애니메이션을 구현한다)
    # ------------------------------------------------------------------ #
    def _paint_rect(self, index):
        """드래그/슬라이드 오프셋을 반영한, 탭을 그릴 최종 사각형."""
        r = self._draw_rect(index)
        if (self._drag_active and self._drag_offset
                and self.tabGroup(index) == self._drag_group):
            # 잡은 그룹: 커서를 1:1 로 따라간다.
            r = r.translated(self._drag_offset, 0)
        else:
            # 그 외 탭: 진행 중인 슬라이드 애니메이션 오프셋을 반영한다.
            off = self._anim_offsets.get(self._uid(index), 0)
            if off:
                r = r.translated(int(round(off)), 0)
        return r

    def _draw_tab_label(self, painter, rect, index, font, fm, selected):
        """탭의 아이콘 + 텍스트를 직접 그린다.

        아이콘과 텍스트를 같은 세로 중심선에 맞추고(수직 중앙 정렬), 좌우
        여백을 줄여서 묶음을 탭 중앙에 배치한다. fm 은 font 에 대응하는
        QFontMetrics 로, paint 루프에서 폰트당 한 번만 만들어 넘겨받는다.
        """
        text = self.tabText(index)
        icon = self.tabIcon(index)
        has_icon = not icon.isNull()
        isize = self.iconSize()
        iw = isize.width() if has_icon else 0
        ih = isize.height() if has_icon else 0
        gap = self._ICON_TEXT_GAP if has_icon else 0

        # 닫기 X 영역(오른쪽)을 제외한 부분에 아이콘+텍스트를 배치한다.
        reserve = self._close_reserve(index)
        if reserve:
            rect = rect.adjusted(0, 0, -reserve, 0)

        avail = rect.width() - iw - gap - 2 * self._LABEL_HMARGIN
        avail = max(0, avail)
        elided = fm.elidedText(text, Qt.ElideRight, avail)
        if hasattr(fm, "horizontalAdvance"):
            tw = fm.horizontalAdvance(elided)
        else:
            tw = fm.width(elided)

        total = iw + gap + tw
        x = rect.left() + (rect.width() - total) // 2
        x = max(x, rect.left() + self._LABEL_HMARGIN)
        cy = rect.center().y()

        if has_icon:
            mode = QIcon.Normal
            if not self.isTabEnabled(index):
                mode = QIcon.Disabled
            elif selected:
                mode = QIcon.Selected
            pm = icon.pixmap(isize, mode, QIcon.On)
            painter.drawPixmap(QRect(x, int(round(cy - ih / 2.0)), iw, ih), pm)
            x += iw + gap

        painter.save()
        painter.setFont(font)
        cg = QPalette.Normal if self.isTabEnabled(index) else QPalette.Disabled
        painter.setPen(self.palette().color(cg, QPalette.WindowText))
        painter.drawText(QRect(x, rect.top() + self._TEXT_VOFFSET, tw + 1, rect.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, elided)
        painter.restore()

    def _draw_close_button(self, painter, rect, index):
        """탭의 닫기 X 를 직접 그린다. (자식 위젯 미사용)"""
        opt = QStyleOption()
        opt.initFrom(self)
        opt.rect = self._close_rect(rect)
        if index == self._close_hover_index:
            opt.state |= QStyle.State_MouseOver | QStyle.State_Raised
        if not self.isTabEnabled(index):
            opt.state &= ~QStyle.State_Enabled
        painter.drawPrimitive(QStyle.PE_IndicatorTabClose, opt)

    def _rounded_path(self, rect, radius, tl, tr, br, bl):
        """rect 로부터 지정한 모서리만 둥근 QPainterPath 를 만든다.

        tl/tr/br/bl 은 각각 좌상/우상/우하/좌하 모서리를 둥글게 할지 여부.
        (QRect 의 right()/bottom() 은 마지막 픽셀 좌표라 +1 로 보정한다.)
        """
        r = radius
        x1, y1 = rect.left(), rect.top()
        x2, y2 = rect.right() + 1, rect.bottom() + 1
        path = QPainterPath()
        path.moveTo(x1 + (r if tl else 0), y1)
        path.lineTo(x2 - (r if tr else 0), y1)
        if tr:
            path.quadTo(x2, y1, x2, y1 + r)
        path.lineTo(x2, y2 - (r if br else 0))
        if br:
            path.quadTo(x2, y2, x2 - r, y2)
        path.lineTo(x1 + (r if bl else 0), y2)
        if bl:
            path.quadTo(x1, y2, x1, y2 - r)
        path.lineTo(x1, y1 + (r if tl else 0))
        if tl:
            path.quadTo(x1, y1, x1 + r, y1)
        path.closeSubpath()
        return path

    def _draw_group_tab_shape(self, painter, rect, index, in_sel_group,
                              selected, round_left, round_right):
        """탭 모양을 직접 그린다. (그룹 양끝만 둥글게)

        그룹 내 첫 탭은 좌측 위 모서리를, 마지막 탭은 우측 위 모서리를
        둥글게 그리고(아래쪽은 콘텐츠에 붙으므로 각지게), 그 사이의 탭들은
        각진 모서리로 맞붙어 하나의 그룹 블록을 이룬다. 채움색은 선택
        상태에 따라 팔레트에서 고른다.
        """
        pal = self.palette()
        if selected:
            fill = pal.color(QPalette.Base)          # 현재 탭: 가장 밝게
        elif in_sel_group:
            fill = pal.color(QPalette.Midlight)      # 선택 그룹의 다른 탭
        else:
            fill = pal.color(QPalette.Button)        # 그 외 그룹
        border = pal.color(QPalette.Mid)

        # 탭은 아래가 콘텐츠에 붙으므로 위쪽 양끝만 둥글게(아래는 각지게) 그린다.
        r = min(self._corner_radius, rect.height() // 2, rect.width() // 2)
        path = self._rounded_path(rect, r,
                                  tl=round_left, tr=round_right,
                                  br=False, bl=False)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(path, fill)

        # 선택 그룹 상단 액센트 바: 둥근 끝을 따라가도록 경로로 클립한다.
        if in_sel_group and self._top_accent:
            color = self._accent_color or pal.highlight().color()
            painter.setClipPath(path)
            painter.fillRect(
                QRect(rect.left(), rect.top(), rect.width(), self._accent_thickness),
                color,
            )
            painter.setClipping(False)

        pen = QPen(border)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.restore()

    def _draw_native_tab_shape(self, painter, rect, index):
        """네이티브 스타일로 탭 모양을 그린다. (타입2·3 공용)"""
        opt = QStyleOptionTab()
        self.initStyleOption(opt, index)
        opt.rect = rect
        painter.drawControl(QStyle.CE_TabBarTabShape, opt)

    def _draw_top_accent(self, painter, rect):
        """탭 상단(rect.top())에 선택 그룹 액센트 바를 그린다."""
        color = self._accent_color or self.palette().highlight().color()
        painter.fillRect(
            QRect(rect.left(), rect.top(), rect.width(), self._accent_thickness),
            color,
        )

    def _draw_left_color_marker(self, painter, rect, color):
        """타입2: 그룹 첫 탭 왼쪽 위 모서리에 그룹 색상 삼각형을 그린다."""
        size = self._LEFT_MARKER_SIZE
        x, y = rect.left(), rect.top()
        path = QPainterPath()
        path.moveTo(x, y)               # 좌상 꼭짓점
        path.lineTo(x + size, y)        # 상변을 따라 오른쪽으로
        path.lineTo(x, y + size)        # 좌변을 따라 아래로
        path.closeSubpath()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(path, color)
        painter.restore()

    def paintEvent(self, event):
        painter = QStylePainter(self)

        # 1) 배경을 지운다. (탭이 없는 영역/이동 후 잔상 방지)
        painter.fillRect(self.rect(), self.palette().window())

        # 2) 탭을 직접 그린다. (그룹 양끝만 둥근 블록 모양)
        #    선택된 탭이 속한 그룹의 탭들은 살짝 높게 그린다.
        #    그리기 순서: 다른 그룹(낮음) -> 선택 그룹(높음) -> 현재 탭(맨 위)
        #
        #    paint 는 애니메이션 프레임마다 호출되므로, 탭마다 groupTabIndices()
        #    (각각 O(n))를 부르면 전체가 O(n^2) 이 되어 큰 탭 수에서 느려진다.
        #    그래서 그룹 배열을 한 번만 읽어 재사용하고, "같은 그룹은 인접"이라는
        #    불변식을 이용해 각 탭의 그룹 양끝 여부를 O(1) 로 판별한다.
        n = self.count()
        selected = self.currentIndex()
        groups = [self.tabGroup(i) for i in range(n)]
        sel_group = groups[selected] if 0 <= selected < n else None

        other = [i for i in range(n) if groups[i] != sel_group]
        same = [i for i in range(n) if groups[i] == sel_group and i != selected]
        order = other + same
        if 0 <= selected < n:
            order.append(selected)

        # 드래그 중인 그룹은 맨 위(마지막)로 올려 그려 다른 탭 위로 떠 보이게 한다.
        dg = self._drag_group
        if self._drag_active and dg is not None:
            order = [i for i in order if groups[i] != dg] \
                + [i for i in order if groups[i] == dg]

        normal_font = self.font()
        bold_font = self._bold_font()
        # QFontMetrics 생성은 비싸므로 폰트당 한 번만 만들어 재사용한다.
        normal_fm = QFontMetrics(normal_font)
        bold_fm = QFontMetrics(bold_font)
        # 네이티브 스타일이 비선택 탭을 아래로 내려 그리는 양(타입3 보정용).
        shift = self.style().pixelMetric(QStyle.PM_TabBarTabShiftVertical, None, self)

        # 화면(갱신 영역) 밖 탭은 그릴 필요가 없다. 탭이 많아 스크롤될 때
        # event.rect() 는 보이는 구간이므로, 그와 겹치지 않는 탭은 건너뛴다.
        er = event.rect()

        # 타입2: 그룹별 마커 색을 그룹 등장 순서 기준으로 미리 계산해 둔다.
        color_by_group = None
        if self._group_style == self.STYLE_LEFT_COLOR:
            colors = self._DEFAULT_GROUP_COLORS
            color_by_group = {
                g: (self._group_colors.get(g) or QColor(colors[gi % len(colors)]))
                for gi, g in enumerate(dict.fromkeys(groups))
            }

        for i in order:
            g = groups[i]
            base_rect = self._paint_rect(i)
            # 갱신 영역과 겹치지 않는(화면 밖) 탭은 건너뛴다.
            if not base_rect.intersects(er):
                continue
            in_sel_group = (sel_group is not None and g == sel_group)
            is_first = (i == 0 or groups[i - 1] != g)
            is_last = (i == n - 1 or groups[i + 1] != g)

            if self._group_style in (self.STYLE_ROUNDED, self.STYLE_LEFT_COLOR):
                # 타입1·2: 직접 그리므로 네이티브 세로 시프트가 없다. 선택 그룹은
                # 그대로, 그 외 그룹만 _group_raise 만큼 내려 평평한 블록을 이룬다.
                rect = (base_rect if in_sel_group
                        else base_rect.adjusted(0, self._group_raise, 0, 0))
                if self._group_style == self.STYLE_ROUNDED:
                    # 타입1: 그룹 양끝(첫 탭 좌측/마지막 탭 우측)만 둥글게.
                    self._draw_group_tab_shape(painter, rect, i, in_sel_group,
                                               i == selected, is_first, is_last)
                else:
                    # 타입2: 모서리는 각지게(라운딩 없음) 그리고, 그룹 첫 탭
                    # 왼쪽 위에 그룹 색상 삼각형을 덧그린다.
                    self._draw_group_tab_shape(painter, rect, i, in_sel_group,
                                               i == selected, False, False)
                    if is_first:
                        self._draw_left_color_marker(painter, rect, color_by_group[g])
                label_rect = rect
            else:
                # 타입3(PLAIN): 순수 네이티브 탭. 네이티브 스타일이 비선택 탭을
                # shift 만큼 내려 그리므로, 선택 그룹의 탭들이 선택 탭과 같은
                # 높이로 정렬되도록 shape 사각형을 그만큼 올려서 보정한다.
                if in_sel_group and i != selected:
                    rect = base_rect.adjusted(0, -shift, 0, 0)
                elif not in_sel_group:
                    rect = base_rect.adjusted(0, self._group_raise, 0, 0)
                else:
                    rect = base_rect
                self._draw_native_tab_shape(painter, rect, i)
                # 라벨/액센트는 실제(시각적) 위치 기준으로 배치한다. 비선택
                # 탭은 스타일이 shift 만큼 내려 그리므로 그만큼 맞춘다.
                label_rect = rect if i == selected else rect.adjusted(0, shift, 0, 0)
                if in_sel_group and self._top_accent:
                    self._draw_top_accent(painter, label_rect)

            if in_sel_group:
                font, fm = bold_font, bold_fm
            else:
                font, fm = normal_font, normal_fm
            self._draw_tab_label(painter, label_rect, i, font, fm, i == selected)

            # 닫기 X 를 (자식 위젯이 아니라) 직접 그린다 → z-order 충돌 없음.
            # 전역 스위치가 켜져 있고 그 탭이 숨김 대상이 아닐 때만 그린다.
            if self._tab_close_visible(i):
                self._draw_close_button(painter, label_rect, i)

        painter.end()
