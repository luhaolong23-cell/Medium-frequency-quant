# 持续运行 Runbook

## 1. 推荐运行模式

当前推荐用这组配置常驻：

- `QUANT_STORAGE_BACKEND=sqlite`
- `QUANT_SQLITE_PATH=data/quant-platform.sqlite3`
- `QUANT_MARKET_DATA_PROVIDER=yfinance`

这套模式的定位是：

- 市场层日更
- 选股层日更
- 持仓巡检按调度时点运行
- 交易执行仍然是 `paper trading`

## 2. 从 0 开始部署后的启动顺序

如果这套程序刚部署到一台新机器，推荐按下面顺序启动：

1. 安装依赖并确认 Python 环境可用
2. 在项目根目录准备 SQLite 存储目录 `data/`
3. 先启动 API 网关
4. 手动执行一轮 `run_daily`，生成首批市场、题材、选股和交易快照
5. 再启动 scheduler 常驻，让之后的流程按天自动运行

原因是：

- API 负责给前端和手动命令提供统一接口
- 首次 `run_daily` 用来生成基础快照，避免页面初始为空
- Scheduler 负责后续每日自动更新，不需要每天手工执行

首次部署后，这套程序的实际运行链路是：

- 市场主数据同步
- 市场行情更新
- 牛市判断
- 股票池 inventory 更新
- 热门题材生成并落库
- 股票筛选与观察池更新
- 纸面买入信号和纸面订单生成
- 持仓巡检与纸面卖出

## 3. 本地手动启动

先启动 API：

```bash
./scripts/start_api_gateway.sh
```

再启动 scheduler：

```bash
./scripts/start_scheduler.sh
```

默认行为：

- API 监听 `0.0.0.0:18080`
- SQLite 文件写到 `data/quant-platform.sqlite3`
- provider 默认是 `yfinance`

## 4. 手动检查程序是否正常

健康检查：

```bash
curl http://127.0.0.1:18080/health
```

看最近流程结果：

```bash
curl http://127.0.0.1:18080/workflow/logs/latest-summary
```

看当前跟踪牛市：

```bash
curl http://127.0.0.1:18080/markets/bull/today
```

看当前持仓：

```bash
curl http://127.0.0.1:18080/positions
```

## 5. 调度器会做什么

调度器按 `configs/app.yaml` 执行：

- `sync_refdata` 日更
- `ingest_market_bars` 日更
- `run_regime` 日更
- `run_daily_selection` 日更
- `run_position_monitor` 日更

其中：

- `run_daily_selection` 会继续生成买入信号和纸面买单
- `run_position_monitor` 会检查已有 `OPEN` 持仓，并在满足卖出条件时生成 `SELL` 订单并平仓

## 6. 当前卖出规则

当前已实现两条卖出规则：

- `SELL_TRAILING_DRAWDOWN`
  最高点回撤达到 `30%`
- `SELL_SHRINK_DOWN`
  连续 `3` 天缩量下跌

对应配置在：

- `configs/trading_rules.yaml`

## 7. systemd 常驻

仓库里已经提供模板：

- `deploy/systemd/quant-platform-api.service`
- `deploy/systemd/quant-platform-scheduler.service`

安装方式：

```bash
sudo cp deploy/systemd/quant-platform-api.service /etc/systemd/system/
sudo cp deploy/systemd/quant-platform-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quant-platform-api
sudo systemctl enable --now quant-platform-scheduler
```

查看日志：

```bash
sudo journalctl -u quant-platform-api -f
sudo journalctl -u quant-platform-scheduler -f
```

## 8. 当前边界

现在可以持续运行的是：

- 数据更新
- 牛市跟踪
- 优质股日排名
- 观察池更新
- 买入信号
- 纸面买入
- 持仓巡检
- 纸面卖出和平仓

现在还没实现的是：

- 真实券商下单
- 券商订单回报对账
- 资金账户同步
- 更完整的风险约束
- 盘中实时逐笔监控
