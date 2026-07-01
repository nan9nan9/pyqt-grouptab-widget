# -*- coding: utf-8 -*-
"""GroupTabWidget 데모 앱 (QMainWindow + setCentralWidget 구조).

실제 앱처럼 GroupTabWidget 을 QMainWindow 의 centralWidget 으로 등록한다.

실행:
    python examples/basic_example.py

특정 바인딩으로 실행하려면 QT_API 환경변수를 지정한다.
    QT_API=pyqt6   python examples/basic_example.py
    QT_API=pyside6 python examples/basic_example.py
"""

import os
import sys

# 설치 없이 바로 실행할 수 있도록 src 경로를 등록 (pip install 한 경우엔 불필요)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon, QPixmap, QColor, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QSpinBox,
    QLabel,
    QCheckBox,
    QComboBox,
)

from grouptab import GroupTabWidget


# 그룹 번호별 색상 팔레트
GROUP_COLORS = [
    "#4C8BF5", "#34A853", "#FBBC05", "#EA4335",
    "#9C27B0", "#00ACC1", "#FF7043", "#5E35B1", "#795548",
]


def _group_color(group):
    return QColor(GROUP_COLORS[(int(group) - 1) % len(GROUP_COLORS)])


def _group_icon(group):
    """그룹 색상의 원형 아이콘을 만든다."""
    pm = QPixmap(16, 16)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(_group_color(group))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 12, 12)
    p.end()
    return QIcon(pm)


def _make_page(label, group):
    """탭에 등록할 간단한 페이지 위젯을 만든다."""
    page = QWidget()
    lay = QVBoxLayout(page)
    title = QLabel("‘{}’ 페이지 (그룹 {})".format(label, group))
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size: 18px;")
    lay.addStretch(1)
    lay.addWidget(title)
    lay.addWidget(QLabel("이 탭에 등록된 위젯입니다.", alignment=Qt.AlignCenter))
    lay.addStretch(1)
    return page


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GroupTabWidget 데모 (QMainWindow)")
        self.resize(760, 400)

        self._tab_counter = 0

        # 실제 앱과 동일하게 GroupTabWidget 을 centralWidget 으로 등록한다.
        self.tabs = GroupTabWidget()
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabCloseRequested.connect(self.tabs.removeTab)
        self.setCentralWidget(self.tabs)

        self._build_toolbars()

        # 현재 그룹 표시 (상태바)
        self.tabs.currentGroupChanged.connect(self._on_group_changed)
        self.statusBar().showMessage("탭을 드래그하면 같은 그룹 전체가 함께 이동합니다.")

        # 초기 샘플 탭: 이름 길이와 아이콘 종류를 다양하게.
        samples = [
            (1, "홈", "color"),
            (1, "대시보드", "color"),
            (1, "A", "none"),
            (2, "프로젝트 관리", "color"),
            (2, "설정", "gear"),
            (3, "Notifications", "loading"),
            (3, "로그", "none"),
            (3, "사용자 환경설정 페이지", "color"),
        ]
        for group, name, kind in samples:
            self._add_tab(name, group, kind)
        self.tabs.setCurrentIndex(0)

    def _build_toolbars(self):
        tb = QToolBar("controls")
        tb.setMovable(False)
        self.addToolBar(Qt.BottomToolBarArea, tb)

        tb.addWidget(QLabel(" 그룹: "))
        self.group_spin = QSpinBox()
        self.group_spin.setRange(1, 9)
        self.group_spin.setValue(1)
        tb.addWidget(self.group_spin)
        tb.addWidget(self._btn("탭 추가", self._on_add))
        tb.addWidget(self._btn("현재 탭 삭제", self._on_remove))

        close_chk = QCheckBox("닫기 버튼")
        close_chk.toggled.connect(self.tabs.setTabsClosable)
        tb.addWidget(close_chk)

        accent_chk = QCheckBox("상단 액센트 바")
        accent_chk.setChecked(self.tabs.topAccentEnabled())
        accent_chk.toggled.connect(self.tabs.setTopAccentEnabled)
        tb.addWidget(accent_chk)

        anim_chk = QCheckBox("이동 애니메이션")
        anim_chk.setChecked(self.tabs.groupMoveAnimationEnabled())
        anim_chk.toggled.connect(self.tabs.setGroupMoveAnimationEnabled)
        tb.addWidget(anim_chk)

        # 그룹탭 모양 타입 선택
        tb.addWidget(QLabel(" 모양: "))
        style_combo = QComboBox()
        # (표시 이름, 스타일 값) 순서 = 타입1/2/3
        self._styles = [
            ("라운딩", GroupTabWidget.STYLE_ROUNDED),
            ("왼쪽 색상", GroupTabWidget.STYLE_LEFT_COLOR),
            ("네이티브", GroupTabWidget.STYLE_PLAIN),
        ]
        for name, _ in self._styles:
            style_combo.addItem(name)
        style_combo.currentIndexChanged.connect(self._on_style_changed)
        tb.addWidget(style_combo)

        tb.addWidget(self._btn("◀ 그룹", self.tabs.previousGroup))
        tb.addWidget(self._btn("그룹 ▶", self.tabs.nextGroup))

        # 아이콘 변경 버튼들 (두 번째 줄)
        self.addToolBarBreak(Qt.BottomToolBarArea)
        tb2 = QToolBar("icons")
        tb2.setMovable(False)
        self.addToolBar(Qt.BottomToolBarArea, tb2)
        tb2.addWidget(QLabel(" 현재 탭 아이콘: "))
        for text, kind in [("색 점", "color"), ("Loading", "loading"),
                           ("Gear", "gear"), ("없음", "none")]:
            tb2.addWidget(self._btn(
                text, lambda checked=False, k=kind: self._set_current_icon(k)))

    def _btn(self, text, slot):
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    # "탭 추가" 버튼으로 넣을 때 쓸, 길이가 다양한 이름 후보들
    _NAME_POOL = [
        "새 탭", "Report", "분석", "Settings",
        "아주 긴 이름의 탭입니다", "X", "모니터링", "Dashboard 2",
    ]

    def _add_tab(self, name, group, kind="color"):
        icon = _group_icon(group) if kind == "color" else None
        idx = self.tabs.addGroupTab(_make_page(name, group), name, group, icon)
        if kind == "loading":
            self.tabs.setTabLoading(idx)
        elif kind == "gear":
            self.tabs.setTabGear(idx)
        self.tabs.setCurrentIndex(idx)
        return idx

    def _on_add(self):
        name = self._NAME_POOL[self._tab_counter % len(self._NAME_POOL)]
        self._tab_counter += 1
        self._add_tab("{} {}".format(name, self._tab_counter),
                      self.group_spin.value())

    def _on_remove(self):
        idx = self.tabs.currentIndex()
        if idx != -1:
            self.tabs.removeTab(idx)

    def _on_style_changed(self, index):
        """그룹탭 모양 타입을 전환한다."""
        name, style = self._styles[index]
        self.tabs.setGroupStyle(style)
        self.statusBar().showMessage("그룹탭 모양: {}".format(name))

    def _on_group_changed(self, group):
        self.statusBar().showMessage("현재 그룹: {}".format(group))

    def _set_current_icon(self, kind):
        """현재 탭의 아이콘을 없음/색 점/Loading GIF/Gear GIF 로 바꾼다."""
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        self.tabs.setTabMovie(idx, None)   # 진행 중인 GIF 가 있으면 해제
        if kind == "color":
            self.tabs.setTabIcon(idx, _group_icon(self.tabs.tabGroup(idx)))
        elif kind == "none":
            self.tabs.setTabIcon(idx, QIcon())
        elif kind == "loading":
            self.tabs.setTabLoading(idx)
        elif kind == "gear":
            self.tabs.setTabGear(idx)


def main():
    app = QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


if __name__ == "__main__":
    main()
