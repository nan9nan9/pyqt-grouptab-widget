# -*- coding: utf-8 -*-
"""pytest 공용 설정.

디스플레이가 없는 CI 에서도 돌도록 offscreen 플랫폼을 기본값으로 지정하고,
세션 단위 QApplication 을 제공한다. (pytest-qt 없이도 동작)
"""
import os

# QApplication 생성 전에 플랫폼을 정해야 하므로 import 시점에 설정한다.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from qtpy.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
