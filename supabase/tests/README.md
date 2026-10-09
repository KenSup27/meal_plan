# 数据库测试

已有 schema/seed 契约检查使用 pytest。新增 Auth 测试会实际执行 PostgreSQL，
需要显式指定 `MEAL_PLAN_TEST_DB_URL`；没有配置时显示 skip，不能算全库验收通过。
无需新增 Python 数据库驱动，仅使用 `psql` 和现有 pytest。

## 建立独立的本地测试库

```bash
createdb meal_plan_auth_test
psql -X -v ON_ERROR_STOP=1 -d meal_plan_auth_test -f supabase/tests/bootstrap_local.sql
psql -X -v ON_ERROR_STOP=1 -d meal_plan_auth_test -f supabase/schema.sql -f supabase/seed.sql
```

`bootstrap_local.sql` 只允许数据库名 `meal_plan_auth_test`，禁止用于 Supabase 项目。
本地 Auth 表是数据库契约桩，不是可验证密码、发送 OTP 或签发 JWT 的 Auth 服务。

## 按模块验收

```bash
pytest -q supabase/tests/test_auth_policy.py
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests/test_auth_database.py::test_email_and_phone_registration_lifecycle
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests/test_auth_database.py::test_anonymous_owner_and_cross_user_permissions
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests/test_auth_database.py::test_registered_user_database_workflow
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests/test_auth_database.py::test_recipe_deletion_and_ingredient_reassignment
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests/test_auth_database.py::test_plan_week_changes_preserve_existing_items
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest -q supabase/tests
```

每个行为测试独立事务并最终回滚。生命周期测试保留“无邮箱的 Auth 账号”兼容性回归，
但本版本 `phone.enabled = false`，它不代表上线手机号 OTP。
以上 SQL 行为测试只使用测试 UUID / example.invalid 邮箱。
跨用户测试在切换 JWT subject 前完成延迟约束检查，模拟每个 HTTP 请求独立事务。

新增边界回归覆盖菜谱删除、同事务创建后删除、账号级联删除、移动食材两端非空、
删除最后一个食材失败、同事务整体替换食材，以及父计划改周不能让已有餐项越界。
初始化脚本适用于独立空测试库；重跑 schema 不等同于升级旧版表结构。

## 云端运行同一组行为测试

在显式指定的测试项目中，把每个测试文件放入以下顺序的**单次 SQL 调用**：

```text
BEGIN;
supabase/tests/sql/helpers.sql
supabase/tests/sql/<测试文件>.sql
SET CONSTRAINTS ALL IMMEDIATE;
ROLLBACK;
```

`auth_lifecycle.sql` 中的 `/* APPLY_AUTH_MODULE */` 应替换为 `supabase/auth.sql`
去除外层 BEGIN/COMMIT 后的内容；pytest 已自动处理。
Cloud Auth 使用真实 `auth.users` 表，不运行 bootstrap。
SQL 测试不证明真实密码验证、JWT 签名或会话生命周期通过。
当前 MVP 使用邮箱＋密码、不要求邮箱验证；云端开关和真实 Auth 端到端验收清单见
[ADR 0004](../../docs/adr/0004-email-password-mvp.md)。
保留的 OTP 模板测试只检查后续迭代资产，不代表 MVP 启用验证码或需要配置 SMTP。

## 真实云端邮箱密码冒烟（显式启用）

```bash
MEAL_PLAN_HOSTED_TEST_PROJECT=ziusvgtrmarbkmrvnpyq \
  node --env-file=.env.supabase.local supabase/tests/hosted/password-smoke.mjs
```

需要 Node 22、项目 URL 和 publishable key；不需要 SMTP、密码预置或 service_role。
此脚本不属于默认 pytest：它会向指定云端项目创建两个临时账号和测试计划。
脚本先检查邮箱自动确认、手机号关闭、匿名关闭及允许注册；不满足即停止，不发送邮件。
随机邮箱使用 `meal-plan-smoke-<run UUID>-a/b@example.com`，不要换成真实用户地址。
Auth 模块通过才继续 Data API 模块；任意失败立即停止后续验收并尝试全局登出。
密码/令牌不输出；最后 `CLEANUP` 行只输出 run UUID、用户 UUID、测试邮箱及登出结果。

**清理是必需的单独步骤，不会自动回滚 HTTP 写入。** 无论成功或失败，使用管理工具
先核对 `CLEANUP` 对应的 UUID、精确测试邮箱、`raw_user_meta_data.meal_plan_test_run`，
并确认 `auth.sessions` 中这些账号已无会话；再仅删除这些测试账号，级联清理其业务数据。
不按邮箱前缀批量删除。若网络中断导致未得到用户 UUID，通过本轮精确邮箱＋run UUID
定位并核实，不要直接重新运行留下旧账号。最后检查用户与业务数据计数回到运行前状态。

2026-10-09 数据库开发阶段的云端记录：13 项通过，两个账号已登出并清理；
当时本地 34 项回归全部通过。新增两项边界回归后，本地应完整运行 36 项；
未设置数据库连接时是 31 项通过、5 项跳过，不代表完整验收。
提交前审查不自动重跑会创建云端账号的冒烟，也不自动部署本次 SQL 修复。
覆盖范围为 Supabase Auth、Profile、食材只读、周计划/人工餐和相关视图隔离，
不代表前端、FastAPI、菜谱原子写入或完整采购 HTTP 流程已经验收。
