# -*- coding: utf-8 -*-
"""GroupTabWidget - GroupTabBar 를 사용하는 QTabWidget.

QTabWidget 처럼 탭마다 위젯(페이지)을 등록할 수 있으면서, 탭이 그룹으로
묶여 동작한다. 탭 바로는 GroupTabBar 를 사용하므로 다음 기능을 그대로
가진다.

- 탭별 그룹 번호 할당
- 그룹에 탭 추가 시 그룹 블록의 마지막 순서에 삽입
- 드래그 시 그룹이 블록 단위로 함께 이동 (페이지도 함께 이동)
- 선택된 그룹의 탭을 살짝 올리고 굵은 글씨로 강조

PyQt5 / PyQt6 / PySide2 / PySide6 모두 호환된다. (qtpy 사용)
"""

from qtpy.QtWidgets import QTabWidget

from .grouptabbar import GroupTabBar


class GroupTabWidget(QTabWidget):
    """그룹 단위로 동작하는 QTabWidget.

    Signals:
        groupMoved(object, int, int): 그룹 블록이 드래그로 이동했을 때 방출.
            (group, oldOrderIndex, newOrderIndex)
    """

    # 그룹탭 모양 타입 (GroupTabBar 의 것을 그대로 노출).
    STYLE_ROUNDED = GroupTabBar.STYLE_ROUNDED
    STYLE_LEFT_COLOR = GroupTabBar.STYLE_LEFT_COLOR
    STYLE_PLAIN = GroupTabBar.STYLE_PLAIN

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bar = GroupTabBar(self)
        self.setTabBar(self._bar)
        # 그룹 관련 시그널을 그대로 노출한다.
        self.groupMoved = self._bar.groupMoved
        self.currentGroupChanged = self._bar.currentGroupChanged
        # 닫기 X 는 우리가 직접 그리므로, 바의 tabCloseRequested 를
        # QTabWidget 의 동일 시그널로 직접 포워딩한다.
        self._bar.tabCloseRequested.connect(self.tabCloseRequested)

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def groupTabBar(self):
        """내부 GroupTabBar 인스턴스를 반환한다."""
        return self._bar

    def setTabsClosable(self, closable):
        """닫기 X 표시를 켜고 끈다.

        네이티브 자식 위젯 버튼을 만들지 않도록 QTabWidget.setTabsClosable
        (super)은 호출하지 않고, 직접 그리는 바의 설정만 켠다.
        """
        self._bar.setTabsClosable(closable)

    def addGroupTab(self, widget, label, group, icon=None):
        """주어진 그룹의 마지막 순서에 (위젯, 라벨) 탭을 추가한다.

        그룹이 이미 존재하면 해당 그룹 블록의 끝에, 없으면 전체의 맨 뒤에
        새 그룹 블록으로 추가된다. icon 에 QIcon 을 주면 탭에 함께 표시된다.

        Returns:
            int: 새로 추가된 탭의 인덱스.
        """
        indices = self._bar.groupTabIndices(group)
        if indices:
            pos = indices[-1] + 1
        else:
            pos = self.count()
        return self.insertGroupTab(pos, widget, label, group, icon)

    def insertGroupTab(self, index, widget, label, group, icon=None):
        """index 위치에 group 소속 (위젯, 라벨) 탭을 삽입한다.

        Returns:
            int: 새로 추가된 탭의 인덱스.
        """
        # QTabWidget.insertTab 이 탭(탭 바)과 페이지(스택)를 함께 추가한다.
        if icon is not None:
            idx = self.insertTab(index, widget, icon, label)
        else:
            idx = self.insertTab(index, widget, label)
        # 추가된 탭에 그룹 정보를 부여한다.
        self._bar.tagTab(idx, group)
        return idx

    # ------------------------------------------------------------------ #
    # GroupTabBar 로의 편의 위임
    # ------------------------------------------------------------------ #
    def tabGroup(self, index):
        """해당 탭의 그룹 번호를 반환한다."""
        return self._bar.tabGroup(index)

    def groupTabIndices(self, group):
        """해당 그룹에 속한 탭 인덱스 목록을 반환한다."""
        return self._bar.groupTabIndices(group)

    def groupOrder(self):
        """현재 표시 순서대로 그룹 번호의 고유 목록을 반환한다."""
        return self._bar.groupOrder()

    # ------------------------------------------------------------------ #
    # 그룹 전환
    # ------------------------------------------------------------------ #
    def currentGroup(self):
        """현재 선택된 탭이 속한 그룹을 반환한다."""
        return self._bar.currentGroup()

    def setCurrentGroup(self, group):
        """해당 그룹으로 전환한다. (마지막으로 본 탭, 없으면 첫 탭)"""
        return self._bar.setCurrentGroup(group)

    def nextGroup(self):
        """다음 그룹으로 순환 전환한다."""
        self._bar.nextGroup()

    def previousGroup(self):
        """이전 그룹으로 순환 전환한다."""
        self._bar.previousGroup()

    # ------------------------------------------------------------------ #
    # 애니메이션(GIF) 아이콘
    # ------------------------------------------------------------------ #
    def setTabMovie(self, index, movie):
        """해당 탭에 애니메이션 아이콘(QMovie 또는 파일 경로)을 표시한다.

        None 을 주면 해제한다.
        """
        self._bar.setTabMovie(index, movie)

    def tabMovie(self, index):
        """해당 탭에 설정된 QMovie 를 반환한다. (없으면 None)"""
        return self._bar.tabMovie(index)

    def setTabLoading(self, index):
        """기본 제공 로딩 스피너(GIF)를 탭 아이콘으로 표시한다."""
        self._bar.setTabLoading(index)

    def setTabGear(self, index):
        """기본 제공 회전 톱니바퀴(GIF)를 탭 아이콘으로 표시한다."""
        self._bar.setTabGear(index)

    def setTopAccentEnabled(self, enabled):
        """선택된 그룹 탭 윗부분의 액센트 바 표시 여부를 설정한다."""
        self._bar.setTopAccentEnabled(enabled)

    def topAccentEnabled(self):
        return self._bar.topAccentEnabled()

    def setTopAccentColor(self, color):
        """액센트 바 색상 설정. (None 이면 팔레트 highlight 색)"""
        self._bar.setTopAccentColor(color)

    def setGroupStyle(self, style):
        """그룹탭 모양 타입을 설정한다.

        STYLE_ROUNDED(양끝 라운딩) / STYLE_LEFT_COLOR(첫 탭 왼쪽 색상 마커)
        / STYLE_PLAIN(네이티브 탭) 중 하나.
        """
        self._bar.setGroupStyle(style)

    def groupStyle(self):
        """현재 그룹탭 모양 타입을 반환한다."""
        return self._bar.groupStyle()

    def setGroupColor(self, group, color):
        """타입2(STYLE_LEFT_COLOR)에서 특정 그룹의 마커 색을 지정한다."""
        self._bar.setGroupColor(group, color)

    def setGroupMoveAnimationEnabled(self, enabled):
        """그룹 이동 슬라이드 애니메이션을 켜고 끈다. (기본 켜짐)

        이 옵션만으로 제어되며, Qt/QTabWidget 의 전역 애니메이션 설정과는
        무관하게 동작한다.
        """
        self._bar.setGroupMoveAnimationEnabled(enabled)

    def groupMoveAnimationEnabled(self):
        """그룹 이동 슬라이드 애니메이션 사용 여부."""
        return self._bar.groupMoveAnimationEnabled()
