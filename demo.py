# -*- coding: utf-8 -*-
"""GroupTabWidget 데모 앱.

실행:
    python demo.py

특정 바인딩으로 실행하려면 QT_API 환경변수를 지정한다.
    QT_API=pyqt6 python demo.py
    QT_API=pyside6 python demo.py
"""

import sys

from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon, QPixmap, QColor, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QLabel,
    QCheckBox,
)

from grouptabwidget import GroupTabWidget


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


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GroupTabWidget 데모")
        self.resize(720, 360)

        self._tab_counter = 0

        layout = QVBoxLayout(self)

        # 그룹 탭 위젯 (탭마다 페이지가 붙는다)
        self.tabs = GroupTabWidget()
        self.tabs.tabBar().setExpanding(False)
        # 닫기 버튼 클릭 시 해당 탭 제거
        self.tabs.tabCloseRequested.connect(self.tabs.removeTab)
        layout.addWidget(self.tabs)

        # 컨트롤 영역
        controls = QHBoxLayout()
        controls.addWidget(QLabel("그룹:"))

        self.group_spin = QSpinBox()
        self.group_spin.setRange(1, 9)
        self.group_spin.setValue(1)
        controls.addWidget(self.group_spin)

        add_btn = QPushButton("탭 추가")
        add_btn.clicked.connect(self._on_add)
        controls.addWidget(add_btn)

        remove_btn = QPushButton("현재 탭 삭제")
        remove_btn.clicked.connect(self._on_remove)
        controls.addWidget(remove_btn)

        accent_chk = QCheckBox("상단 액센트 바")
        accent_chk.setChecked(self.tabs.topAccentEnabled())
        accent_chk.toggled.connect(self.tabs.setTopAccentEnabled)
        controls.addWidget(accent_chk)

        close_chk = QCheckBox("닫기 버튼")
        close_chk.toggled.connect(self.tabs.setTabsClosable)
        controls.addWidget(close_chk)

        controls.addStretch(1)

        # 그룹 전환 버튼
        prev_grp = QPushButton("◀ 그룹")
        prev_grp.clicked.connect(self.tabs.previousGroup)
        controls.addWidget(prev_grp)

        next_grp = QPushButton("그룹 ▶")
        next_grp.clicked.connect(self.tabs.nextGroup)
        controls.addWidget(next_grp)

        layout.addLayout(controls)

        # 현재 탭 아이콘 변경 버튼들 (없음 / 색 점 / Loading GIF / Gear GIF)
        icon_controls = QHBoxLayout()
        icon_controls.addWidget(QLabel("현재 탭 아이콘:"))
        kinds = [("색 점", "color"), ("Loading", "loading"),
                 ("Gear", "gear"), ("없음", "none")]
        for text, kind in kinds:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked=False, k=kind: self._set_current_icon(k))
            icon_controls.addWidget(btn)
        icon_controls.addStretch(1)
        layout.addLayout(icon_controls)

        # 현재 그룹 표시
        self.group_label = QLabel()
        self.tabs.currentGroupChanged.connect(self._on_group_changed)
        layout.addWidget(self.group_label)

        hint = QLabel("탭을 드래그하면 같은 그룹 전체가 페이지와 함께 이동합니다.")
        layout.addWidget(hint)

        # 초기 샘플 탭 구성: 이름 길이와 아이콘 종류를 다양하게.
        #   color = 그룹 색 점 / none = 아이콘 없음 / loading, gear = GIF
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

    def _on_group_changed(self, group):
        self.group_label.setText("현재 그룹: {}".format(group))

    def _set_current_icon(self, kind):
        """현재 탭의 아이콘을 없음/색 점/Loading GIF/Gear GIF 로 바꾼다."""
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        # 진행 중인 GIF 가 있으면 먼저 해제
        self.tabs.setTabMovie(idx, None)
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
