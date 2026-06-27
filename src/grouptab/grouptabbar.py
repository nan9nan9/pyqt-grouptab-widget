# -*- coding: utf-8 -*-
"""GroupTabBar - 그룹핑이 가능한 QTabBar 위젯.

QTabBar 의 모양을 유지하면서, 각 탭에 그룹 번호를 할당할 수 있다.
같은 그룹의 탭들은 항상 인접하여 하나의 블록을 이루며, 드래그 시
그룹 전체가 하나의 블록처럼 함께 이동한다. 선택된 탭이 속한 그룹은 살짝
올라오고 글씨가 굵어지며, 윗부분에 액센트 바로 강조된다.

PyQt5 / PyQt6 / PySide2 / PySide6 모두 호환된다. (qtpy 사용)
"""

import os

from qtpy.QtCore import Qt, QRect, Signal, QVariantAnimation, QEasingCurve
from qtpy.QtGui import QFont, QFontMetrics, QColor, QIcon, QMovie, QPalette
from qtpy.QtWidgets import (
    QTabBar,
    QApplication,
    QStylePainter,
    QStyleOptionTab,
    QStyle,
    QProxyStyle,
)


# 기본 제공 GIF 아이콘이 있는 디렉토리 (패키지 내 assets/)
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class _TabButtonOffsetStyle(QProxyStyle):
    """탭의 좌/우 버튼(닫기 버튼 등) 위치를 지정한 만큼 이동시키는 프록시 스타일.

    QTabBar 는 닫기 버튼을 스타일의 SE_TabBarTabRightButton/LeftButton 위치에
    배치하므로, 그 사각형을 오프셋해 버튼 위치를 미세 조정한다.
    """

    def __init__(self, dx=0, dy=0, base_style=None):
        super().__init__(base_style)
        self._dx = dx
        self._dy = dy

    def setOffset(self, dx, dy):
        self._dx = dx
        self._dy = dy

    def subElementRect(self, element, option, widget=None):
        rect = super().subElementRect(element, option, widget)
        if element in (QStyle.SE_TabBarTabRightButton,
                       QStyle.SE_TabBarTabLeftButton):
            rect = rect.translated(self._dx, self._dy)
        return rect


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

    # --- 라벨 레이아웃 상수 (직접 그리기) ---
    _LABEL_HMARGIN = 7      # 아이콘과 좌우 가장자리 사이 여백(px)
    _ICON_TEXT_GAP = 5      # 아이콘과 텍스트 사이 간격(px)
    _TEXT_PAD = 6           # 글자 잘림(생략) 방지용 여유 폭(px)
    _TEXT_VOFFSET = -1      # 글꼴 비대칭 보정: 텍스트를 살짝 위로(px)

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

        # 이동 애니메이션 상태: uid -> 현재 적용할 x 오프셋(px)
        self._anim_offsets = {}
        self._anim_start = {}      # uid -> 애니메이션 시작 시점의 오프셋
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_tick)
        self._anim.finished.connect(self._on_anim_finished)

        # 그룹 전환 상태
        self._current_group = None
        self._last_uid_by_group = {}   # group -> 그 그룹에서 마지막으로 본 탭의 uid
        self.currentChanged.connect(self._on_current_changed)

        # 애니메이션(GIF) 아이콘: uid -> QMovie
        self._movies = {}

        # 닫기 버튼 위치 미세 조정 (오른쪽 3px, 위로 1px)
        self._btn_style = _TabButtonOffsetStyle(3, -1)
        self.setStyle(self._btn_style)

        self.setMovable(True)
        self.setDrawBase(False)

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
        if icon is not None:
            idx = self.insertTab(index, icon, text)
        else:
            idx = self.insertTab(index, text)
        self.tagTab(idx, group)
        return idx

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
        """닫기 버튼 표시를 켜고 끈다. (켜고 끈 뒤 탭 폭을 다시 맞춘다)"""
        super().setTabsClosable(closable)
        self.relayoutTabs()

    def relayoutTabs(self):
        """QTabBar 의 탭 레이아웃을 강제로 다시 계산하게 한다.

        닫기 버튼을 끈 뒤에도 QTabBar 가 캐시된 탭 폭을 그대로 두는 경우가
        있어, 같은 elideMode 를 재설정해 tabSizeHint 를 다시 반영시킨다.
        """
        self.setElideMode(self.elideMode())

    def setCloseButtonOffset(self, dx, dy):
        """닫기 버튼 위치를 (dx, dy)px 만큼 이동한다."""
        self._btn_style.setOffset(dx, dy)
        self.relayoutTabs()

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

    def _close_indicator(self):
        """닫기 버튼이 차지할 (예약 폭, 왼쪽에 있는지) 를 반환한다.

        tabsClosable 가 아니면 (0, False).
        """
        if not self.tabsClosable():
            return 0, False
        w = self.style().pixelMetric(QStyle.PM_TabCloseIndicatorWidth, None, self)
        # SH_TabBar_CloseButtonPosition: LeftSide=0, RightSide=1 (정수 반환)
        side = self.style().styleHint(QStyle.SH_TabBar_CloseButtonPosition, None, self)
        return w + self._ICON_TEXT_GAP, (side == 0)

    def _draw_rect(self, index):
        """탭을 그릴 기준 사각형."""
        return self.tabRect(index)

    def _group_rect(self, group):
        """그룹에 속한 탭들이 실제로 그려지는 영역을 합친 사각형."""
        rect = QRect()
        for i in self.groupTabIndices(group):
            r = self._draw_rect(i)
            rect = QRect(r) if rect.isNull() else rect.united(r)
        return rect

    def _reorder_to_uids(self, desired_uids):
        """탭들을 desired_uids 의 순서가 되도록 재정렬한다."""
        for target, uid in enumerate(desired_uids):
            cur = self._index_of_uid(uid)
            if cur != -1 and cur != target:
                self.moveTab(cur, target)
        self.update()

    def _move_group(self, group, target_order_index):
        """group 블록을 그룹 순서상 target_order_index 위치로 이동한다."""
        order = self.groupOrder()
        if group not in order:
            return
        old_index = order.index(group)
        order.remove(group)
        target_order_index = max(0, min(target_order_index, len(order)))
        if target_order_index == old_index:
            return
        order.insert(target_order_index, group)

        # 새 그룹 순서에 맞춰 전체 탭(uid) 순서를 구성한다.
        # 각 그룹 내부의 상대 순서는 그대로 유지된다.
        desired = []
        for g in order:
            desired.extend(self._uid(i) for i in self.groupTabIndices(g))
        self._animate_reorder(desired)
        self.groupMoved.emit(group, old_index, target_order_index)

    def _draw_x_by_uid(self, with_offset):
        """현재 각 탭(uid)의 그리기 x 좌표를 반환한다."""
        result = {}
        for i in range(self.count()):
            uid = self._uid(i)
            x = self._draw_rect(i).x()
            if with_offset:
                x += self._anim_offsets.get(uid, 0)
            result[uid] = x
        return result

    def _animate_reorder(self, desired_uids):
        """탭 순서를 바꾸고, 이전 위치 -> 새 위치로 슬라이드 애니메이션한다."""
        old = self._draw_x_by_uid(with_offset=True)
        self._reorder_to_uids(desired_uids)
        new = self._draw_x_by_uid(with_offset=False)

        starts = {}
        for uid, nx in new.items():
            if uid in old and old[uid] != nx:
                starts[uid] = old[uid] - nx
        if not starts:
            return
        self._anim_start = starts
        self._anim_offsets = dict(starts)   # 시작 시점엔 이전 위치에서 출발
        self._anim.stop()
        self._anim.start()
        self.update()

    def _on_anim_tick(self, t):
        # t: 0.0 -> 1.0. 오프셋을 점점 0 으로 줄인다.
        for uid, start in self._anim_start.items():
            self._anim_offsets[uid] = start * (1.0 - float(t))
        self.update()

    def _on_anim_finished(self):
        self._anim_offsets = {}
        self._anim_start = {}
        self.update()

    def _target_order_index(self, x):
        """커서 x 좌표에 대응하는, 드래그 중인 그룹의 목표 순서 인덱스."""
        target = 0
        for g in self.groupOrder():
            if g == self._drag_group:
                continue
            r = self._group_rect(g)
            if x > r.center().x():
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
        # 닫기 버튼이 켜져 있으면 그만큼 폭을 더 확보한다.
        reserve, _ = self._close_indicator()
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
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            idx = self.tabAt(_event_pos(event))
            if idx != -1:
                self._drag_group = self.tabGroup(idx)
                self._press_pos = _event_pos(event)
                self._drag_active = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_group is not None and (event.buttons() & Qt.LeftButton):
            pos = _event_pos(event)
            if not self._drag_active and self._press_pos is not None:
                if (pos - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                    self._drag_active = True
            if self._drag_active:
                target = self._target_order_index(pos.x())
                order = self.groupOrder()
                if self._drag_group in order and order.index(self._drag_group) != target:
                    self._move_group(self._drag_group, target)
            # 그룹 드래그를 전담하므로, 네이티브 단일 탭 드래그가 시작되지
            # 않도록 super 로 넘기지 않는다.
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_group = None
        self._drag_active = False
        self._press_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ #
    # 그리기 (탭을 직접 그려서 선택 그룹 강조/애니메이션을 구현한다)
    # ------------------------------------------------------------------ #
    def _paint_rect(self, index):
        """애니메이션 오프셋을 반영한, 탭을 그릴 최종 사각형."""
        r = self._draw_rect(index)
        off = self._anim_offsets.get(self._uid(index), 0)
        if off:
            r = r.translated(int(round(off)), 0)
        return r

    def _draw_tab_label(self, painter, rect, index, font, selected):
        """탭의 아이콘 + 텍스트를 직접 그린다.

        아이콘과 텍스트를 같은 세로 중심선에 맞추고(수직 중앙 정렬), 좌우
        여백을 줄여서 묶음을 탭 중앙에 배치한다.
        """
        text = self.tabText(index)
        icon = self.tabIcon(index)
        has_icon = not icon.isNull()
        isize = self.iconSize()
        iw = isize.width() if has_icon else 0
        ih = isize.height() if has_icon else 0
        gap = self._ICON_TEXT_GAP if has_icon else 0

        # 닫기 버튼 영역을 제외한 부분에 아이콘+텍스트를 배치한다.
        reserve, on_left = self._close_indicator()
        if reserve:
            rect = rect.adjusted(reserve, 0, 0, 0) if on_left \
                else rect.adjusted(0, 0, -reserve, 0)

        fm = QFontMetrics(font)
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

    def paintEvent(self, event):
        painter = QStylePainter(self)

        # 1) 배경을 지운다. (탭이 없는 영역/이동 후 잔상 방지)
        painter.fillRect(self.rect(), self.palette().window())

        # 2) 탭을 그린다.
        #    선택된 탭이 속한 그룹의 탭들은 (선택 탭처럼) 살짝 높게 그린다.
        #    그리기 순서: 다른 그룹(낮음) -> 선택 그룹(높음) -> 현재 탭(맨 위)
        selected = self.currentIndex()
        sel_group = self.tabGroup(selected) if 0 <= selected < self.count() else None
        shift = self.style().pixelMetric(QStyle.PM_TabBarTabShiftVertical, None, self)

        other = [i for i in range(self.count()) if self.tabGroup(i) != sel_group]
        same = [i for i in range(self.count())
                if self.tabGroup(i) == sel_group and i != selected]
        order = other + same
        if 0 <= selected < self.count():
            order.append(selected)

        normal_font = self.font()
        bold_font = self._bold_font()

        for i in order:
            opt = QStyleOptionTab()
            self.initStyleOption(opt, i)
            rect = self._paint_rect(i)
            in_sel_group = (sel_group is not None and self.tabGroup(i) == sel_group)
            if in_sel_group and i != selected:
                # 선택 그룹의 비선택 탭: 스타일이 shift 만큼 내리므로 상쇄해
                # 선택 탭과 같은 높이로 올린다.
                rect = rect.adjusted(0, -shift, 0, 0)
            elif not in_sel_group:
                # 일반 탭: 위쪽 여백(_group_raise)만큼 아래로 내려서 그린다.
                rect = rect.adjusted(0, self._group_raise, 0, 0)
            opt.rect = rect

            # 탭 모양만 스타일로 그리고, 아이콘+텍스트는 직접 그린다.
            painter.drawControl(QStyle.CE_TabBarTabShape, opt)

            # 라벨을 그릴 실제(시각적) 영역: 스타일은 비선택 탭을 shift 만큼
            # 아래로 그리므로 라벨도 같은 위치에 맞춘다.
            label_rect = rect if i == selected else rect.adjusted(0, shift, 0, 0)
            font = bold_font if in_sel_group else normal_font
            self._draw_tab_label(painter, label_rect, i, font, i == selected)

        # 3) 선택된 그룹의 탭들 윗부분에 액센트 바를 그린다. (옵션)
        if self._top_accent and sel_group is not None:
            color = self._accent_color or self.palette().highlight().color()
            for i in range(self.count()):
                if self.tabGroup(i) != sel_group:
                    continue
                r = self._paint_rect(i)
                painter.fillRect(
                    QRect(r.left(), r.top(), r.width(), self._accent_thickness),
                    color,
                )

        painter.end()
