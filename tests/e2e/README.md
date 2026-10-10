# 真实浏览器端到端验收

默认测试不执行云端写入。明确选定测试项目、部署与当前代码相同的数据库升级后才运行。
需要 Node 22、Playwright 及本机 Chrome；独立安装的 Playwright 可通过 NODE_PATH 指定。
应用正常启动时加载本地环境文件，包含公开 Supabase URL/key，不需要 service_role。

```bash
uvicorn backend.app.main:app --env-file .env --host 127.0.0.1 --port 8021
MEAL_PREP_E2E_PROJECT=<测试项目引用> \
  MEAL_PREP_E2E_ARTIFACTS=/private/tmp/meal-prep-e2e-artifacts \
  node --env-file=.env tests/e2e/hosted.cjs
```

脚本创建唯一 UUID 标识的 A/B 专用账号，使用真实 Auth、用户 JWT、FastAPI 和 PostgreSQL。
覆盖注册/登录/刷新、错误密码、旧全局缓存隔离、基线、两道菜谱、指定菜谱排餐、盘数、
四项营养精度、生重采购、人工餐、旧版本覆盖拒绝、目标快照、刷新恢复、独立 origin，
以及 A→B→A 的隔离/越权拒绝和 375px 布局。

运行结束后撤销会话。凭据只保存到输出指定的 `/private/tmp/meal-prep-e2e-<UUID>.json`，
权限 0600，供本轮恢复及精确清理；不能提交它、浏览器 storageState 或访问令牌。
截图和 result.json 是验收证据；不要把包含真实用户数据的产物上传仓库。

停掉本轮应用后重新启动，再使用同一份临时清单验证持久化和故障行为：

```bash
MEAL_PREP_E2E_PROJECT=<同一测试项目引用> \
  MEAL_PREP_E2E_MANIFEST=/private/tmp/meal-prep-e2e-<UUID>.json \
  MEAL_PREP_E2E_ARTIFACTS=/private/tmp/meal-prep-e2e-artifacts \
  node tests/e2e/restore.cjs
```

该补充流程验证后端重启恢复、模拟服务 503 时保留草稿且不宣称成功、归档菜谱历史读取、
保留历史/人工餐的整体替换，以及切周不自动创建空计划。它会归档本轮已排餐的测试菜谱。
独立浏览器存储只能证明服务端恢复，不能代替实际跨设备测试。

所有 HTTP 写入都需要清理，无论成功或失败。先逐项核对本轮清单的精确 UUID/邮箱，
确认对应 auth.sessions 为零，再在同一管理事务中先删除这些账号的 meal_plans，
随后删除这些 auth.users，以免菜谱的 RESTRICT 外键先于计划级联删除。
必须使用 UUID 与精确邮箱的联合匹配，不能按前缀批量删除。
完整性函数需与 `supabase/integrity.sql` 同步，以支持已删除父记录的约束检查。
最后核对用户、Profile、菜谱/食材明细、计划/餐项回到运行前计数，再删除临时凭据清单。
