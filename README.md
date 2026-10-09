# Meal Prep & Nutrition Planner

面向需要健身、控制体型并有带饭习惯的上班族的周度营养规划工具。

## 当前状态

项目已建立 MVP 工程脚手架，当前包含 FastAPI 入口、营养计算 API、移动端静态页面、测试和版本管理。菜谱、周计划、采购清单以及最终数据库结构仍待继续设计和实现。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

打开 <http://127.0.0.1:8000/>。

运行测试：

```bash
pytest
```

## 文档入口

* [开发计划](PLAN.md)
* [原始产品需求文档（内容已合并至 PLAN.md）](meal_prep_nutrition_planner_prd.md)
* [技术设计与 API 契约](docs/technical-design.md)
* [数据库 Schema 与 RLS](supabase/schema.sql)
* [基础食材 Seed](supabase/seed.sql)

## Supabase 初始化

在 Supabase 项目的 SQL Editor 中按顺序执行：

1. `supabase/schema.sql`
2. `supabase/seed.sql`

Schema 依赖 Supabase Auth 的 `auth.users` 表，并会在新用户注册后自动创建对应的 `profiles` 记录。执行后应重点验证：匿名用户不能读取数据、登录用户只能读取自己的个人数据、所有已登录用户可以读取启用中的基础食材。

## 下一步开发

1. 讨论并确认数据库表结构和午餐/全天营养口径。
2. 实现食材目录、菜谱和周计划 API。
3. 实现采购清单合并逻辑。
4. 决定本地 JSON 存储到 Supabase 的迁移时点。
5. 再接入 Auth、RLS 和正式持久化。
