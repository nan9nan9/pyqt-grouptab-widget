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
- ✅ 드래그 시 그룹이 **블록 단위로 함께 이동** — 잡은 그룹이 네이티브
  탭처럼 **커서를 실시간으로 따라옵니다** (`GroupTabWidget` 은 페이지도 함께 이동)
- ✅ 탭을 선택하면 **선택된 그룹의 탭 전체가 살짝 올라오고 글씨가 굵게(Bold)** 표시
- ✅ 선택된 그룹 탭 **윗부분에 액센트 바**(굵은 색 표시) — `setTopAccentEnabled(bool)` 로 on/off
- ✅ 그룹 구분 **모양 3종** 선택 (`setGroupStyle`): 양끝 라운딩 블록 / 그룹 첫 탭 왼쪽 색상 삼각형 / 네이티브
- ✅ 그룹 이동 시 밀려나는 그룹의 **슬라이드 애니메이션** — `setGroupMoveAnimationEnabled(bool)` 로 on/off (기본 on)
- ✅ **그룹 무결성 보장**: 탭 추가/삽입은 전용 API로만. 상속된 `addTab()`/`insertTab()`
  직접 호출은 그룹 태그 없는 탭이 생겨 그룹 모델이 깨지므로 **차단**됩니다(`RuntimeError`).

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
바꿔볼 수 있습니다. 그룹 전환 버튼(◀ 그룹 / 그룹 ▶), 상단 액센트 바 토글,
**그룹 모양 선택 콤보**(라운딩 / 왼쪽 색상 / 네이티브), **이동 애니메이션 토글**도
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

# 닫기 버튼
tabs.setTabsClosable(True)
tabs.tabCloseRequested.connect(tabs.removeTab)

# 제거 — 전용 API
tabs.removeTab(0)          # 단일 탭(페이지 포함) 제거
tabs.removeGroupTab(0)     # removeTab 과 동일(그룹 API 대칭용 이름)
tabs.removeGroup(1)        # 그룹 1 의 모든 탭(과 페이지)을 한 번에 제거

# 조회 등 QTabWidget 의 나머지 기능은 그대로 사용 가능
tabs.currentWidget()
tabs.setCurrentGroup(2)
```

> **그룹 관리는 전용 API로만 하세요.** 그룹 무결성을 위해 탭 추가/삽입은
> `addGroupTab()` / `insertGroupTab()` 로만 해야 합니다. 상속된
> `addTab()` / `insertTab()` 을 직접 호출하면 그룹 태그가 없는 탭이 생겨 그룹
> 모델이 깨지므로, 이 두 메서드는 막혀 있어 호출 시 `RuntimeError` 가
> 발생합니다. 제거는 `removeTab()` / `removeGroupTab()`(단일 탭) 또는
> `removeGroup(group)`(그룹 전체)를 사용하세요. (`GroupTabBar` 도 동일하게
> `addTab`/`insertTab` 이 막혀 있고 `removeGroup` 을 제공합니다.)

```python
# ❌ 막혀 있음 — RuntimeError 발생
tabs.addTab(QLabel("x"), "Tab")            # -> addGroupTab(...) 을 쓰라는 안내
tabs.insertTab(0, QLabel("x"), "Tab")      # -> insertGroupTab(...) 을 쓰라는 안내
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

tabbar.removeGroup(1)           # 그룹 1 의 모든 탭 제거
# tabbar.addTab("x") / insertTab(...) 은 막혀 있음 → addGroupTab/insertGroupTab 사용
```

## 주요 API

### GroupTabWidget

| 메서드 | 설명 |
| --- | --- |
| `addGroupTab(widget, label, group[, icon])` | 그룹의 마지막 순서에 (위젯, 라벨) 탭 추가 |
| `insertGroupTab(index, widget, label, group[, icon])` | 지정 위치에 (위젯, 라벨) 탭 삽입 |
| `removeGroupTab(index)` | 단일 탭(과 페이지) 제거 (`removeTab` 과 동일) |
| `removeGroup(group)` | 그룹의 모든 탭(과 페이지)을 한 번에 제거 → 제거 수 반환 |
| `tabGroup(index)` / `groupTabIndices(group)` / `groupOrder()` | 그룹 정보 조회 |
| `groupTabBar()` | 내부 `GroupTabBar` 반환 |
| `currentGroup()` | 현재 선택된 탭의 그룹 |
| `setCurrentGroup(group)` | 해당 그룹으로 전환 (그룹별 마지막 탭, 없으면 첫 탭) |
| `nextGroup()` / `previousGroup()` | 다음/이전 그룹으로 순환 전환 |
| `setGroupStyle(style)` / `groupStyle()` | 그룹 모양: `STYLE_ROUNDED` / `STYLE_LEFT_COLOR` / `STYLE_PLAIN` |
| `setGroupColor(group, color)` | `STYLE_LEFT_COLOR` 에서 그룹별 마커 색 지정 (None 이면 기본색 순환) |
| `setGroupMoveAnimationEnabled(bool)` / `groupMoveAnimationEnabled()` | 그룹 이동 슬라이드 애니메이션 on/off (기본 on) |
| `setTabLoading(index)` / `setTabGear(index)` | 기본 제공 애니메이션 아이콘(회전 스피너/톱니바퀴) |
| `setTabMovie(index, movie)` / `tabMovie(index)` | 탭에 사용자 지정 애니메이션(GIF) 아이콘 설정/조회 (`None`이면 해제) |
| `setTopAccentEnabled(bool)` / `topAccentEnabled()` | 상단 액센트 바 on/off (기본 on) |
| `setTopAccentColor(color)` | 액센트 바 색상 (None 이면 팔레트 highlight) |
| `setTabsClosable(bool)` | 닫기 버튼 표시 on/off |
| `addTab()` / `insertTab()` | ⛔ **막힘** — 그룹 무결성 보호를 위해 `RuntimeError`. `addGroupTab`/`insertGroupTab` 사용 |
| (그 외) | `removeTab` 등 `QTabWidget` 의 나머지 메서드는 그대로 사용 가능 |

> **그룹 이동 애니메이션과 원격 X 환경**: 잡은 그룹은 커서를 1:1 로 따라가고,
> 밀려나는 그룹은 짧은 슬라이드 애니메이션(기본 160ms)으로 이동합니다. 원격
> 디스플레이(Exceed TurboX / VNC / SSH X11)에서 프레임 전송 부담을 줄이려면
> `setGroupMoveAnimationEnabled(False)` 로 끄면 즉시 이동합니다. 이 옵션은 Qt
> 전역 애니메이션 설정과 무관하게 이 값만으로 제어됩니다.

### GroupTabBar

| 메서드 | 설명 |
| --- | --- |
| `addGroupTab(text, group[, icon])` | 그룹의 마지막 순서에 탭 추가 → 추가된 인덱스 반환 |
| `insertGroupTab(index, text, group[, icon])` | 지정 위치에 그룹 탭 삽입 |
| `removeGroup(group)` | 그룹의 모든 탭 제거 → 제거 수 반환 |
| `tabGroup(index)` | 해당 탭의 그룹 번호 반환 |
| `groupTabIndices(group)` | 해당 그룹에 속한 탭 인덱스 목록 |
| `groupOrder()` | 현재 표시 순서대로의 그룹 목록 |
| `addTab()` / `insertTab()` | ⛔ **막힘**(`RuntimeError`) — `addGroupTab`/`insertGroupTab` 사용 |
| `setGroupStyle` / `setGroupColor` / `setGroupMoveAnimationEnabled` / `setGroupCornerRadius` | 모양·색·애니메이션·모서리 반경 설정 (`GroupTabWidget` 과 동일) |

### 시그널

| 시그널 | 설명 |
| --- | --- |
| `groupMoved(group, oldIndex, newIndex)` | 그룹 블록이 드래그로 이동했을 때 방출 |
| `currentGroupChanged(group)` | 선택된 탭의 그룹이 바뀌었을 때 방출 |

> 위 그룹 전환 API(`currentGroup` / `setCurrentGroup` / `nextGroup` /
> `previousGroup`)와 `currentGroupChanged` 시그널은 `GroupTabBar` 에도
> 동일하게 있습니다.

## 동작 방식

- 각 탭의 그룹 정보는 `setTabData()`(그룹 번호 + 고유 uid)로 저장되어 이동/삽입 시에도 따라다닙니다.
- 같은 그룹의 탭은 항상 인접(연속)하도록 유지되어 하나의 블록을 이룹니다. 이
  불변식을 지키려고, 그룹 태그를 붙이지 않는 네이티브 `addTab()`/`insertTab()`
  직접 호출을 막고(`RuntimeError`) 추가/삽입은 `addGroupTab`/`insertGroupTab`
  로만 이뤄지게 합니다. 내부적으로는 `super().insertTab()` 으로 추가한 뒤 그룹을 태깅합니다.
- 그룹을 옮기면 밀려나는 그룹(과 드롭 시 잡았던 그룹)은 옛 위치에서 새 슬롯으로
  짧게 미끄러지는 슬라이드 애니메이션(`QVariantAnimation`)으로 이동합니다.
- 드래그는 전부 직접 처리하므로 네이티브 이동(`setMovable`)은 꺼서, 네이티브
  단일탭 드래그가 끼어드는 충돌(탭은 고정인데 닫기 버튼만 움직이는 현상)을
  원천 차단합니다. 드래그 중에는 잡은 그룹의 탭들을 커서 위치만큼 가로로
  오프셋하여 그려(네이티브 탭처럼 커서를 1:1 로 따라옴), 다른 그룹의 중심을
  넘으면 `moveTab()` 으로 순서를 바꿉니다.
- 탭을 직접 그리므로, `paintEvent` 시작에서 배경을 지워 이동 후 잔상이
  남지 않게 합니다.
- 닫기 버튼(X)은 **자식 위젯이 아니라 `paintEvent` 에서 직접 그립니다**
  (`PE_IndicatorTabClose`). 자식 위젯은 항상 부모 paint 위에 그려져, 드래그로
  그룹을 띄울 때 깔리는 탭의 X 가 위로 뚫고 나오는 z-order 충돌이 생기는데,
  직접 그리면 X 가 탭과 같은 레이어라 paint 순서대로 자연스럽게 정렬됩니다.
  클릭은 마우스 이벤트로 직접 판정해 `tabCloseRequested` 를 방출합니다.
- 선택된 탭이 속한 그룹의 탭들은 원래 QTabBar 의 선택 탭처럼 위로 올라오며,
  바 높이를 `_group_raise`(기본 3px)만큼 키워 위쪽 여백을 확보하고 일반 탭은
  그만큼 내려 그려서, 선택 그룹이 좀 더 또렷하게 올라오게 합니다.
- `GroupTabWidget` 은 `QTabWidget` 에 `GroupTabBar` 를 탭 바로 끼워서 만듭니다.
  그룹 이동 시 `moveTab()` 이 방출하는 `tabMoved` 시그널로 `QTabWidget` 이
  페이지(스택)를 자동으로 같이 옮기므로, 탭과 페이지가 항상 일치합니다.
