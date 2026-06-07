# 热门题材映射与找股方案

## 目标

构建一条可渐进落地的题材找股链路：

- `全球热门题材` 由全球 ETF / 主题代理生成
- `本地热门题材` 由各地区本地行业指数生成
- 每个地区通过 `LLM + skill` 将题材映射成股票 API 可执行的筛选条件
- 系统通过统一股票 API 直接拉取该地区符合题材方向的股票
- `IBKR` 仅负责自动化交易执行，不承担主研究数据源职责

这套方案的目标不是让 LLM 直接选股，而是让 LLM 生成题材到本地筛选条件的映射配置。

## 设计原则

- 题材由系统统一定义，不由数据源定义。
- 本地热门题材优先来自本地行业指数，不用股票涨幅反推行业。
- 全球热门题材是本地题材的补充，后续本地找股时两者都参与。
- 找股尽量通过一个主股票 API 完成，不为每个题材单独接额外股票源。
- LLM 只生成映射草案，系统负责校验、缓存和执行。
- 映射不是每天全量重做，而是按触发条件重建。

## 核心对象

### 1. `theme_registry`

标准题材主表。

建议字段：

- `theme_id`
- `theme_name`
- `theme_group`
- `description`
- `status`

示例：

- `semiconductor`
- `ai_compute`
- `power`
- `defense`
- `gold`

说明：

- `theme_id` 必须稳定
- 第一版优先用稳定母题材，不要一开始把题材拆得太细

### 2. `market_mode_registry`

定义每个市场当前如何生成本地题材、调用哪个映射 skill、使用哪个股票 API。

建议字段：

- `market_code`
- `local_index_enabled`
- `local_index_source`
- `mapping_skill_name`
- `stock_api_source`
- `status`

说明：

- `local_index_enabled=true` 表示该市场已接通本地行业指数
- 暂时没有本地行业指数的市场，仍可保留全球题材补充能力

### 3. `global_theme_proxy_registry`

全球题材代理表。

建议字段：

- `theme_id`
- `proxy_type`
- `proxy_code`
- `weight`
- `source`
- `status`

示例：

- `semiconductor -> SOXX / SMH`
- `power -> XLU`
- `defense -> ITA / PPA`
- `gold -> GLD / GDX`

### 4. `market_local_index_registry`

本地行业指数主数据表。

建议字段：

- `market_code`
- `index_code`
- `index_name`
- `benchmark_index_code`
- `provider`
- `currency`
- `status`

说明：

- 每个市场都要指定一个宽基指数，用于计算行业指数相对强弱
- 只录入当前能免费或稳定获取的数据

### 5. `market_theme_mapping_cache`

LLM 为某个市场生成的题材映射缓存。

建议字段：

- `market_code`
- `theme_id`
- `api_source`
- `sector_filters`
- `industry_filters`
- `exchange_filters`
- `query_payload`
- `confidence`
- `reason`
- `status`
- `effective_from`
- `effective_to`

说明：

- 这是后续 API 找股的直接输入
- 不建议每次请求实时生成，应该先缓存后使用

### 6. `market_theme_daily`

每天每个市场最终用于找股的题材方向表。

建议字段：

- `trade_date`
- `market_code`
- `theme_id`
- `theme_name`
- `source`
- `local_score`
- `global_score`
- `combined_score`
- `supporting_refs`

说明：

- `source` 可取 `local`、`global`、`both`
- 这张表是题材层和选股层之间的主桥接表

## 数据源分工

### 1. 全球热门题材

数据源：

- `yfinance`

用途：

- 拉取全球行业 ETF / 主题 ETF 的日线行情
- 生成 `global_theme_daily`

第一版只做少数稳定代理：

- `semiconductor`
- `power`
- `defense`
- `gold`
- `ai_compute`

### 2. 本地热门题材

数据源：

- 各地区能免费或开源稳定拿到的本地行业指数

用途：

- 生成 `local_theme_daily`

边界：

- 只对接当前能稳定获取的地区
- 不能稳定获取的地区，先不产出本地题材分数

### 3. 股票查询 API

数据源：

- 一个统一主股票 API，例如 `Twelve Data`

用途：

- 根据映射后的 `sector / industry / exchange` 条件拉取本地股票

说明：

- 这里的主股票 API 负责最终返回股票列表
- 不要求原生理解自定义题材名

### 4. 自动交易执行

数据源：

- `IBKR`

用途：

- 接收最终买卖动作
- 不承担主题材研究职责

## 每日流程

### 步骤 1. 生成全球热门题材

输入：

- `global_theme_proxy_registry`
- ETF / 主题代理行情

处理：

- 计算每个代理最近 `1d / 5d / 20d` 表现
- 合成每个 `theme_id` 的 `global_score`

输出：

- `global_theme_daily`

### 步骤 2. 生成本地热门题材

输入：

- `market_local_index_registry`
- 各市场本地行业指数日线

处理：

- 计算行业指数相对宽基指数的强弱
- 在市场内部排序
- 将行业指数映射到标准题材

建议的第一版分数：

```text
local_score =
0.50 * excess_return_5d
+ 0.25 * excess_return_20d
+ 0.15 * persistence
+ 0.10 * volume_confirmation
```

输出：

- `local_theme_daily`

说明：

- `volume_confirmation` 无数据时可降权或记 0

### 步骤 3. 生成市场最终题材方向

输入：

- `local_theme_daily`
- `global_theme_daily`

处理：

- 按 `market_code + theme_id` 合并
- 同一题材可同时保留本地和全球分数

建议的第一版合并分数：

```text
combined_score = 0.7 * local_score + 0.3 * global_score
```

规则：

- 仅本地命中，保留
- 仅全球命中，保留
- 本地和全球都命中，合并

输出：

- `market_theme_daily`

说明：

- 这里不需要复杂的题材状态分类
- 题材表的用途是提供后续找股方向

## 地区映射 skill

### 目标

每个地区一个 skill，负责把当天题材方向映射成股票 API 可执行的查询条件。

示例：

- `us_theme_mapper`
- `jp_theme_mapper`
- `tw_theme_mapper`

### 输入

- `market_code`
- 当天 `market_theme_daily`
- 主股票 API 支持的 `sector / industry / exchange` 枚举
- 该市场本地行业指数名称和历史映射样例
- 历史有效映射缓存

### 输出

结构化 JSON：

```json
{
  "market_code": "JP_EQ",
  "theme_id": "semiconductor",
  "filters": {
    "sector": ["Technology"],
    "industry": ["Semiconductors", "Semiconductor Equipment & Materials"],
    "exchange": ["TSE"]
  },
  "confidence": 0.84,
  "reason": "日本本地半导体题材主要集中在设备与材料链"
}
```

### 生成原则

- 优先映射到股票 API 原生支持的字段
- 尽量避免输出 API 不支持的题材名
- 优先复用历史高质量映射
- 新题材先生成草案，再由系统校验

## 映射校验

LLM 映射不能直接生效，必须通过系统校验。

建议至少包含以下规则：

1. `sector / industry / exchange` 必须存在于 API 支持枚举内
2. 查询结果数量不能为 0
3. 查询结果数量不能异常大
4. 与历史映射相比偏移不能过大
5. `confidence` 低于阈值时不自动放行

建议状态：

- `approved`
- `needs_review`
- `rejected`

建议阈值：

- `confidence >= 0.80` 且结果数量正常，自动通过
- 其余进入复核或降级逻辑

## API 找股流程

### 输入

- 某市场当天的 `market_theme_daily`
- 已通过校验的 `market_theme_mapping_cache`

### 过程

1. 读取该市场所有有效题材
2. 按 `theme_id` 取映射缓存
3. 直接调用统一股票 API
4. 返回每个题材对应的股票列表
5. 合并去重
6. 进入后续股票评分逻辑

### 输出

- `market_theme_stock_candidates_daily`

建议字段：

- `trade_date`
- `market_code`
- `theme_id`
- `symbol`
- `source`
- `query_payload`
- `match_reason`

说明：

- 这张表表示“因题材命中而进入候选方向”的股票
- 不是最终买入列表

## 缓存与重建策略

映射缓存不应每天全量重建。

建议触发条件：

1. 出现新题材
2. 某题材查询结果连续异常
3. 本地行业指数结构明显变化
4. 每周定期重审
5. 人工手动触发

建议策略：

- 日常运行直接用缓存
- 只有命中触发条件时才重跑映射 skill

## 第一版范围

建议第一版只做：

- 市场：`US_EQ`、`JP_EQ`、`TW_EQ`
- 题材：`semiconductor`、`power`、`defense`、`gold`、`ai_compute`
- 全球题材源：`yfinance`
- 本地行业指数：仅接已确认免费可用的市场
- 股票查询：固定一个主股票 API
- 执行层：`IBKR`

不建议第一版做：

- 过细的动态子题材
- 多个股票 API 同时做主源
- 实时逐次生成映射
- 题材直接决定买入

## 推荐任务拆分

### 阶段 1. 数据与配置层

- 建 `theme_registry`
- 建 `market_mode_registry`
- 建 `global_theme_proxy_registry`
- 建 `market_local_index_registry`

### 阶段 2. 每日题材计算

- 生成 `global_theme_daily`
- 生成 `local_theme_daily`
- 合并 `market_theme_daily`

### 阶段 3. 映射层

- 为首批市场定义 mapping skill 输入输出格式
- 落地 `market_theme_mapping_cache`
- 完成映射校验逻辑

### 阶段 4. 找股层

- 根据映射缓存调股票 API
- 输出 `market_theme_stock_candidates_daily`
- 将题材候选股票接入后续评分链路

## 风险

主要风险：

- LLM 映射过宽或过窄
- API 的 `industry` 枚举不足以表达细题材
- 某些市场本地行业指数源不稳定
- 题材过细会导致维护成本快速上升

控制方式：

- 第一版只使用稳定母题材
- 强制映射校验
- 只在少数市场先跑通
- 题材找股只作为候选池入口，不直接替代后续评分

## 结论

这套方案的核心不是让 LLM 直接告诉系统买什么，而是：

- 用全球 ETF 和本地行业指数先生成题材方向
- 用每地区 mapping skill 把题材方向转换成统一股票 API 能执行的筛选条件
- 用 API 直接得到该地区符合题材方向的股票
- 再把这些股票交给后续策略评分和交易执行模块

这使系统具备：

- 题材定义统一
- 地区映射可扩展
- 数据源职责清晰
- 后续能平滑接入 `IBKR` 自动化交易
