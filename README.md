# GroupTab Widget

그룹핑이 가능한 탭 위젯입니다. 두 가지 클래스를 제공합니다.

- **`GroupTabBar`** (`grouptab.GroupTabBar`) — `QTabBar` 기반 탭 바.
- **`GroupTabWidget`** (`grouptab.GroupTabWidget`) — `QTabWidget` 기반으로, 탭마다
  **위젯(페이지)을 등록**할 수 있습니다. 내부적으로 `GroupTabBar` 를 탭 바로
  사용합니다.

일반 탭의 모양을 그대로 유지하면서, 각 탭에 **그룹 번호**를 부여하여 그룹
단위로 동작하게 합니다.

- ✅ **PyQt5 / PyQt6 / PySide2 / PySide6 모두 호환** (`qtpy` 사용)
- ✅ `QTabBar` / `QTabWidget` 기반 — 기본 탭 모양 유지
- ✅ 탭 아이콘 지원: **이미지 / 색 점 / 기본 제공 Loading·Gear / 사용자 GIF**
- ✅ **닫기 버튼**(`setTabsClosable(True)`) 지원 — 라벨과 겹치지 않게 공간 자동 확보
- ✅ 그룹에 탭 추가 시 해당 그룹 블록의 **마지막 순서**에 삽입
- ✅ 드래그 시 그룹이 **블록 단위로 함께 이동** + **슬라이드 애니메이션**
  (`GroupTabWidget` 은 페이지도 함께 이동)
- ✅ 탭을 선택하면 **선택된 그룹의 탭 전체가 살짝 올라오고 글씨가 굵게(Bold)** 표시
- ✅ 선택된 그룹 탭 **윗부분에 액센트 바**(굵은 색 표시) — `setTopAccentEnabled(bool)` 로 on/off

## 설치

```bash
pip install -e .          # qtpy 와 함께 grouptab 패키지 설치
# 그리고 PyQt5 / PyQt6 / PySide2 / PySide6 중 하나가 설치되어 있어야 합니다.
```

설치 없이 쓰려면 `src/` 를 `PYTHONPATH` 에 추가하거나, 예제처럼 경로를 등록하면 됩니다.

## 디렉토리 구조

```
src/grouptab/          # 패키지
  __init__.py          # GroupTabBar, GroupTabWidget export
  grouptabbar.py
  grouptabwidget.py
  assets/              # 기본 제공 GIF (loading.gif, gear.gif)
examples/
  basic_example.py     # 데모 앱
pyproject.toml
```

## 데모 실행

```bash
python examples/basic_example.py

# 특정 바인딩으로 실행
QT_API=pyqt6   python examples/basic_example.py
QT_API=pyside6 python examples/basic_example.py
```

데모에는 그룹별 색상 아이콘 / 아이콘 없는 탭 / **애니메이션 GIF 아이콘**이
섞여 있고, "현재 탭 아이콘" 버튼(색 점 / Loading / Gear / 없음)으로 바로
바꿔볼 수 있습니다. 그룹 전환 버튼(◀ 그룹 / 그룹 ▶)과 상단 액센트 바 토글도
있습니다.

기본 제공 GIF(`loading.gif` 회전 스피너, `gear.gif` 회전 톱니바퀴)는
패키지(`src/grouptab/assets/`)에 포함되어 있어 `setTabLoading()` / `setTabGear()`
로 바로 사용할 수 있습니다.

## 사용법

### GroupTabWidget (탭마다 위젯 등록)

```python
from qtpy.QtWidgets import QLabel
from grouptab import GroupTabWidget

tabs = GroupTabWidget()

# addGroupTab(위젯, 라벨, 그룹번호) — 그룹의 마지막 순서에 추가
tabs.addGroupTab(QLabel("페이지1"), "Tab1", 1)
tabs.addGroupTab(QLabel("페이지2"), "Tab2", 1)
tabs.addGroupTab(QLabel("페이지3"), "Tab3", 2)
tabs.addGroupTab(QLabel("페이지4"), "Tab4", 1)   # 탭 순서: Tab1, Tab2, Tab4, Tab3

# 아이콘도 함께 지정 가능
from qtpy.QtGui import QIcon
tabs.addGroupTab(QLabel("페이지5"), "Tab5", 2, QIcon("icon.png"))
# 또는 나중에: tabs.setTabIcon(index, QIcon("icon.png"))

# 기본 제공 애니메이션 아이콘 (한 줄)
tabs.setTabLoading(0)   # 회전 스피너
tabs.setTabGear(1)      # 회전 톱니바퀴

# 사용자 지정 애니메이션(GIF) 아이콘 — QMovie 또는 파일 경로
from qtpy.QtGui import QMovie
tabs.setTabMovie(2, "anim.gif")           # 경로
tabs.setTabMovie(2, QMovie("anim.gif"))   # QMovie
tabs.setTabMovie(2, None)                  # 해제

# 닫기 버튼 (QTabWidget 기본 기능)
tabs.setTabsClosable(True)
tabs.tabCloseRequested.connect(tabs.removeTab)

# QTabWidget 의 기능을 그대로 사용 가능
tabs.currentWidget()
tabs.removeTab(0)
```

탭을 드래그하면 그 탭이 속한 그룹 전체가 **페이지와 함께** 하나의 블록처럼
이동합니다. 그룹 내부 탭들의 상대 순서는 항상 유지됩니다.

### GroupTabBar (탭 바만 필요할 때)

```python
from grouptab import GroupTabBar

tabbar = GroupTabBar()
tabbar.addGroupTab("Tab1", 1)   # addGroupTab(텍스트, 그룹번호)
tabbar.addGroupTab("Tab2", 1)
tabbar.addGroupTab("Tab3", 2)
tabbar.addGroupTab("Tab4", 1)   # 결과 순서: Tab1, Tab2, Tab4, Tab3
```

## 주요 API

### GroupTabWidget

| 메서드 | 설명 |
| --- | --- |
| `addGroupTab(widget, label, group)` | 그룹의 마지막 순서에 (위젯, 라벨) 탭 추가 |
| `insertGroupTab(index, widget, label, group)` | 지정 위치에 (위젯, 라벨) 탭 삽입 |
| `tabGroup(index)` / `groupTabIndices(group)` / `groupOrder()` | 그룹 정보 조회 |
| `groupTabBar()` | 내부 `GroupTabBar` 반환 |
| `currentGroup()` | 현재 선택된 탭의 그룹 |
| `setCurrentGroup(group)` | 해당 그룹으로 전환 (그룹별 마지막 탭, 없으면 첫 탭) |
| `nextGroup()` / `previousGroup()` | 다음/이전 그룹으로 순환 전환 |
| `setTabLoading(index)` / `setTabGear(index)` | 기본 제공 애니메이션 아이콘(회전 스피너/톱니바퀴) |
| `setTabMovie(index, movie)` / `tabMovie(index)` | 탭에 사용자 지정 애니메이션(GIF) 아이콘 설정/조회 (`None`이면 해제) |
| `setTopAccentEnabled(bool)` / `topAccentEnabled()` | 상단 액센트 바 on/off (기본 on) |
| `setTopAccentColor(color)` | 액센트 바 색상 (None 이면 팔레트 highlight) |
| `setTabsClosable(bool)` | 닫기 버튼 표시 on/off |
| `setMoveAnimationEnabled(bool)` / `moveAnimationEnabled()` | 그룹 이동 슬라이드 애니메이션 on/off (기본 on) |
| (그 외) | `QTabWidget` 의 모든 메서드 사용 가능 |

> **원격 X 환경(Exceed TurboX / VNC / SSH X11) 팁**: 매 프레임 화면 전송이
> 느린 원격 디스플레이에서는 이동 애니메이션이 끊기거나 잔상이 남을 수 있습니다.
> 이때 `tabs.setMoveAnimationEnabled(False)` 로 끄면 즉시 이동해 깔끔합니다.

### GroupTabBar

| 메서드 | 설명 |
| --- | --- |
| `addGroupTab(text, group)` | 그룹의 마지막 순서에 탭 추가 → 추가된 인덱스 반환 |
| `insertGroupTab(index, text, group)` | 지정 위치에 그룹 탭 삽입 |
| `tabGroup(index)` | 해당 탭의 그룹 번호 반환 |
| `groupTabIndices(group)` | 해당 그룹에 속한 탭 인덱스 목록 |
| `groupOrder()` | 현재 표시 순서대로의 그룹 목록 |

### 시그널

| 시그널 | 설명 |
| --- | --- |
| `groupMoved(group, oldIndex, newIndex)` | 그룹 블록이 드래그로 이동했을 때 방출 |
| `currentGroupChanged(group)` | 선택된 탭의 그룹이 바뀌었을 때 방출 |

> 위 그룹 전환 API(`currentGroup` / `setCurrentGroup` / `nextGroup` /
> `previousGroup`)와 `currentGroupChanged` 시그널은 `GroupTabBar` 에도
> 동일하게 있습니다.

## 동작 방식

- 각 탭의 그룹 정보는 `setTabData()` 로 저장되어 이동/삽입 시에도 따라다닙니다.
- 같은 그룹의 탭은 항상 인접(연속)하도록 유지되어 하나의 블록을 이룹니다.
- 단일 탭의 네이티브 드래그는 마우스 이벤트에서 가로채 막고, 대신
  `moveTab()` 으로 그룹 전체를 함께 옮깁니다.
- 탭을 직접 그리므로, `paintEvent` 시작에서 배경을 지워 이동 후 잔상이
  남지 않게 합니다.
- `setTabsClosable(True)` 일 때 닫기 버튼 폭(`PM_TabCloseIndicatorWidth`)만큼
  `tabSizeHint` 에 공간을 더하고, 라벨은 그 영역을 제외하고 그려 겹침을
  방지합니다.
- 그룹 이동 시 `QVariantAnimation` 으로 각 탭의 그리기 위치를 이전 위치에서
  새 위치로 보간하여 자연스러운 슬라이드 효과를 줍니다.
- 선택된 탭이 속한 그룹의 탭들은 원래 QTabBar 의 선택 탭처럼 위로 올라오며,
  바 높이를 `_group_raise`(기본 3px)만큼 키워 위쪽 여백을 확보하고 일반 탭은
  그만큼 내려 그려서, 선택 그룹이 좀 더 또렷하게 올라오게 합니다.
- `GroupTabWidget` 은 `QTabWidget` 에 `GroupTabBar` 를 탭 바로 끼워서 만듭니다.
  그룹 이동 시 `moveTab()` 이 방출하는 `tabMoved` 시그널로 `QTabWidget` 이
  페이지(스택)를 자동으로 같이 옮기므로, 탭과 페이지가 항상 일치합니다.
