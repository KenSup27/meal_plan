# Meal Prep & Nutrition Planner

面向需要健身、控制体型并有带饭习惯的上班族的周度营养规划工具。

## 当前状态

已实现移动端静态页面、FastAPI 营养计算及 Profile / 食材 / 菜谱 / 周计划 / 采购清单 API，
以及 Supabase 六张业务表、五个派生视图、RLS、注册后自动创建 Profile 和 34 种基础食材 Seed。
数据库当前认证决策为邮箱＋密码、不要求邮箱验证，暂缓邮箱和短信验证码，见 [ADR 0004](docs/adr/0004-email-password-mvp.md)。

**目前还不是完整的持久化端到端版本：**

* FastAPI 业务 API 仍使用内存仓储；重启会丢失这部分数据，配置 Supabase 环境变量不会自动启用数据库仓储。
* 前端菜谱、计划等仍使用浏览器本地存储；当前登录界面仍走邮箱 / 手机验证码，尚未对齐邮箱＋密码流程。
* 前端登录配置通过 `window.MEAL_PREP_SUPABASE` 注入，不会自动读取后端 `.env`。
* 数据库食材使用 bigint ID，API / 前端现有食材标识和种子目录仍需统一；不可直接按列表位置映射。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

打开 <http://127.0.0.1:8000/>，API 文档见 <http://127.0.0.1:8000/docs>。
未配置 Supabase 时，认证接口不能完成真实登录，页面业务流程也不代表云端数据已保存。

如需测试后端真实 Auth 接口，从 `.env.example` 创建本地 `.env`，
填写 `SUPABASE_URL` 和 `SUPABASE_PUBLISHABLE_KEY`（兼容 `SUPABASE_ANON_KEY`），然后启动：

```bash
uvicorn backend.app.main:app --reload --env-file .env
```

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
```

完整数据库验收还需 PostgreSQL 15+、`psql` 和独立测试库。
按 [数据库测试说明](supabase/tests/README.md) 初始化后运行：

```bash
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests
```

真实 SQL 测试使用事务回滚，包括注册生命周期、匿名 / 跨用户权限、营养及采购聚合、
菜谱删除与食材调整、计划周修改边界。不要把 skip 算作数据库全量通过。
云端密码冒烟会创建测试账号，需显式启用并单独清理；不会在默认测试中执行。

## Supabase 初始化

对于**新建的空项目**，在 SQL Editor 中依次执行：

1. `supabase/schema.sql`
2. `supabase/seed.sql`

Schema 依赖 Supabase Auth 的 `auth.users`，新账号自动创建 `profiles`，
并回填已有账号缺失的 Profile，不覆盖已有营养基线。
匿名角色无业务表 / 视图权限；登录用户只能访问自己的数据，基础食材对登录用户只读。
停用食材仍可读以保证历史营养计算，食材选择器应过滤 `is_active = true`。

`schema.sql` 是初始化定义，**不是旧版数据库的通用升级迁移**：
`CREATE TABLE IF NOT EXISTS` 不会修改已有列或约束。已有旧表时，先核对差异、
备份并编写显式迁移，不要直接覆盖或删表重建。
`supabase/auth.sql` 仅更新 Auth/Profile 触发器、回填和权限，不负责升级全部业务表。

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

## 合并后的联调顺序

1. 对齐前端邮箱＋密码注册、登录、登出与后端认证接口。
2. 实现按登录用户隔离的 Supabase 仓储，统一食材 ID / 目录和字段契约。
3. 菜谱及食材明细必须原子写入同一事务，避免延迟约束阻止分两次 HTTP 提交。
4. 在测试项目应用经核对的迁移并验证 RLS；将前端业务存储接到后端。
5. 在同步最新 `main` 的主项目中进行注册 → 营养基线 → 菜谱 → 周计划 → 采购清单 → 刷新 / 重登后的持久化端到端测试。
