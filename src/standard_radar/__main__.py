"""python -m standard_radar 入口（与 console script 双通路等价，两条通路都要冒烟）。

见 plan/03-架构与技术选型.md §五（编码策略）与 plan/02 §五（桩/转正约定）。
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
