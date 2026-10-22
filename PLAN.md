# xfinance 实施计划

## 定位

个人股票查看器。核心交互只有一条主线：打开一个标的，把它换算成任意一种硬通货，再和它自己、和其他标的比较。

- 行情总览 -> 点击卡片 -> K 线 -> 切换计价 / 复权 / 周期 -> 打开指标。
- 自定义指数把两个标的写成一条表达式，直接看比值。
- 工具箱回答三个问题：定投赚了多少、几个标的是否同涨同跌、复利多久翻倍。

前端 Vue 3 + lightweight-charts。后端 FastAPI，uv 管理，SQLite 本地缓存。默认 10 秒轮询刷新总览。

## 数据形状（先定形状，后写逻辑）

```python
Bar(date, open, high, low, close, volume, amount)        # 所有序列统一为 OHLCV
SeriesMeta(symbol, name, kind, market, currency, unit,
           chart="candlestick"|"line", quotable=bool)
Snapshot(symbol, last, prev_close, change_pct, open, high, low,
         volume, amount, ts, bids[5], asks[5], source)
Numeraire(id, label, group, unit, kind="unit"|"fiat"|"asset",
          series, currency)                              # 1 单位计价物值多少美元
ChartPayload(meta, bars, volume, indicators, quote, window, source)
```

计价是一个纯函数，不散落在路由里：

```
asset_usd   = price_in_asset_currency * fx(asset_currency -> USD)
quoted      = asset_usd / numeraire_value_usd
normalized  = quoted / quoted[window_start]        # 起点=1
```

`numeraire_value_usd` 只由注册表决定：

| 计价物 | 值（美元） |
| --- | --- |
| USD | 1 |
| CNY / JPY / EUR | 1 / USDXXX |
| 黄金（美元/盎司） | XAUUSD |
| 白银（美元/盎司） | XAGUSD |
| WTI / 布伦特（美元/桶） | WTIUSD / BRENTUSD |
| 上金所金（人民币/克） | AU9999 / USDCNY |

指标、表达式、统计、降采样都是无框架依赖的纯函数。外部数据源只在 `infrastructure/external/` 里出现。

## 模块

```
app/
  app.py                 create_app：装配、静态资源、异常处理
  __main__.py            CLI + 内嵌 uvicorn
  config.py              pydantic-settings
  api/                   HTTP 边界：路由、依赖、错误映射
  services/              用例编排：总览、图表、表达式、工具、行情同步
  domain/                纯函数：计价、指标、DSL、统计、降采样、目录
  repositories/          SQLAlchemy 仓储 + 迁移
  infrastructure/
    external/            TDX / Frankfurter / Sina / SGE / Treasury / Demo
    cache.py             进程内 TTL 缓存
```

分层约束：`api -> services -> domain <- repositories`。`domain` 不 import FastAPI、SQLAlchemy、httpx。

## 数据源与降级

| 数据 | 主源 | 备用 |
| --- | --- | --- |
| A 股 / ETF / 指数 K 线 | eltdx（通达信 7709，服务端前/后复权） | 演示序列 |
| 证券名称检索 | eltdx 代码表（12 小时缓存） | 内置目录 |
| 汇率日线 | Frankfurter（ECB） | 演示序列 |
| 黄金 / 白银 / WTI / 布伦特日线 | 新浪外盘期货历史 | 演示序列 |
| 商品实时快照 | 新浪 `hf_*` | 日线最后两根 |
| 上金所 Au99.99 日线 | 上金所官方 | 新浪 SGE 快照 / 演示 |
| 美债收益率 | 美国财政部 CSV | 演示序列 |

`XFINANCE_DATA_MODE=auto|live|demo`。`auto` 先真实源，按板块失败回退到演示序列，并在响应 `meta.source` 和界面标签上明确标注，绝不静默伪装成实时。

## API 契约

```
GET  /api/health
GET  /api/meta/numeraires
GET  /api/meta/status
GET  /api/overview
GET  /api/search?q=
GET  /api/instruments/{symbol}
GET  /api/instruments/{symbol}/snapshot
GET  /api/instruments/{symbol}/chart?timeframe=1d|1w|1m&adjust=qfq|hfq|none
     &numeraire=CNY&normalize=true&range=1y&indicators=ma:20,ma:60,boll:20,macd,rsi:14,kdj,vol
GET  /api/watchlist           POST/DELETE /api/watchlist/{symbol}
GET  /api/custom-indices      POST /api/custom-indices
GET  /api/custom-indices/{id} DELETE /api/custom-indices/{id}
POST /api/custom-indices/validate
GET  /api/custom-indices/{id}/chart?range=1y&window=60
GET  /api/tools/dca?symbol=&start=&amount=&day=&fee=&numeraire=
GET  /api/tools/correlation?symbols=a,b,c&window=120&numeraire=
POST /api/tools/compound
```

统一响应：`{"data": ..., "meta": {"source": ..., "cached": ..., "generated_at": ...}}`。错误：`{"error": {"code", "message"}}`。

## 持久化

| 表 | 键 | 用途 |
| --- | --- | --- |
| `securities` | `symbol` | TDX 代码表缓存，搜索 |
| `bars` | `(symbol, timeframe, adjust, date)` | 日/周/月 K 线，含复权三态 |
| `watchlist` | `symbol` | 自选股 |
| `custom_indices` | `id`, `name` unique | 表达式 |
| `sync_state` | `key` | 每类序列最后同步时间 |

SQLite WAL + busy_timeout。迁移由 Alembic 管理，启动时 upgrade head。

## 性能措施

- K 线 / 汇率 / 商品批量 upsert，单事务。
- 快照 TTL 5 秒（股票）/ 10 秒（商品），单飞锁避免并发打爆上游。
- 计价换算序列 5 分钟缓存。
- 图表按时间桶聚合到约 320 点，指标先算后降采样。
- TDX 代码表 12 小时落库；按需同步，不预抓全市场。
- 自定义指数校验前端 300ms 防抖，后端限制递归深度与引用环。

## 实施阶段与验收

1. **脚手架**：pyproject、设置、表结构、迁移。`uv sync` 成功，迁移在空库可重放。
2. **领域层**：计价、指标、DSL、统计、降采样。离线 pytest 全绿。
3. **数据源**：五个适配器 + 演示源。真实源 curl 探针可通，失败可降级。
4. **服务与 API**：总览、图表、自选、指数、工具。`TestClient` 覆盖主路径，`uvicorn` 后可 curl。
5. **前端**：总览、标的详情、工具箱、指数弹窗。构建产物可被 FastAPI 托管；浏览器实检截图。
6. **打包与开发流**：Vite 插件代理 `/api`、`scripts/devserver.py` 一条命令双启、Hatch 构建钩子、wheel 安装可运行。

## 关键取舍

- **统一 bars 表**而不是每类数据一张表：图表、计价、统计都只需要 `(symbol, date, ohlc)`，复权维度和周期维度放进主键。
- **服务端算指标**：前端只渲染，指标预热期不会被截断；降采样发生在指标之后。
- **不做 WebSocket**：10 秒轮询足够个人查看器，断线恢复简单，服务端无连接状态。
- **真实数据优先、演示数据兜底**：保证首次启动和离线测试都能用，但界面必须显示数据来源。

## 实施结果

六个阶段全部落地，验收方式如下。

| 阶段 | 证据 |
| --- | --- |
| 脚手架 | `uv sync` 通过；空库 `alembic upgrade head` 建出 6 张表；SQLite 以 WAL 打开 |
| 领域层 | 计价、指标、表达式、统计、降采样共 47 个纯函数用例通过 |
| 数据源 | 通达信、ECB、新浪、上金所、美国财政部均做过真实请求探针；演示源覆盖全部序列 |
| 服务与 API | 总览、图表、自选、指数、工具在演示与真实两种模式下 curl 通过；离线 API 测试覆盖生命周期与错误路径 |
| 前端 | 总览、标的、自定义指数、工具箱四个页面可在 Chrome 中操作；桌面与 390px 移动端截图核验，无横向溢出 |
| 打包 | `uv build` 产出的 wheel 含 `frontend-build` 与迁移；装进全新虚拟环境后 `xfinance-app` 可启动并托管 SPA |

测试总数 79，全部离线。

### 实际取舍

- **演示数据带共享市场因子**：股票、ETF、指数共用一个权益因子，商品共用一个商品因子。这样演示模式下的相关性矩阵和总览走势不会是一堆互不相关的随机线。
- **复权数据按周期与复权方式分别缓存**：直接使用通达信服务端的前复权 / 后复权，不在本地重算仿射系数，避免与上游约 0.01 元的偏差。
- **计价失败回退原生价格而不是报错**：响应里带 `quote_error` 和 `quoted=false`，界面显示警告。这样单一汇率源故障不会让整个图表不可用。
- **服务端算指标并先算后降采样**：指标预热期不会被区间截断。
- **没有做 WebSocket**：10 秒轮询足够，断线恢复简单，服务端无连接状态。

### 仍未做

- 港股、美股、期货合约连续主力切换。
- 中国法定节假日日历。
- 自定义指数的区间收益、波动率等派生指标。
- 多用户、鉴权、远程部署加固。

这些都不影响个人单机查看这条主路径。
