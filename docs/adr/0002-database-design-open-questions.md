# ADR 0002：MVP 数据库模型定稿

## 状态

已接受（2026-10-09）。

本 ADR 取代此前“讨论中”的数据库草案，作为 `supabase/schema.sql` 和
`supabase/seed.sql` 的设计依据。

当前邮箱＋密码 MVP 认证与“暂缓邮件/短信验证码”范围见 [ADR 0004](0004-email-password-mvp.md)。

## 决策

### 1. 核心实体与所有权

保留六张表：`profiles`、`ingredients`、`recipes`、`recipe_ingredients`、
`meal_plans`、`meal_plan_items`。

* `profiles.id` 引用 Supabase `auth.users.id`，新用户通过触发器自动创建 Profile。
* `recipes`、`meal_plans` 通过 `user_id` 归属 Profile。
* `recipe_ingredients` 和 `meal_plan_items` 通过父记录间接归属用户。
* 个人记录使用 `on delete cascade`；食材被菜谱引用时使用 `on delete restrict`。

### 2. 菜谱语义

`recipes` 表示“一盘可直接食用的菜”，不表示一锅菜或批量制作结果，因此不再有
`servings`、`yield`、`batch_weight` 或保存的营养汇总字段。每条
`recipe_ingredients.raw_weight_g` 是单盘生重；数据库通过延迟约束触发器禁止空菜谱提交。

延迟检查只约束事务结束时仍存在的菜谱，允许删除菜谱及账号级联清理。
食材从一道菜谱移动到另一道菜谱时，两端仍存在的菜谱都必须非空；整组替换食材需在同一事务完成。

菜谱营养由 `recipe_nutrition` View 从食材明细实时聚合，前端或缓存字段不具备权威性。

### 3. 计划与餐项

* `meal_plans.week_start` 必须是周一，`unique (user_id, week_start)` 保证每个用户每周一个计划。
* 计划保存创建时的 `target_kcal`、`target_protein_g`、`target_carbs_g`、`target_fat_g` 快照。
* `meal_plan_items.meal_type` 使用 `breakfast`、`lunch`、`dinner`；MVP 交互先使用午餐和晚餐。
* `input_mode` 使用 `recipe` 或 `manual`。
* 菜谱餐要求 `recipe_id` 和正数 `quantity`，人工餐要求整餐 `manual_*` 营养值且不允许 `recipe_id`。
* 不设置 `(meal_plan_id, planned_date, meal_type)` 唯一约束，同一天同一餐可以有多条菜谱记录。
* 触发器保证餐项日期位于计划周内、菜谱与计划属于同一用户，且归档菜谱不能加入新餐项。
* 修改计划的 `week_start` 同样检查已有餐项；已有餐项会落到新计划周之外时拒绝修改。

### 4. 食材与营养口径

* 所有营养值统一为每 100g 生重，`nutrition_basis = 'raw'`。
* `ingredients.category` 使用稳定代码：`meat`、`seafood`、`dairy`、`vegetable`、
  `fruit`、`carb`、`seasoning`、`other`；展示层负责本地化。
* 食材不物理删除，使用 `is_active = false` 归档。已登录用户可读取全部食材，选择器应自行过滤启用项，以保证历史菜谱仍可计算。
* Seed 按唯一名称 Upsert，当前提供 34 种可重复导入的测试食材。

### 5. 派生查询

数据库不持久化采购清单，提供以下安全 View：

* `recipe_nutrition`：按原始食材明细计算单盘营养。
* `meal_plan_item_nutrition`：按 `quantity` 或人工餐营养计算餐项。
* `meal_plan_nutrition`：按日期和餐次汇总，允许同餐多条记录。
* `meal_plan_totals`：整周计划汇总并返回目标快照。
* `shopping_list_items`：只合并 `input_mode = 'recipe'` 的原始生重。

这些 View 使用 `security_invoker`，并向 `authenticated` 只授予查询权限，遵循底层 RLS。

### 6. 安全

所有六张持久化表启用 RLS。Profile、菜谱、计划和关联明细仅允许当前用户访问；
食材对登录用户只读；匿名角色对表和 View 均无权限。数据库触发器额外校验跨表所有权，
避免绕过 API 直接写入其他用户的计划或菜谱。

## 未纳入本次模型的内容

早餐组成食材、批量制作/分装、采购清单持久化、Auth/RLS 之外的协作权限，以及人工餐的
食材明细，留待后续 ADR；当前人工餐按整餐营养值记录。
