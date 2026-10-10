# Meal Prep & Nutrition Planner

面向需要健身、控制体型并有带饭习惯的上班族的周度营养规划工具。

## 当前状态

已实现移动端静态页面、FastAPI 营养计算及 Profile / 食材 / 菜谱 / 周计划 / 采购清单 API，
以及 Supabase 六张业务表、七个派生视图、两个事务 RPC、RLS、注册后自动创建 Profile 和 34 种基础食材 Seed。
数据库当前认证决策为邮箱＋密码、不要求邮箱验证，暂缓邮箱和短信验证码，见 [ADR 0004](docs/adr/0004-email-password-mvp.md)。

前端使用邮箱＋密码登录，基线、菜谱、周计划通过 FastAPI 保存至 Supabase。
后端按请求绑定用户 JWT，让数据库 RLS 执行隔离；内存仓储仅用于显式测试依赖替换。
页面停止读写旧全局业务缓存，退出或切换账号立即清空页面状态并取消旧请求。
营养从原始明细汇总后统一舍入，盘数按菜谱餐项的 quantity 求和。
设计及迁移边界见 [ADR 0005](docs/adr/0005-business-persistence-and-isolation.md)。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

打开 <http://127.0.0.1:8000/>，API 文档见 <http://127.0.0.1:8000/docs>。
未配置 Supabase 时，认证与业务接口返回服务未配置错误；不会回退到内存保存。

正常使用前，从 `.env.example` 创建本地 `.env`，
填写 `SUPABASE_URL` 和 `SUPABASE_PUBLISHABLE_KEY`（兼容 `SUPABASE_ANON_KEY`），然后启动：

```bash
uvicorn backend.app.main:app --reload --env-file .env
```

`SUPABASE_PROJECT_URL` 是 URL 的兼容别名。FastAPI 的 `/runtime-config.js` 自动向前端提供
公开 URL/key，页面在初始化认证前加载；不需要手工修改 HTML 或注入临时预览脚本。
`/api/v1/health` 仅检查进程；需要登录的 `/api/v1/ready` 会实际读取数据库食材目录。

不要提交 `.env`、数据库连接密码、service_role / secret key、访问令牌或真实用户数据。
浏览器只能使用 publishable / anon key，不能注入服务端管理密钥。

## 测试

```bash
# 默认仅运行后端测试
pytest -q
# 前端纯逻辑测试；不是浏览器端到端测试
node --test frontend/tests/*.test.js
# 数据库契约测试；未指定数据库时，真实 SQL 行为测试会跳过
pytest -q supabase/tests
# 完整后端与 SQL 回归（独立测试库）
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q backend/tests supabase/tests
```

完整数据库验收还需 PostgreSQL 15+、`psql` 和独立测试库。
按 [数据库测试说明](supabase/tests/README.md) 初始化后运行：

```bash
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests
```

真实 SQL 测试使用事务回滚，包括注册生命周期、匿名 / 跨用户权限、营养及采购聚合、
菜谱删除与食材调整、计划周修改边界。不要把 skip 算作数据库全量通过。
云端密码冒烟会创建测试账号，需显式启用并单独清理；不会在默认测试中执行。
完整浏览器流程及重启恢复测试见 [端到端测试说明](tests/e2e/README.md)。

## Supabase 初始化

对于**新建的空项目**，在 SQL Editor 中依次执行：

1. `supabase/schema.sql`
2. `supabase/seed.sql`
3. `supabase/business.sql`

`schema.sql` 已包含完整性规则。已有项目若尚未同步菜谱删除/食材转移/计划改周修复，
再执行 `supabase/integrity.sql`（对应升级版本 `20261010000335`）。

Schema 依赖 Supabase Auth 的 `auth.users`，新账号自动创建 `profiles`，
并回填已有账号缺失的 Profile，不覆盖已有营养基线。
匿名角色无业务表 / 视图权限；登录用户只能访问自己的数据，基础食材对登录用户只读。
停用食材仍可读以保证历史营养计算，食材选择器应过滤 `is_active = true`。

`schema.sql` 是初始化定义，**不是旧版数据库的通用升级迁移**：
`CREATE TABLE IF NOT EXISTS` 不会修改已有列或约束。已有旧表时，先核对差异、
备份并编写显式迁移，不要直接覆盖或删表重建。
`supabase/auth.sql` 仅更新 Auth/Profile 触发器、回填和权限，不负责升级全部业务表。
已采用当前 Schema 的项目，业务接通升级仅执行
`supabase/migrations/20261009150703_business_persistence_and_precision.sql`；其内容与 `business.sql` 相同，
新增事务 RPC、保留中间精度的 RLS 视图并更新汇总视图，不扩展业务表或放宽 RLS。
该版本号由已授权的 Supabase 远程迁移生成；部署记录见验收报告。

SQL 不会配置 Auth 服务开关。`supabase/auth-policy.json` 是目标配置记录，
需按 [ADR 0004](docs/adr/0004-email-password-mvp.md) 在测试项目单独配置并验证。
本地测试的 Auth 桩不具备发送邮件、校验密码或签发 JWT 的能力。

## 文档入口

* [开发计划（当前认证范围以开头说明和 ADR 0004 为准）](PLAN.md)
* [原始产品需求文档](meal_prep_nutrition_planner_prd.md)
* [技术设计与 API 契约](docs/technical-design.md)
* [数据库模型定稿](docs/adr/0002-database-design-open-questions.md)
* [当前邮箱密码认证决策](docs/adr/0004-email-password-mvp.md)
* [数据库 Schema 与 RLS](supabase/schema.sql)
* [基础食材 Seed](supabase/seed.sql)
* [数据库测试与云端冒烟说明](supabase/tests/README.md)

* [本次修复及端到端验收](docs/reviews/2026-10-10-unified-fixes-e2e.md)
