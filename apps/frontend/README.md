# Quant Platform Frontend

这个目录是量化交易系统的 Vue 3 前端。

当前实现的是一个单页 Dashboard，围绕后端已有流程展开：

- 市场状态总览
- 牛市筛选过程
- 题材热度与种子池
- 候选排名
- 观察池
- 信号与订单
- 开放持仓
- 手动触发 `run-daily`

## 1. 环境要求

- Node.js 24+
- npm 10+

本机当前验证通过的命令来自：

- `node`
- `npm`

## 2. 安装依赖

在当前目录执行：

```bash
npm install
```

## 3. 启动开发环境

先启动后端网关：

```bash
cd /home/luuuu/miniconda3/envs/new-auto-trading
./scripts/start_api_gateway.sh
```

默认后端地址：

- `http://127.0.0.1:18080`

再启动前端开发服务器：

```bash
cd /home/luuuu/miniconda3/envs/new-auto-trading/apps/frontend
npm run dev -- --host 0.0.0.0
```

默认前端地址：

- `http://127.0.0.1:5173`

## 4. API 联调方式

开发环境默认不直接跨域请求 `18080`，而是走同源代理：

- 前端请求：`/api/...`
- Vite 代理转发到：`http://127.0.0.1:18080/...`

对应配置：

- `.env.example`
- `vite.config.js`
- `src/lib/api.js`

如果你要改后端地址，优先改：

```env
VITE_API_BASE_URL=/api
```

如果不是本地联调，而是独立部署前后端，需要额外处理以下其中一种：

- 反向代理 `/api` 到后端服务
- 后端开启 CORS，并把 `VITE_API_BASE_URL` 指向真实 API 地址

## 5. 可用命令

开发：

```bash
npm run dev
```

生产构建：

```bash
npm run build
```

本地预览构建产物：

```bash
npm run preview
```

## 6. 构建产物

执行 `npm run build` 后，产物输出到：

- `dist/`

当前已验证可生成：

- `dist/index.html`
- `dist/assets/*.css`
- `dist/assets/*.js`

## 7. 目录结构

```text
apps/frontend
├── index.html
├── package.json
├── src
│   ├── App.vue
│   ├── lib
│   │   ├── api.js
│   │   └── format.js
│   └── modules
│       ├── markets
│       ├── selection
│       ├── system
│       └── trading
└── vite.config.js
```

目录按领域拆分，不横向堆组件：

- `markets`：市场状态、牛市判定过程
- `selection`：题材、种子池、候选排名
- `trading`：观察池、信号、订单、持仓
- `system`：页头摘要、手动触发面板

## 8. 当前已验证内容

已经实际验证过：

- `npm install`
- `npm run build`
- `http://127.0.0.1:5173/api/health`
- `http://127.0.0.1:5173/api/workflow/logs/latest-summary`

说明当前前端至少满足：

- 能安装依赖
- 能生产构建
- 能通过开发代理访问后端接口
