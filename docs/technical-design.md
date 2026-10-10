# Meal Prep & Nutrition Planner 技术设计

## 当前架构

移动端静态页面由 FastAPI 托管。Supabase SDK 负责邮箱密码认证及会话刷新；
页面业务请求携带当前 JWT，FastAPI 验证用户后建立请求范围的 Supabase Data API 仓储。
数据库以 authenticated 角色执行 RLS。普通业务请求不使用 service_role。

六张业务表及约束见 ADR 0002；邮箱密码范围见 ADR 0004；持久化、隔离与数值口径见
[ADR 0005](adr/0005-business-persistence-and-isolation.md)。内存仓储仅通过测试依赖替换启用。

## 页面与状态

单页应用在 `/` 提供营养基线、菜谱、周计划、采购清单四个视图。
前端已保存数据来自 API，草稿和采购勾选只保留在当前页面内存。
旧 `meal-prep-planner-demo-v1` 全局缓存不读、不写、不自动迁移到登录账号。

认证用户发生变化时清空所有业务状态、表单和 DOM，取消旧请求；账号代次阻止旧异步结果回填。
同账号 token 刷新保留草稿。切周使用请求序号避免晚到响应覆盖当前周。
初始读取失败显示重试；保存失败保留草稿并显示错误，不宣称成功或降级本地保存。

## 数据与计算

身体输入使用 Mifflin–St Jeor 计算 BMR/TDEE，活动系数为 1.2、1.375、1.55。
减脂目标为 TDEE−400，维持为 TDEE，增肌为 TDEE+300；推荐蛋白质为体重×1.8。
脂肪默认占目标热量 25%，其余热量分配碳水；碳水不能为负。
用户确认的四项目标按一位小数量化存入 Profile；计划建立时复制目标快照。

菜谱是一盘菜。营养为 `Σ(每100g生重营养 × 单盘生重 / 100)`；
餐项乘 quantity 后，从原始明细分别累计餐项、日、周，最后各自舍入一位小数。
后端使用 Decimal/ROUND_HALF_UP，数据库使用 numeric；禁止累加已舍入的单盘或日汇总。
盘数为菜谱餐项 quantity 总和。人工餐影响营养，不计盘数和采购。
采购按食材 ID 合并 `Σ(单盘生重 × quantity)`，返回总生重。

菜谱归档后不能新排餐，但既有计划仍可读取及计算。停用食材也可用于历史计算。
已归档的原有餐项必须完整保持不变，才能在整体替换中保留；修改或新增引用被拒绝。

## API 契约

前缀 `/api/v1`。除 health、注册、登录和刷新外，接口均需要用户 Bearer token；
`/runtime-config.js` 只输出公开 URL/key 并禁止缓存，供页面先于认证初始化加载。
完整字段契约以 `/docs` 中的 OpenAPI 为准。

| 方法与路径 | 行为 |
| --- | --- |
| POST `/auth/register`、`/auth/login`、`/auth/refresh` | 返回 user 及规范 session；兼容原始 REST 顶层 token |
| POST `/auth/logout`、GET `/auth/me` | 退出会话、读取已验证用户 |
| GET `/health`、`/ready` | 进程探针；登录后的实际数据库可读探针 |
| POST `/nutrition/calculate` | 计算推荐，不保存基线 |
| PUT/GET `/profile/baseline` | 确认保存、恢复当前用户基线 |
| GET `/ingredients` | 真实 bigint ID 食材目录，选择器只提供 active 食材 |
| POST/GET `/recipes` | 创建/列出当前用户的未归档菜谱 |
| GET/PATCH/DELETE `/recipes/{id}` | 读取、整体编辑、归档；读取支持历史归档菜谱 |
| POST `/meal-plans` | 建立周一开始的计划及目标快照；重复周返回 409 |
| GET `/meal-plans/{week_start}` | 读取计划及 revision；不存在返回 404 |
| POST `/meal-plans/{week_start}/items` | 原子追加餐项 |
| PUT `/meal-plans/{week_start}/items` | 原子整体替换，包含 items 和读取时的 expected_revision |
| GET `/meal-plans/{week_start}/nutrition` | 七日及全周汇总、餐次完整性 |
| GET `/meal-plans/{week_start}/shopping-list` | 当前计划的分类采购生重 |

整体替换缺少版本号或版本已变化返回 409；前端重新读取后才能再次保存。
餐项替换保留已有 UUID，人工营养响应的 manual_nutrition 映射为提交的 manual_* 字段。
菜谱与食材明细通过 save_recipe 在一个事务内保存；餐项通过 save_plan_items 锁定父计划并写入。
无效输入整笔回滚，不留下空父记录或部分餐项。

唯一冲突返回 409，输入约束返回 422，未登录/失效凭据返回 401，不存在/其他用户记录返回 404，
缺配置/数据库不可用返回 503；不把 SQL 或凭据详情暴露给浏览器。

## 初始化、升级与验收

空项目按 schema.sql → seed.sql → business.sql 初始化。已有库使用显式迁移，
不要以重跑 schema.sql 升级。integrity.sql 同步旧部署缺失的既有完整性规则。
命名迁移、启动及完整验收命令见根 README 和 tests/e2e/README.md。

验收覆盖真实浏览器→FastAPI→Supabase 写入、账号隔离、重启/独立 origin 恢复、
采购与营养精度、失败草稿保留及 375px 布局。实际跨设备验证需另行执行。
