# AGENT.md

## 项目目标

这是一个面向上班族的带饭与营养规划 MVP。核心闭环是：录入营养基线 → 创建菜谱 → 规划一周带饭 → 生成生重采购清单。

## 当前架构

* `backend/`：FastAPI 单体后端，当前只放健康检查和营养计算骨架。
* `frontend/`：无构建依赖的移动端静态页面骨架，由 FastAPI 在生产模式下托管。
* `supabase/`：后续迁移使用的数据库草案，表结构仍需产品讨论确认。
* `data/`：本地运行数据目录，禁止提交真实用户数据。

## 开发规则

* 修改 API 后必须补充或更新 `backend/tests/` 中的测试。
* 不要把 `.env`、密钥、本地运行数据或用户数据提交到 Git。
* 不要把前端传来的营养汇总值作为权威数据；服务端应根据明细重新计算。
* 保持移动端优先，优先保证 375px 宽度下的可用性。
* 数据库表结构尚未最终定稿；涉及持久化设计的改动先记录到 `docs/adr/`，不要擅自扩展业务表。

## 常用命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
pytest -q
```

打开 <http://127.0.0.1:8000/> 查看应用骨架。
