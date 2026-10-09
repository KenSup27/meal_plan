# Meal Prep & Nutrition Planner 开发计划

> 本文是下一阶段开发窗口的工作基线。它整理了本窗口已经讨论并确认的产品范围、架构方向、数据库原则、脚手架现状和后续任务。数据库 SQL 草案在本计划确认前不视为最终方案。

## 1. 项目目标

为有健身、体型管理和带饭习惯的上班族提供一个“提前规划 → 按生重采购 → 按份备餐”的工具。

核心闭环：

```text
营养基线 → 创建一盘菜的菜谱 → 规划午餐/晚餐 → 汇总营养 → 生成生重采购清单
```

## 2. MVP 范围

### MVP 必须包含

1. 营养基线计算：性别、年龄、身高、体重、活动系数、目标。
2. 用户可以手动修改推荐的热量和三大营养素目标。
3. 菜谱管理：菜谱定义为“一盘菜 / 一份可直接食用的菜品”。
4. 菜谱食材按生重录入，并计算这一盘菜的营养。
5. 周度计划：支持午餐和晚餐。
6. 同一天同一种餐允许有多条菜谱记录。
7. 采购清单：按食材合并本周菜谱所需生重。

### 后续功能，先预留数据模型

1. 早餐作为人工输入内容参与全天营养汇总。
2. 人工早餐的食材明细输入和采购计算。
3. 一锅菜批量制作、分装份数和批量采购。
4. Auth、RLS、Supabase 正式持久化。
5. 更复杂的推荐算法、离线同步和多设备协作。

早餐的 `meal_type` 从第一版就预留为 `breakfast`，但第一阶段不要求完成早餐交互。

## 3. 已确定的产品语义

### 3.1 Recipe 是一盘菜

一个 `recipe` 表示一盘可直接食用的菜，不表示一锅菜，也不表示批量制作结果。

例如：

```text
鸡胸肉西兰花
鸡胸肉：150g 生重
西兰花：200g 生重
橄榄油：5g 生重
```

因此：

* `recipe_ingredients.raw_weight_g` 是这一盘菜的生重。
* `recipes` 暂时不需要 `servings`、`batch_weight`、`yield` 等字段。
* 菜谱营养直接由食材明细计算，不再进行整锅营养除以份数。
* 未来若支持一锅菜分装，再增加批量模式和产出份数。

### 3.2 计划项数量

`meal_plan_items.quantity` 表示计划吃几盘，建议不要使用 `servings`，以免与未来批量菜谱概念混淆。

采购量：

```text
recipe_ingredients.raw_weight_g × meal_plan_items.quantity
```

### 3.3 餐次

统一使用 `meal_type` 管理：

```text
breakfast
lunch
dinner
```

MVP 实际使用午餐和晚餐；早餐只预留。

### 3.4 菜谱输入与人工输入

`meal_plan_items` 需要区分：

```text
input_mode = recipe
input_mode = manual
```

菜谱餐：使用 `recipe_id` 和 `quantity` 计算。

人工餐：未来使用 `manual_kcal`、`manual_protein_g`、`manual_carbs_g`、`manual_fat_g` 等字段参与汇总，`recipe_id` 为空。

人工早餐究竟是直接录入整餐营养，还是录入鸡蛋、牛奶、面包等组成食材后由系统计算，下一阶段实现早餐时再确认。最快 MVP 建议先录入整餐营养值。

### 3.5 营养仪表盘口径

每天计算：

```text
早餐营养 + 午餐营养 + 晚餐营养
```

在早餐尚未录入时，页面应显示：

* 当前已规划营养
* 当前目标
* 已规划餐次
* 尚未录入餐次

不要把缺少早餐造成的差额直接标记成“营养不足”。

## 4. MVP 技术架构

当前以最快验证为目标，采用单体结构：

```text
移动端静态页面
        │
        └── FastAPI 单体应用
              ├── /api/v1 API
              ├── 营养计算服务
              ├── 静态资源托管
              └── 后续接入 Supabase PostgreSQL
```

### 当前选择

* 后端：FastAPI + Pydantic。
* 前端：无构建依赖的 HTML/CSS/JavaScript 移动端页面骨架。
* 数据库：Supabase 作为后续正式持久化目标；当前不提前锁定最终表结构。
* 计算：营养计算在服务端完成，避免前后端规则不一致。
* 版本：Git `main` 分支，语义化版本从 `v0.1.0` 开始。

### 暂不引入

* Vue/React 构建链。
* 独立部署的第二个后端服务。
* 复杂离线同步。
* 采购清单持久化表。
* 一锅菜和批量分装模型。

当 MVP 验证通过后，再评估是否迁移到 Vue/React、Supabase Auth/RLS 和正式前后端分离部署。

## 5. 数据库候选模型

### 5.1 用户

使用 Supabase 的 `auth.users` 作为登录用户表，业务扩展使用 `profiles`：

```text
profiles
- id → auth.users.id
- display_name
- sex
- age
- height_cm
- weight_kg
- activity_factor
- goal
- target_kcal
- protein_g
- carbs_g
- fat_g
- baseline_confirmed_at
- created_at
- updated_at
```

`profiles` 保存当前基线；周计划保存创建时的营养目标快照，避免用户后续修改目标影响历史计划。

### 5.2 全局食材

```text
ingredients
- id
- name
- category
- nutrition_basis
- kcal_per_100g
- protein_per_100g
- carbs_per_100g
- fat_per_100g
- data_source
- is_active
- created_at
```

MVP 统一使用每 100g 生重营养数据：

```text
nutrition_basis = raw
```

数据库分类建议使用稳定代码，而不是中文展示文本：

```text
meat
seafood
dairy
vegetable
fruit
carb
seasoning
other
```

前端负责显示中文名称。食材不建议物理删除，使用 `is_active = false`，避免历史菜谱失效。

### 5.3 一盘菜菜谱

```text
recipes
- id
- user_id
- name
- description
- archived_at
- created_at
- updated_at
```

```text
recipe_ingredients
- recipe_id
- ingredient_id
- raw_weight_g
```

当前不把 `total_kcal`、`total_protein_g` 等汇总字段作为权威数据。权威数据来自菜谱食材明细聚合，可通过数据库 View 或服务端查询生成：

```text
recipe_nutrition
- recipe_id
- total_kcal
- total_protein_g
- total_carbs_g
- total_fat_g
```

### 5.4 周计划

```text
meal_plans
- id
- user_id
- week_start
- status
- target_kcal
- target_protein_g
- target_carbs_g
- target_fat_g
- created_at
- updated_at
```

约束：

```text
unique(user_id, week_start)
```

`week_start` 统一保存周一日期。

### 5.5 计划餐项

```text
meal_plan_items
- id
- meal_plan_id
- planned_date
- meal_type
- input_mode
- recipe_id nullable
- meal_name nullable
- quantity nullable
- manual_kcal nullable
- manual_protein_g nullable
- manual_carbs_g nullable
- manual_fat_g nullable
- sort_order
- created_at
```

约束逻辑：

```text
input_mode = recipe
→ recipe_id 必填
→ quantity > 0

input_mode = manual
→ recipe_id 为空
→ manual_* 字段必填
```

同一天同一餐允许多条记录，例如晚餐可以有牛肉和蔬菜两道菜。不要设置 `unique(meal_plan_id, planned_date, meal_type)`，否则无法表示多道菜。

## 6. 采购清单设计

MVP 不建立 `shopping_lists` 表。采购清单是周计划的实时派生结果：

```text
meal_plan_items(input_mode = recipe)
    → recipes
    → recipe_ingredients
    → ingredients
    → 按 ingredient_id 合并 raw_weight_g
```

人工输入餐默认不进入采购清单，因为可能来自外卖、食堂或已经购买的食物。

未来如果人工早餐也要参与采购，再增加组成明细表，例如：

```text
meal_plan_item_components
- meal_plan_item_id
- ingredient_id
- raw_weight_g
```

## 7. 数据库安全原则

接入 Supabase 后：

* `profiles`、`recipes`、`recipe_ingredients`、`meal_plans`、`meal_plan_items` 只能由所属用户读写。
* `ingredients` 对已登录用户只读。
* 食材由管理员或 Seed 过程维护。
* 菜谱删除优先采用归档；历史计划引用的菜谱不能直接硬删除。
* 菜谱和计划相关写入应使用事务，避免出现孤立关联记录。

## 8. 当前脚手架

已建立：

* [AGENT.md](AGENT.md)：开发规则和常用命令。
* [README.md](README.md)：项目入口。
* [requirements.txt](requirements.txt)：Python 依赖。
* [backend/app/main.py](backend/app/main.py)：FastAPI 入口和静态页面托管。
* [backend/app/api/routes.py](backend/app/api/routes.py)：健康检查和营养计算 API。
* [backend/app/services/nutrition.py](backend/app/services/nutrition.py)：BMR/TDEE 计算服务。
* [frontend/index.html](frontend/index.html)：移动端页面骨架。
* [frontend/app.js](frontend/app.js)：页面 API 调用骨架。
* [backend/tests/test_api.py](backend/tests/test_api.py)：API 测试骨架。
* [supabase/schema.sql](supabase/schema.sql)：尚未定稿的数据库草案。
* [supabase/seed.sql](supabase/seed.sql)：33 种基础食材测试数据。

## 9. 下一窗口开发顺序

### 阶段一：先确认数据库

1. 确认 `meal_type`、`input_mode` 和 `quantity` 字段。
2. 确认人工早餐采用整餐营养录入还是食材明细录入。
3. 按本计划修订 `supabase/schema.sql`，不要保留“一锅菜 servings”语义。
4. 确认 RLS、归档和外键删除策略。

### 阶段二：实现 MVP API

1. 食材查询。
2. 菜谱创建、查询、修改、归档。
3. 菜谱营养聚合。
4. 周计划和计划餐项 CRUD。
5. 按餐次和日期汇总营养。
6. 生成采购清单。

### 阶段三：完善页面

1. 营养基线确认页。
2. 一盘菜菜谱创建页。
3. 午餐/晚餐周计划页。
4. 每日营养汇总和缺少餐次提示。
5. 采购清单页。

### 阶段四：接入正式持久化

1. Supabase Auth。
2. Supabase Schema 和 Seed。
3. RLS 验收。
4. 本地运行数据迁移方案。

## 10. 版本信息

当前版本：`0.1.0`

Git 状态：

```text
branch: main
tag: v0.1.0
commit: b52b8e4 chore: initialize MVP project scaffold
```

下一阶段完成数据库定稿后，建议创建：

```text
v0.2.0 - database model and CRUD API skeleton
```
