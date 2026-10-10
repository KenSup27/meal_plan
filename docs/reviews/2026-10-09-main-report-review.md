# 测试报告复核：当前 main

日期：2026-10-09（Asia/Shanghai）

## 复核对象与结论

原报告：`/Users/kenyu/.codex/visualizations/2026/10/09/01a11f64-c5fa-7ec0-8189-1ad049678441/main-981bcb3-test-report.md`。

主项目：`/Users/kenyu/Documents/Codex/meal_prep_project`，当前 `main` 为
`c922dedccc6f4cb9c03e1585e45c8929a88209fd`，工作目录干净。
本聊天工作树最初也在此提交，已新建并切换到 `codex/unified-report-fixes`。

`git diff 981bcb3..main --stat` 只有 README 一行变化；报告涉及的功能代码均未变化。
本次逐项阅读代码并运行本地探针，确认报告中的五项问题仍然存在。
本次交付为复核与统一修复方案，尚未实施功能修复；没有改动主项目工作目录、main、云端配置或云端数据。

## 逐项核对

| 报告问题 | 当前证据 | 复核结论与责任 |
| --- | --- | --- |
| P1：跨账号数据串用 | `frontend/app.js:5,27,34-35` 使用固定 localStorage key，在登录状态确定前恢复全部业务状态；`frontend/auth.js` 的登录/退出仅控制应用显隐，没有通知业务层重置。合成 A → 退出 → B 会话事件后，B 会话下仍渲染 A 的私有菜谱。 | 仍存在；前端主责。本次未认定云端 RLS 越权。 |
| P1：业务不落库 | `frontend/app.js:71,78-81` 的目标、菜谱、餐项保存只修改本地状态；`backend/app/repositories/memory.py:145-149` 始终返回进程内单例。`routes.py` 直接调用该仓储，设置 Supabase Auth 参数不会切换业务仓储。 | 仍存在；前后端共同主责。本次没有重新查询云端业务计数。 |
| P2：加入计划选错菜谱 | `frontend/app.js:67` 的 `add-to-plan` 忽略按钮上的 `id`，把 `pendingMeal` 设为 null；`:58` 仅按已有餐项的 `recipe_id` 选中。合成点击三文鱼按钮时无选项显式选中，第一选项仍为 A 的测试菜谱。 | 仍存在；前端主责。 |
| 后端认证响应丢失 session | `backend/app/services/auth.py:112-126` 仅解析嵌套 `session`。运行报告自带的原始 REST 响应探针，注册、登录、刷新均 `session_received=false`，退出码 1。 | 仍存在；后端主责。前端 SDK 登录成功不能覆盖此契约缺陷。 |
| P2：盘数与营养精度 | `frontend/app.js:59,61` 把 `plan.items.length` 显示为盘数；`app-core.js:90-108,167-200` 先舍入单盘再乘数量。合成午餐 2 盘、晚餐 1 盘显示 2 盘；前后端同明细汇总见下表。 | 仍存在；盘数由前端修复，精度需三层统一。 |

合成 DOM 探针在 Node VM 中执行当前 `auth.js`、`app.js` 和 `app-core.js`，使用虚拟 DOM、虚拟 localStorage、合成会话及 mock fetch，没有调用真实认证或写入数据库。它验证事件处理和生成 HTML，不替代真实浏览器布局及网络 E2E。

样例：鸡胸肉 150g、西兰花 200g、橄榄油 5g，每盘按当前目录营养值计算，安排 2 + 1 盘。

| 当前实现 | kcal | 蛋白质 g | 碳水 g | 脂肪 g |
| --- | ---: | ---: | ---: | ---: |
| 前端 `aggregatePlanNutrition` | 935.1 | 121.8 | 25.8 | 38.7 |
| 后端 `summarize_nutrition` | 935.1 | 121.7 | 25.8 | 38.6 |

原始单盘蛋白质为 40.55g、脂肪为 12.85g。先舍入为 40.6/12.9 再乘 3，造成差异。

## 影响统一方案的补充发现

1. **数据库视图也有中间舍入。** `supabase/schema.sql:133-181` 的 `recipe_nutrition` 将单盘结果转换为一位小数，餐项视图再乘数量；日/周视图继续累计餐项值。此为当前 SQL 的静态计算路径证据，尚未针对此样例运行数据库数值对照。它不足以说明表字段精度有缺陷，但说明精度修复不能只改前端。
2. **替换仓储工厂还不够。** `backend/app/services/meal_plans.py:124,142` 依赖原地修改内存对象，没有显式持久化餐项的仓储方法。
3. **食材与状态结构不一致。** 前端使用 `chicken` 等字符串标识和中文分类，数据库使用 bigint ID 和稳定分类代码；计划目标、人工餐响应也需要显式映射。不能按食材列表位置转换 ID。
4. **计划目标会被前端读取动作覆盖。** `frontend/app.js:36` 每次获取计划都以当前基线替换目标，和 ADR 0002 的创建时快照规则冲突。
5. **跨月周的添加餐项有边界错误。** `meal_plans.py:122` 使用 `week_start.replace(day=week_start.day + 6)`，例如 2026-09-28 会产生无效日期。纳入周计划接口接通时的边界修复。
6. **默认认证降级不宜带入持久化模式。** `backend/app/core/auth.py:63-64` 在缺少 Auth 配置时把任意 Bearer 值当用户 ID。持久化模式必须拒绝缺配置，不得沿用此模拟身份逻辑。
7. **说明文件过时。** README 当前声称前端仍走邮箱/手机验证码，实际 `auth.js` 已使用邮箱密码；`AGENT.md` 的架构描述也落后于已接受的 ADR 0002。实施时一并更新相关说明。

## 本次验证记录

使用主项目已有 `.venv`，设置 `PYTHONDONTWRITEBYTECODE=1`，pytest 禁用缓存写入。

| 检查 | 结果 | 覆盖边界 |
| --- | --- | --- |
| 默认 pytest（配置仅收集 backend/tests） | 27 通过 | 后端已有用例 |
| 显式 pytest backend/tests supabase/tests | 58 通过、5 跳过 | 后端与数据库静态契约；没有指定连接时 SQL 行为测试跳过 |
| 指定已有独立本地库的 5 项 SQL 行为测试 | 5 通过 | 每项事务回滚；未创建/重建数据库，未访问云端 |
| `node --test frontend/tests/*.test.js` | 11 通过 | 前端既有纯逻辑用例 |
| 原报告 `auth-contract-probe-latest.py` | 3 项 session 缺失，退出码 1 | 合成 REST 响应，不访问网络 |
| 合成 DOM/会话/数量探针 | 复现账号残留、菜谱选择、盘数问题 | 无真实浏览器或真实账号 |
| 前端/后端同明细数值探针 | 蛋白质与脂肪各差 0.1g | 调用当前计算函数，无外部数据 |

已有测试合计 74 项通过（58 + 5 + 11，默认 27 项包含在 58 项内），不包含上述预期失败的诊断。
本地 SQL 测试第一次因沙箱禁止访问 PostgreSQL socket 而失败；允许连接同一独立测试库后 5 项均通过，不能把首次连接失败解释为数据库业务缺陷。

可重复执行的已有检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -o addopts='' -q -p no:cacheprovider backend/tests supabase/tests
PYTHONDONTWRITEBYTECODE=1 MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test python -m pytest -o addopts='' -q -p no:cacheprovider supabase/tests/test_auth_database.py
node --test frontend/tests/*.test.js
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python /Users/kenyu/.codex/visualizations/2026/10/09/01a11f64-c5fa-7ec0-8189-1ad049678441/auth-contract-probe-latest.py
```

## 下一步

统一方案与阶段验收见 [ADR 0005：业务持久化、账号隔离与数值口径](../adr/0005-business-persistence-and-isolation.md)。
