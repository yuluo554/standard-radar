"""测试全局夹具：源码态自举。

仓库直接跑 pytest 时把 src/ 加入 sys.path（等价于已安装），保证"源码态=安装态"；
安装态（editable/site-packages）不受影响。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
