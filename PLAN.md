# Meal Prep & Nutrition Planner 项目总计划

> 2026-10-09 MVP 认证范围更新（用户最新决定，覆盖旧版验证码要求）：使用邮箱＋密码注册登录，关闭邮箱验证；邮件 OTP、Magic Link、短信验证码及邮件找回密码暂缓，不以 SMTP/Resend 配置作为 MVP 前置条件。保留 Supabase Auth、自动建档和多用户 RLS 隔离。数据库工作流不实现前后端登录界面或 API，交接与验收边界见 [ADR 0004](docs/adr/0004-email-password-mvp.md)。

> 本文是下一阶段开发窗口的唯一工作基线，合并了原始 PRD 和本窗口讨论出的产品范围、架构方向、数据库原则、脚手架现状和后续任务。数据库 SQL 草案在本计划确认前不视为最终方案。

## 0. 产品需求基线

### 0.1 产品背景

目标用户是需要健身、控制体型且有带饭习惯的上班族。

核心痛点：

* 难以精准控制每日热量和三大营养素。
* 每周不知道该准备什么饭。
* 不清楚去超市应该购买多少生重食材。

核心产品逻辑：

```text
前置规划 → 生重采购 → 按量烹饪 → 减少餐后记录成本
```

产品不是传统的餐后打卡工具，而是以周度排餐和采购清单为核心。

### 0.2 用户工作流

#### 阶段一：初始资产建设

1. 输入性别、年龄、身高、体重、活动系数和目标。
2. 系统计算 BMR、TDEE、目标热量和三大营养素。
3. 用户在结果页手动调整推荐值。
4. 用户确认后，最终数值成为当前营养基线。
5. 用户创建自己的“一盘菜”菜谱。
6. 从基础食材库选择食材，录入单盘生重。

#### 阶段二：周度规划与执行

1. 创建某一周的计划。
2. 为日期安排午餐和晚餐菜谱。
3. 同一天同一种餐允许添加多道菜。
4. 查看每日和整周营养汇总。
5. 一键生成按分类合并的生重采购清单。

早餐从数据结构上预留，但不作为第一阶段必需的交互；后续以人工输入方式加入全天营养计算。

### 0.3 功能模块

#### 营养基线计算器

输入：

* 性别
* 年龄
* 身高
* 体重
* 活动系数：久坐 1.2、偶尔活动 1.375、规律训练 1.55
* 目标：减脂、维持、增肌

结果页必须允许手动修改目标热量、蛋白质、碳水和脂肪，确认后再保存。

#### 私房菜谱工坊

菜谱定义为一盘菜，而不是一锅菜。操作流程：

```text
命名菜谱 → 选择基础食材 → 输入每盘生重 → 计算营养 → 保存
```

#### 周度带饭规划器

支持选择日期、餐次、菜谱和数量。第一阶段餐次为午餐和晚餐，餐次统一通过 `meal_type` 管理。

仪表盘应显示已规划营养、目标、已规划餐次和缺少餐次，不应把尚未录入早餐造成的差额直接判断为营养不足。

#### 智能采购清单

将本周计划中由菜谱产生的食材按 `ingredient_id` 合并，并累加生重，按肉禽、水产、蛋奶、蔬菜、水果、碳水、调料、其他分组展示。

### 0.4 核心算法

使用 Mifflin-St Jeor 公式：

```text
男性 BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄 + 5
女性 BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄 - 161
TDEE = BMR × 活动系数
```

目标热量：

```text
减脂 = TDEE - 400 kcal
维持 = TDEE
增肌 = TDEE + 300 kcal
```

默认宏量营养素：

```text
蛋白质 = 体重(kg) × 1.8g
脂肪 = 目标热量 × 25% ÷ 9
碳水 = (目标热量 - 蛋白质热量 - 脂肪热量) ÷ 4
```

如果碳水计算结果小于 0，服务端返回业务错误，不静默保存负数。

菜谱营养：

```text
单盘营养 = Σ(每100g食材营养 × raw_weight_g ÷ 100)
```

计划营养：

```text
Σ(菜谱营养 × quantity) + Σ(人工输入餐营养)
```

后端使用 Decimal 或等价的高精度计算；接口和页面展示统一保留 1 位小数。

### 0.5 产品级技术约束

* 移动端优先，优先保证 375px 宽度下的周计划和采购清单体验。
* 基础食材至少准备 30 种可测试数据，当前 Seed 草案包含 33 种。
* 所有营养数据在 MVP 中统一按每 100g 生重记录。
* 前端传入的营养汇总只能作为展示缓存，不能作为服务端权威来源。
* 原始 PRD 中“Vue/React + Supabase 直连 + FastAPI”的架构描述已被本计划第 4 节的最快 MVP 架构覆盖；开发时以第 4 节为准。

### 0.6 用户登录是 MVP 必须项

由于菜谱、营养基线和周计划都属于个人数据，MVP 不能以匿名用户作为正式产品形态。最小登录范围包括：

* 邮箱验证码登录：输入邮箱并接收一次性验证码。
* 手机号验证码登录：输入国家/地区码、手机号并接收短信验证码。
* 手机号验证码是硬性要求，不能用密码登录替代。
* 登录状态恢复。
* 登出。
* 未登录用户访问业务页面时跳转登录页。
* 注册成功后自动创建对应的 `profiles` 记录。
* 用户只能访问自己的 profile、recipe 和 meal plan。

第一阶段暂不做第三方登录、团队邀请、角色权限、MFA、社交账号绑定和密码登录。登录身份使用 Supabase Auth，业务数据使用 `auth.users.id` 作为用户主键来源；FastAPI 接收并验证 Bearer Token，数据库通过 RLS 做最终数据隔离。

手机号验证码需要配置 Supabase 支持的短信服务商；这是上线前的外部依赖，包含发送频率限制、模板、地区覆盖和费用配置。邮箱验证码同样需要配置邮件发送和域名策略。

当前本地脚手架可以暂时匿名启动，但在完成 Auth、RLS 和个人数据隔离前，不视为 MVP 完成。

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
4. 第三方登录、密码登录、团队权限、MFA 等高级认证能力。
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
* 数据库：Supabase 作为正式认证和持久化目标；当前脚手架尚未接入。
* 计算：营养计算在服务端完成，避免前后端规则不一致。
* 版本：Git `main` 分支，语义化版本从 `v0.1.0` 开始。

### 暂不引入

* Vue/React 构建链。
* 独立部署的第二个后端服务。
* 复杂离线同步。
* 采购清单持久化表。
* 一锅菜和批量分装模型。

当 MVP 验证通过后，再评估是否迁移到 Vue/React 和正式前后端分离部署。

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

### 阶段四：接入认证与正式持久化

1. Supabase Auth 注册、登录、登出和会话恢复。
2. Supabase Schema 和 Seed。
3. profiles 自动创建和 RLS 验收。
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

## 11. API 规划

当前脚手架已经提供：

### `GET /api/v1/health`

用于本地和部署健康检查：

```json
{ "status": "ok" }
```

### `POST /api/v1/nutrition/calculate`

请求字段：

```json
{
  "sex": "female",
  "age": 30,
  "height_cm": 165,
  "weight_kg": 60,
  "activity_factor": 1.375,
  "goal": "cut"
}
```

响应字段：

```json
{
  "bmr_kcal": 1320.0,
  "tdee_kcal": 1815.0,
  "target_kcal": 1415.0,
  "protein_g": 108.0,
  "carbs_g": 154.2,
  "fat_g": 39.3
}
```

下一阶段规划实现：

认证不由 FastAPI 自己发送验证码：前端通过 Supabase Auth 发起邮箱 OTP 或手机号 SMS OTP，拿到 Access Token 后再请求 FastAPI；FastAPI 只验证 Token 并建立当前用户上下文。

* `GET /api/v1/ingredients`
* `POST /api/v1/recipes`
* `GET /api/v1/recipes`
* `PATCH /api/v1/recipes/{recipe_id}`
* `POST /api/v1/meal-plans`
* `GET /api/v1/meal-plans/{week_start}`
* `PUT /api/v1/meal-plans/{week_start}/items`
* `GET /api/v1/meal-plans/{week_start}/nutrition`
* `GET /api/v1/meal-plans/{week_start}/shopping-list`

在数据库结构和认证方案确认前，不提前实现完整 CRUD API。

## 12. 三窗口开发协作计划

后续开发拆分为三个独立窗口：数据库窗口、后端窗口、前端窗口。三个窗口共享同一工作目录，因此必须遵守文件边界和交接顺序。

### 12.1 数据库窗口

#### 负责范围

数据库窗口只负责：

* `supabase/schema.sql` 或正式迁移文件。
* `supabase/seed.sql` 和基础食材数据。
* `supabase/migrations/`。
* 数据库相关 RLS、索引、View、触发器。
* `docs/adr/0002-database-design-open-questions.md` 等数据库设计文档。

数据库窗口不负责：

* 修改 `backend/` 业务代码。
* 修改 `frontend/` 页面代码。
* 自行改变 API 返回格式。

#### 必须完成的内容

1. 定稿 `profiles`、`ingredients`、`recipes`、`recipe_ingredients`、`meal_plans`、`meal_plan_items`。
2. 落实 `meal_type`：`breakfast`、`lunch`、`dinner`。
3. 落实 `input_mode`：`recipe`、`manual`。
4. 落实 `quantity` 的“一盘菜数量”语义。
5. 确认 `recipe_id` 在人工餐模式下可为空。
6. 保存周计划创建时的营养目标快照。
7. 确认菜谱归档、外键和删除策略。
8. 确认 RLS：用户只能访问自己的个人数据，基础食材登录后只读。
9. 提供至少 30 种基础食材 Seed。
10. 为菜谱营养和计划营养提供 View、RPC 或明确的查询方式。
11. 提供 `auth.users → profiles` 的注册后自动建档方案。
12. 验证匿名、已登录用户和跨用户访问的 RLS 行为。
13. 配置并记录邮箱 OTP 和手机号 SMS OTP 的 Supabase Auth 策略。
14. 明确短信服务商、邮件发送服务、验证码有效期和发送频率限制。

#### 数据库窗口交付标准

* Schema 可以在干净的 Supabase 项目中按顺序执行。
* Seed 可以重复执行，不产生重复基础食材。
* RLS 有最少一组跨用户访问验证。
* 新用户注册后可以自动得到一条 `profiles` 记录。
* 邮箱 OTP 和手机号 SMS OTP 在目标部署环境中均可实际发送并完成验证。
* 明确字段类型、约束、索引和时区规则。
* 在 `PLAN.md` 或数据库 ADR 中记录所有与原草案不同的决定。

### 12.2 后端窗口

#### 负责范围

后端窗口只负责：

* `backend/`。
* `requirements.txt`、`pyproject.toml` 中的后端依赖。
* `backend/tests/`。
* API 契约和后端相关技术文档。

后端窗口不负责：

* 修改数据库迁移的业务语义。
* 修改前端页面和样式。
* 将未确认的字段直接写入数据库。

#### 必须完成的内容

1. 保持现有营养计算 API 和 Decimal 精度规则。
2. 实现食材查询接口。
3. 实现菜谱 CRUD 和菜谱营养聚合。
4. 实现周计划及餐项 CRUD。
5. 实现按日期、餐次和整周的营养汇总。
6. 实现采购清单：只合并 `input_mode = recipe` 的菜谱餐项。
7. 校验 `meal_type`、`input_mode`、`quantity` 和所有权。
8. 为每个 API 增加成功、校验失败、权限失败和不存在资源的测试。
9. 在数据库接入前允许使用 Mock Repository 或本地适配器。
10. 增加统一的当前用户依赖，验证 Supabase Bearer Token。
11. 对未登录请求返回 401，对无权资源访问返回 403 或 404。
12. 后端不负责发送验证码，只负责验证 Supabase 返回的访问令牌和当前用户。

#### 后端窗口交付标准

* OpenAPI 文档与 `PLAN.md` 中的 API 规划一致。
* 不能信任前端提交的营养汇总，服务端必须重新计算。
* 所有个人数据接口都以当前用户身份为边界。
* 关键计算和采购合并有自动化测试。
* 登录用户和未登录用户的 API 行为有自动化测试。
* 提供前端可以直接使用的请求、响应和错误格式。

### 12.3 前端窗口

#### 负责范围

前端窗口只负责：

* `frontend/`。
* 页面交互、表单校验、移动端布局和页面状态。
* 前端测试或浏览器验收材料。

前端窗口不负责：

* 修改 `supabase/` 数据库结构。
* 直接绕过后端实现权威营养计算。
* 修改 API 的字段语义。

#### 必须完成的内容

1. 营养基线表单和结果页手动调整。
2. 一盘菜菜谱创建和编辑。
3. 午餐/晚餐周计划编辑。
4. `meal_type` 选择和同餐多条菜品展示。
5. 每日营养汇总、目标快照和未录入餐次提示。
6. 采购清单按分类展示和移动端勾选交互。
7. 处理 loading、空状态、错误状态和表单校验。
8. 暂时为早餐保留数据和页面扩展位，但不强制实现早餐录入。
9. 增加登录、注册、登出页面和会话状态管理。
10. 对未登录用户保护菜谱、计划和采购清单页面。
11. 提供邮箱 OTP 和手机号 SMS OTP 两种登录入口。
12. 手机号输入包含国家/地区码、验证码倒计时、重发和错误提示。

#### 前端窗口交付标准

* 在 375px 宽度下可以完成核心流程。
* 不在前端保存权威营养结果。
* API 错误可以向用户显示可理解的提示。
* 页面使用 API 契约中的字段，不私自依赖数据库列名。
* 关键流程至少完成一次手动验收：基线 → 菜谱 → 计划 → 采购单。
* 手动验收包含：注册 → 登录 → 刷新页面保持登录 → 登出 → 业务页不可访问。
* 手动验收分别覆盖：邮箱验证码登录、手机号短信验证码登录、验证码过期、重复发送限制。

### 12.4 三窗口依赖顺序

```text
数据库窗口：定稿表结构、Auth 关联、RLS、Seed、查询方式
        │
        ▼
后端窗口：实现认证依赖、Repository、业务服务、API、测试
        │
        ▼
前端窗口：实现登录状态、接入 API、实现页面、完成端到端验收
```

前端可以在后端未完成时使用 Mock 响应开发视觉和交互；但正式联调必须以后端 OpenAPI 和数据库最终字段为准。

数据库窗口和后端窗口可以部分并行，但一旦字段语义发生变化，必须先更新 `PLAN.md` 或 ADR，再同步给另外两个窗口。

### 12.5 文件边界与 Git 规则

推荐分支命名：

```text
feature/database-schema
feature/backend-api
feature/frontend-mvp
```

每个窗口开始前：

```bash
git status
git pull --rebase
```

每个窗口只提交自己负责范围内的文件，提交信息建议使用：

```text
db: finalize meal plan schema
backend: add shopping list endpoint
frontend: add weekly planner page
docs: update API contract
```

`PLAN.md`、`README.md` 和 ADR 属于共享文档，只在发生跨窗口设计变化时修改。版本标签只由集成阶段创建，不由单个开发窗口随意创建。

### 12.6 集成验收顺序

1. 数据库窗口完成干净环境执行和 RLS 验收。
2. 后端窗口连接最终 Schema，运行认证和 API 自动化测试。
3. 前端窗口接入登录和后端 API，完成移动端核心流程。
4. 集成窗口执行完整链路：

```text
注册/登录 → 保存营养基线 → 创建两道菜 → 安排午餐/晚餐
→ 查看每日营养 → 生成合并采购清单
```

5. 通过后创建下一个版本，例如 `v0.2.0`。
