# AGENT.md

## 项目目标

这是一个面向上班族的带饭与营养规划 MVP。核心闭环是：录入营养基线 → 创建菜谱 → 规划一周带饭 → 生成生重采购清单。

## 当前架构

* `backend/`：FastAPI 认证与业务 API；按请求绑定用户 JWT 的 Supabase 仓储，内存仓储仅用于显式测试替换。
* `frontend/`：无构建依赖的移动端页面，由 FastAPI 托管；已保存业务数据以服务端为准。
* `supabase/`：六张业务表及 RLS、事务 RPC、精度视图、初始化/升级 SQL 和真实 PostgreSQL 回归。
* `data/`：本地运行数据目录，禁止提交真实用户数据。

## 开发规则

* 修改 API 后必须补充或更新 `backend/tests/` 中的测试。
* 不要把 `.env`、密钥、本地运行数据或用户数据提交到 Git。
* 不要把前端传来的营养汇总值作为权威数据；服务端应根据明细重新计算。
* 保持移动端优先，优先保证 375px 宽度下的可用性。
* 数据库业务模型见 ADR 0002；涉及持久化设计的改动先记录到 `docs/adr/`，不要擅自扩展业务表或放宽 RLS。

## 常用命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --env-file .env
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q backend/tests supabase/tests
node --test frontend/tests/*.test.js
```

打开 <http://127.0.0.1:8000/> 查看应用；环境配置及真实浏览器验收见 README。
