# 真实浏览器端到端验收

先运行无需云端账号的页面专项回归（启动不加载环境配置的本地应用，默认 8022）：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8022
# 另一个终端执行：
MEAL_PREP_E2E_URL=http://127.0.0.1:8022 node tests/e2e/retest-regressions.cjs
```

该脚本使用合成 Auth/业务响应，操作真实 375px 页面与 Swagger UI；覆盖退出后直接重登、
注册/错误密码/提交中切模式、缺配置/SDK、初始会话竞态、真实关闭端口后的连接拒绝、
浏览器离线、HTTP 503、会话取消，以及 Swagger 实际 Bearer 请求头。
可用 `MEAL_PREP_E2E_ARTIFACTS` 指定截图和结果输出目录。

默认测试不执行云端写入。明确选定测试项目、部署与当前代码相同的数据库升级后才运行。
需要 Node 22、Playwright 及本机 Chrome；独立安装的 Playwright 可通过 NODE_PATH 指定。
应用正常启动时加载本地环境文件，包含公开 Supabase URL/key，不需要 service_role。

```bash
uvicorn backend.app.main:app --env-file .env --host 127.0.0.1 --port 8021
MEAL_PREP_E2E_PROJECT=<测试项目引用> \
  MEAL_PREP_E2E_ARTIFACTS=reports/e2e \
  node --env-file=.env tests/e2e/hosted.cjs
```

脚本创建唯一 UUID 标识的 A/B 专用账号，使用真实 Auth、用户 JWT、FastAPI 和 PostgreSQL。
覆盖注册/登录/刷新、错误密码、旧全局缓存隔离、基线、两道菜谱、指定菜谱排餐、盘数、
四项营养精度、生重采购、人工餐、旧版本覆盖拒绝、目标快照、刷新恢复、独立 origin，
以及 A→B→A 的隔离/越权拒绝和 375px 布局。退出后的直接重登不会先点击模式标签；
Swagger 使用 B 的真实 token 请求 A 菜谱，并断言请求头正确且返回 404。

运行结束后撤销会话。凭据只保存到输出指定的 `<hosted 输出的 manifest 绝对路径>`，
位于系统临时目录的独立 `meal-prep-e2e-private-*` 目录（目录权限 0700、文件权限 0600），供本轮恢复及精确清理；不能提交它、浏览器 storageState 或访问令牌。
截图和 result.json 是验收证据；不要把包含真实用户数据的产物上传仓库。

停掉本轮应用后重新启动，再使用同一份临时清单验证持久化和故障行为：

```bash
MEAL_PREP_E2E_PROJECT=<同一测试项目引用> \
  MEAL_PREP_E2E_MANIFEST=<hosted 输出的 manifest 绝对路径> \
  MEAL_PREP_E2E_ARTIFACTS=reports/e2e \
  node tests/e2e/restore.cjs
```

该补充流程验证后端重启恢复、模拟服务 503 与连接拒绝时保留草稿且不宣称成功、归档菜谱历史读取、
保留历史/人工餐的整体替换，以及切周不自动创建空计划。它会归档本轮已排餐的测试菜谱。
独立浏览器存储只能证明服务端恢复，不能代替实际跨设备测试。

所有 HTTP 写入都需要清理，无论成功或失败。先逐项核对本轮清单的精确 UUID/邮箱，
确认对应 auth.sessions 为零，再在同一管理事务中先删除这些账号的 meal_plans，
随后删除这些 auth.users，以免菜谱的 RESTRICT 外键先于计划级联删除。
必须使用 UUID 与精确邮箱的联合匹配，不能按前缀批量删除。
完整性函数需与 `supabase/integrity.sql` 同步，以支持已删除父记录的约束检查。
最后核对用户、Profile、菜谱/食材明细、计划/餐项回到运行前计数，再删除临时凭据清单。

## 报告目录与查看

默认输出固定解析到项目根目录下的 `reports/e2e/<run-id>/`，与启动命令的工作目录无关。
`hosted.cjs` 和 `retest-regressions.cjs` 每次生成新的 UUID，不覆盖既有报告。
设置 `MEAL_PREP_E2E_ARTIFACTS` 可指定输出**根目录**，脚本仍追加 `<run-id>/`；
相对路径按项目根目录解析，绝对路径直接使用。旧版“变量直接指定最终目录”的含义已变更。
使用项目内自定义路径时，应放在已忽略的 `reports/` 下；不要将产物放到源码目录或提交它们。

脚本启动时输出运行 ID 与产物绝对路径。直接打开目录中的 JSON 和 PNG 查看结果：

```text
reports/e2e/<hosted-run-id>/
  run.json
  result.json
  *.png
  restore/<restore-attempt-id>/restore-result.json
reports/e2e/<regression-run-id>/
  run.json
  regression-result.json
  *.png
```

`restore.cjs` 必须设置 `MEAL_PREP_E2E_MANIFEST` 为前序 hosted 输出的清单路径。
不设置产物变量时，使用 Manifest 记录的原报告目录；若显式设置，则该根目录下必须
已经存在同一运行 ID 的 hosted `run.json`，不会创建无关运行。每次恢复验证在原运行内
创建新的 `restore/<UUID>/` 子目录，重复执行也不会覆盖。旧清单无报告路径时仅尝试
默认目录下的匹配标记；旧版运行没有标记时会明确失败，不会擅自创建目录。

Manifest 含密码，始终在项目外的私有临时目录，不写入报告目录。普通报告只记录运行元数据，
不复制 Manifest；报告仍可能含测试邮箱和业务数据，整个 `reports/` 已忽略。
`result.json` 等最终文件只有成功走到对应写入点才生成；仅有 `run.json` 不表示测试通过。
清理测试账号和会话后，按精确路径清理私有清单，保留需要的普通报告。

仅验证路径管理、不启动浏览器或连接数据库：

```bash
node --test tests/e2e/artifacts.test.cjs
```
