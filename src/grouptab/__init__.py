# -*- coding: utf-8 -*-
"""grouptab - 그룹핑이 가능한 Qt 탭 위젯.

PyQt5 / PyQt6 / PySide2 / PySide6 호환 (qtpy 추상화).

    from grouptab import GroupTabWidget
    tabs = GroupTabWidget()
    tabs.addGroupTab(page, "Tab1", 1)
"""

from .grouptabbar import GroupTabBar
from .grouptabwidget import GroupTabWidget

__all__ = ["GroupTabBar", "GroupTabWidget"]
