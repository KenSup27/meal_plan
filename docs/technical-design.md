# Meal Prep & Nutrition Planner 技术设计

## 1. MVP 架构

```text
移动端静态页面
        │
        └── FastAPI 单体应用
              ├── API：营养计算、菜谱、周计划、采购清单
              ├── 静态资源托管
              └── 未来接入 Supabase PostgreSQL
```

当前脚手架采用单体结构，以减少 MVP 的部署和认证复杂度。`frontend/` 暂时使用无构建依赖的静态页面，后续如果交互复杂度上升，再迁移到 Vue 3 或 React。`supabase/` 保留为后续持久化方案，数据库表结构尚未最终定稿。

## 2. 页面与路由

| 路由 | 页面 | MVP 能力 |
| --- | --- | --- |
| `/onboarding` | 营养基线 | 输入身体数据、查看 BMR/TDEE、修改并确认目标 |
| `/recipes` | 我的菜谱 | 查看、创建、编辑、删除菜谱 |
| `/recipes/new` | 新建菜谱 | 搜索食材、填写生重、实时汇总营养 |
| `/planner` | 周度规划 | 选择周次、日期、菜谱和份数 |
| `/shopping-list` | 采购清单 | 按分类展示合并后的生重，可勾选已购买 |

移动端底部导航固定显示“规划、菜谱、采购、我的”。表单数字输入必须限制为非负值，并在失焦时进行单位和范围校验。

## 3. 数据与计算规则

### 3.1 营养基线

```text
male_bmr   = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
female_bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
tdee       = bmr * activity_factor

cut  calories = tdee - 400
maintain     = tdee
bulk calories = tdee + 300

protein_g = weight_kg * 1.8
fat_g     = calories * 0.25 / 9
carb_g    = (calories - protein_g * 4 - fat_g * 9) / 4
```

如果计算出的碳水小于 0，接口返回可识别的业务错误，要求用户调整目标或基础数据，不允许静默返回负数。用户确认后，`profiles` 中的目标字段成为后续仪表盘的唯一基线。

### 3.2 菜谱营养

```text
recipe_nutrient = Σ(ingredient_nutrient_per_100g * raw_weight_g / 100)
```

`recipes` 中的汇总字段用于列表快速展示；保存或修改菜谱时由前端计算预览，并由后端/数据库校验后写入。正式版本可增加数据库触发器或专用 RPC，MVP 先在写入服务中统一计算。

### 3.3 采购清单

```text
shopping_item[ingredient_id] =
  Σ(recipe_ingredient.raw_weight_g * plan_item.servings)
```

采购接口按食材 ID 合并，返回食材名称、分类和总生重。分类排序固定为：肉禽、水产、蛋奶、蔬菜、水果、碳水、调料、其他。

## 4. FastAPI API 契约

所有接口前缀为 `/api/v1`，除健康检查外都需要 `Authorization: Bearer <supabase_access_token>`。

### `POST /nutrition/calculate`

请求：

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

响应：

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

### `POST /shopping-lists/preview`

请求：

```json
{
  "meal_plan_id": "00000000-0000-0000-0000-000000000000"
}
```

响应：

```json
{
  "week_start": "2026-10-12",
  "items": [
    {
      "ingredient_id": 1,
      "ingredient_name": "鸡胸肉",
      "category": "肉禽",
      "total_raw_weight_g": 1200.0
    }
  ]
}
```

接口只读取当前用户自己的计划。计划不存在、计划不属于当前用户或计划中包含已删除菜谱时，分别返回 `404` 或 `409`，不返回部分结果。

### `GET /health`

返回 `{ "status": "ok" }`，用于部署探针，不需要登录。

## 5. 前端状态约定

Pinia 建议拆分为 `authStore`、`profileStore`、`recipeStore`、`plannerStore`。服务端数据写入成功后再更新本地缓存；计算中的表单预览可以使用本地状态，但不能替代保存结果。所有异步操作都需要包含 loading、空状态和错误状态。

## 6. 验收标准

* 新用户可完成基线计算，并能手动修改推荐值后保存。
* 菜谱可添加至少一种食材和生重，营养汇总与公式一致。
* 周计划支持至少 5 个工作日和同一菜谱多次安排。
* 采购清单能合并不同菜谱中的同一种食材，且总克数正确。
* 用户 A 无法读取或修改用户 B 的 profile、recipe、meal plan。
* 页面在 375px 宽度下可以完成周计划和采购清单操作。
