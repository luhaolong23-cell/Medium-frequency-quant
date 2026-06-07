# 全球中频量化交易系统

这是一个面向全球股票市场的中频量化交易系统骨架。当前已经实现到：

`全球市场牛熊判断 -> 牛市市场内优质股综合排名 -> 前5名详细观察池 -> 量能买入信号 -> 纸面自动下单 -> 持仓巡检 -> 卖出和平仓`

当前节奏定义是：

- `市场层日更`
  每天从 `yfinance` 更新全球市场数据，并按当前 Bull Score 规则判断市场状态。
- `选股层日更`
  每天只在已经进入牛市跟踪名单的市场中做优质股综合排名，并更新待交易观察池。
- `交易层日更`
  对观察池执行买入信号、纸面下单和持仓巡检，并在满足卖出条件时纸面平仓。

## 1. 当前已实现能力

### 市场层

- 全球市场主数据同步
- 市场代理标的日线更新
- SQLite / memory 两种存储模式
- mock / yahoo / yfinance / composite 四种 provider 模式
- 每天一次市场状态判断

当前市场牛熊判断只看两个指标：

- `成交量上升`
- `指数连续上涨`

市场状态输出为：

- `BULL`
- `NEUTRAL`
- `BEAR`

### 选股层

只在牛市市场里，先动态发现当日候选股票，再对候选池做优质股综合排名。

当前优质股综合排名主要看四个维度：

- `题材`
- `放量`
- `估值`
- `体量`

当前实现方式：

- `题材`
  由系统从牛市市场候选股中自动学习当日行业热度，并映射成 `theme_tags` 与 `theme_score`
- `放量`
  用最近 5 日平均成交额相对 20 日平均成交额的放量比 `volume_ratio_5d`
- `多源对比`
  在 `composite` 模式下，会从多个数据源拉取同一份行情，对完整度和多源中位数偏差做比较，再选一份最优结果继续运行
- `估值`
  根据股价在 `52 周高低区间` 中的位置自动计算，越靠近区间低位得分越高
- `体量`
  根据市值区间自动计算，目前只保留 `30 亿 ~ 100 亿` 的中小盘股票

系统每天会：

1. 读取历史上已经进入牛市跟踪名单的市场
2. 只对这些市场动态筛选出的种子池拉取股票日线数据
3. 做资格过滤
4. 按四因子综合评分排序
5. 取前 `5` 名写入当日观察池 `watchlist`
6. 对观察池只用 `量能增加` 这一条信号判断是否买入
7. 按当前价格生成固定金额 `10000` 的纸面买单，并形成持仓
8. 对已持仓股票执行持仓巡检
9. 当触发卖出条件时生成纸面卖单并平仓

## 2. 当前运行逻辑

### 每日市场更新

1. `sync_refdata`
2. `ingest_market_bars`
3. `run_regime`

### 每日选股与交易更新

1. 读取历史上已进入跟踪的牛市市场
2. 对这些市场执行 `run_daily_selection`
3. 写入当日 `stock_candidates_daily`
4. 写入当日 `stock_watchlist_daily`
5. 生成当日买入 `trade_signals_daily`
6. 生成当日买入 `paper_orders`
7. 更新 `paper_positions`
8. 执行 `run_position_monitor`
9. 生成当日卖出 `trade_signals_daily` 与 `paper_orders`
10. 把持仓从 `OPEN` 更新到 `CLOSED`

这意味着：

- 市场层每天重算，并默认从 `yfinance` 拉取市场数据
- 候选排名和观察池是每天更新
- 一旦某个市场进入牛市跟踪名单，即使后续日更结果不再是 `BULL`，当前版本也会继续跟踪
- 取消牛市跟踪的逻辑暂未实现，后续会单独补

## 3. 当前已实现的数据存储

### SQLite 表

- `markets`
- `market_proxies`
- `market_features_daily`
- `market_regime_daily`
- `stock_metadata`
- `stock_candidates_daily`
- `stock_watchlist_daily`
- `trade_signals_daily`
- `paper_orders`
- `paper_positions`

其中：

- `stock_candidates_daily`
  保存当日综合排名后的候选股
- `stock_watchlist_daily`
  保存当日前 5 名待交易观察股票
- `trade_signals_daily`
  保存当日买入与卖出信号
- `paper_orders`
  保存纸面买卖订单
- `paper_positions`
  保存当前纸面持仓及 `OPEN / CLOSED` 状态

## 4. 当前已实现接口

### 公共网关接口

- `GET /health`
- `GET /markets/today`
- `GET /candidates/today`
- `GET /candidates/today?market_code=US_EQ`
- `GET /watchlist/today`
- `GET /watchlist/today?market_code=US_EQ`
- `GET /signals/today`
- `GET /orders/today`
- `GET /positions`
- `GET /markets/bull/today`
- `GET /workflow/logs/latest-summary`
- `POST /admin/run-daily`

### 内部服务接口

- `POST /v1/refdata/sync/markets`
- `GET /v1/refdata/markets`
- `POST /v1/market-data/ingest/daily`
- `GET /v1/market-data/features/{market_code}?trade_date=YYYY-MM-DD`
- `POST /v1/regime/run/daily`
- `GET /v1/regime/markets/today`
- `GET /v1/regime/markets/{market_code}/explain?trade_date=YYYY-MM-DD`
- `POST /v1/selection/run-daily`
- `POST /v1/selection/coarse-screen`
  兼容旧入口，当前内部等价于 `run-daily`
- `GET /v1/selection/candidates?trade_date=YYYY-MM-DD`
- `GET /v1/selection/watchlist?trade_date=YYYY-MM-DD`

## 5. 当前配置文件

- `configs/markets.yaml`
  全球市场与代理标的
- `configs/regime_rules.yaml`
  市场牛熊判断规则
- `configs/selection_rules.yaml`
  日选股过滤条件、四因子权重、观察池数量
- `configs/data_sources.yaml`
  多数据源顺序与超时重试配置
- `configs/app.yaml`
  调度时序

## 6. 调度口径

数据源运行模式：

- `mock`
  只用内置模拟数据
- `yahoo`
  只用 Yahoo Finance chart 接口
- `yfinance`
  只用 yfinance
  当前默认 provider
- `composite`
  按 `configs/data_sources.yaml` 的顺序拉取同一份数据并对比选优

当前默认调度是：

- `sync_refdata` 每天运行
- `ingest_market_bars` 每天运行
- `run_regime` 每天运行
- `run_daily_selection` 每天运行
- `run_position_monitor` 每天运行

## 7. 还没实现的部分

当前还没有实现：

- 更稳的跨日行业热度模型
- 真实 fundamentals / 财务报表因子拉取
- 更细的优质股质量评分模型
- 更多买卖点信号
- 真实券商下单执行
- 券商订单回报对账
- 账户资金同步
- 更完整的风险监控

所以当前系统的正确定位是：

`市场层日更 + 牛市内优质股日度综合排名 + 前5观察池 + 量能信号纸面自动交易`。


## 8. 从 0 开始部署后，程序如何运行

如果从一台全新机器开始部署，这套程序的运行顺序是：

1. 准备 Python 运行环境，并安装项目依赖
2. 准备 SQLite 数据库文件目录 `data/`
3. 启动 API 网关，提供前端和调度器统一访问入口
4. 首次执行一轮全量日任务，生成市场、题材、选股、信号、纸面订单和持仓基础快照
5. 启动 scheduler 常驻，之后按天自动执行各个更新任务
6. 前端页面只读 API 和 SQLite 中已经生成的结果，不直接自己算策略

部署后的日常运行链路是：

1. `sync_refdata`
   同步市场主数据和市场代理标的
2. `ingest_market_bars`
   从 `yfinance` 更新市场行情
3. `run_regime`
   重算市场牛熊状态
4. `sync_stock_universe_inventory`
   更新股票清单
5. `prepare_hot_themes`
   生成并存储当天热门题材快照
   首次可做全市场基础快照，后续默认增量更新
6. `run_daily_selection`
   生成种子池、候选股和待选观察池 `watchlist`
7. `run_paper_trading`
   对观察池执行买入信号、纸面下单和持仓更新
8. `run_position_monitor`
   对已有持仓做卖出巡检和纸面平仓

程序真正自动运行起来，需要至少两个常驻进程：

- `API Gateway`
- `Scheduler`

如果只有 API，没有 Scheduler：

- 前端能打开
- 但市场、题材、选股、交易不会每天自动更新

如果 API 和 Scheduler 都常驻：

- 市场层会每日更新
- 热门题材会先有基础快照，再按天增量更新
- 股票筛选会每日更新
- 纸面交易会每日自动执行

## 9. 持续运行

推荐直接看运行手册：

- `docs/runbook.md`

仓库里已经提供：

- `scripts/start_api_gateway.sh`
- `scripts/start_scheduler.sh`
- `deploy/systemd/quant-platform-api.service`
- `deploy/systemd/quant-platform-scheduler.service`

## 9. GitHub 后首次拉下来的最小启动方式

如果别人从 GitHub 第一次拉下这个项目，建议按这套最小步骤启动：

1. 安装 Python 依赖
2. 安装前端依赖
3. 从根目录 `.env.example` 复制一份本地环境变量
4. 启动 API
5. 启动 Scheduler
6. 打开前端页面

示例：

```bash
cd /path/to/new-auto-trading

python -m pip install -e .
cd apps/frontend && npm install && cd ../..

cp .env.example .env
mkdir -p data

set -a
source .env
set +a
```

启动 API：

```bash
./scripts/start_api_gateway.sh
```

启动 Scheduler：

```bash
./scripts/start_scheduler.sh
```

启动前端：

```bash
cd apps/frontend
npm run dev -- --host 0.0.0.0
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:18080`

首次启动后，Scheduler 会先执行一轮初始化全流程，之后再按调度自动更新。
