"""双源适配器公共契约与请求常量（M2 交付实现；见 plan/03 §2.1）。

- 每库一个独立适配器（gb.py / hb.py），适配器之间不共享字段假设；
- 失败隔离：某个库超时 / 非 200 / 解析失败 / 映射失败时，单列原因码（REASON_*），
  不影响另一库本轮产出；两库全失败才整轮失败（exit 1）；
- 请求纪律：UA 自标识、最小请求间隔、超时与有限重试、翻页上限；
  对账"接口报的 total vs 实际取到条数"（未取全必须在轮次元数据显式记录）；
- 参数"一处定义"：本模块常量是全项目唯一来源，CLI 默认值/文档数字均引用此处，不另写副本。
"""

from __future__ import annotations

# ── 请求与翻页参数（一处定义；M2 按真实抓取复核后冻结） ──
PAGE_SIZE = 500  # 每页条数（接口实测上限 500，见 data/README.md）
MAX_PAGES_DEFAULT = 5  # 单库单轮翻页上限（设计决策：聚焦最新发布批次）
MIN_INTERVAL_S = 1.0  # 相邻请求最小间隔（合规限频）
TIMEOUT_S = 15.0  # 单次请求超时（秒）
RETRIES = 2  # 重试次数（指数退避）

# UA 自标识（可被平台识别与联系；版本号不进 UA，避免与包版本漂移）
USER_AGENT = "standard-radar (+https://github.com/yuluo554/standard-radar; local research tool)"

# ── 列表接口（实测 2026-10-15，见 data/README.md） ──
GB_LIST_URL = "https://std.samr.gov.cn/gb/search/gbQueryPage"
HB_LIST_URL = "https://std.samr.gov.cn/hb/search/hbPage"

# ── 失败原因码（单列，不吞） ──
REASON_TIMEOUT = "timeout"
REASON_HTTP = "http_status"
REASON_PARSE = "parse_error"
REASON_MAPPING = "mapping_skip"
