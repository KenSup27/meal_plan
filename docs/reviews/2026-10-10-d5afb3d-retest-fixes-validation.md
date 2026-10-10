# main@d5afb3d 复测问题修复与验收

## 结果与范围

2026-10-10，已按统一方案在 `codex/retest-d5afb3d-fixes` 完成三项修复及回归。
基线为 `d5afb3d7e30bcc3383d7d6c7b3691d4366d1befd`，主项目 main 保持该提交且工作区干净。
本轮没有推送或合并 GitHub，也没有数据库迁移、增表或 RLS 调整。

修改前的复核证据与方案见 `2026-10-10-d5afb3d-retest-review-and-plan.md`。

## 实现

1. **退出后直接重登**：认证按钮由显式提交状态和 SDK/配置是否可用统一渲染。
   成功、失败、退出均恢复按钮；提交中禁止重复提交和模式切换。
   初始 getSession 的迟到结果不能覆盖之后的登录事件，同账号 token 刷新不清空业务草稿。
   注册后尚无 session 时正确回到登录模式；SDK 抛出异常时也恢复按钮。
2. **连接失败提示**：在业务 fetch 边界包装明确的网络 ApiError。
   读取失败提示检查网络；写入中断说明结果尚未确认、需先核对再重试，保留草稿且不自动重放。
   AbortError 继续用于静默取消，JSON 序列化错误不被误判为断网，HTTP 状态错误保持原语义。
   AuthRetryableFetchError 使用相同中文连接提示；现有 app.js 已消费 ApiError.message，无需改变业务渲染。
3. **Swagger Bearer**：用户校验、请求仓储、auth/me、auth/logout 共用 HTTPBearer 凭据依赖。
   移除普通 authorization Header 参数，生成 BearerAuth 安全方案及受保护操作的 security 声明。
   缺少/错误/空凭据继续返回中文 401 与 WWW-Authenticate，缺配置为 503；公开认证接口保持公开。
   用户校验与 RLS 仓储使用同一规范化 token，不改变真实 Supabase 校验及用户隔离。

修正 hosted.cjs 登录辅助函数，直接重登不再自动点击模式标签绕过问题。
新增确定性页面专项脚本与后端 OpenAPI/鉴权契约测试；restore.cjs 同时覆盖 HTTP 503 和传输失败。

## 本轮验证

| 范围 | 结果 |
| --- | --- |
| FastAPI + 真实本地 PostgreSQL | 110 passed，0 skipped，0 failed |
| 前端逻辑测试 | 18 passed，0 failed |
| 确定性 Chrome 专项回归 | 17 项通过 |
| 真实 Supabase Chrome 主流程 | 21 项通过 |
| 实际后端重启及故障/历史补充 | 6 项通过 |
| git diff --check 与相关 JavaScript 语法检查 | 通过 |

后端仅保留一条既有 Starlette/httpx TestClient 弃用提示，未出现功能测试失败。

```bash
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest backend/tests supabase/tests -o addopts='' -p no:cacheprovider -q
node --test frontend/tests/*.test.js
node tests/e2e/retest-regressions.cjs
# 真实云端测试及恢复流程的环境变量见 tests/e2e/README.md
```

专项脚本操作真实 375px DOM，认证/业务响应为合成数据，Swagger UI 为实际应用生成。
覆盖登录→退出→不切标签直接重登、注册退出、错误密码重试、提交中切模式与重复提交、
缺配置/SDK、初始会话竞态、无会话注册、同账号 token 刷新保留草稿、退出取消旧请求。
关闭真实本地 TCP 监听端口后检查 Chrome 的 `net::ERR_CONNECTION_REFUSED`，
浏览器离线检查 `net::ERR_INTERNET_DISCONNECTED`；两者均显示中文未确认提示、保留草稿、恢复按钮。
另验证 HTTP 503、读取失败重试，以及 Swagger Authorize 实际发送单个正确 Bearer 前缀。

真实云端主流程覆盖邮箱密码注册/登录/刷新、直接重登、营养基线、菜谱、指定菜谱排餐、
数量与四项营养精度、生重采购、人工餐、陈旧覆盖拒绝、目标快照、刷新与独立浏览器存储恢复、
A→B→A 隔离和 375px 无横向溢出。跨用户检查先确认真实 B 请求头，再验证读/编辑/归档均 404；
实际 Swagger 同样携带 B 的有效 token 请求 A 菜谱得到 404，A 重登后菜谱仍存在且名称未被修改。

真实本地应用 8023 进程停止后重新启动，再读取相同云端基线、两道菜谱和三项餐计划。
营养仍为 1435.1 kcal / 146.7g 蛋白质 / 85.8g 碳水 / 53.6g 脂肪；
归档菜谱继续可供历史计划读取，整体替换保留归档和人工餐，切周不自动创建空计划。
未操作其他任务保留的 8017 服务；独立浏览器存储恢复不等于实体跨设备测试。

## 云端清理与证据

测试项目 `meal_plan` / `ziusvgtrmarbkmrvnpyq`，运行标识 `7702fe69-5bfd-4564-a691-f67517a50028`。
仅创建本轮 A/B 两个专用账号。清理前按精确 UUID＋邮箱核对，两者 auth.sessions 均为 0。
同一事务再次校验账号及零会话，先删除对应 meal_plans，再删除对应 auth.users。
auth.users、profiles、recipes、recipe_ingredients、meal_plans、meal_plan_items 最终全部为 0，
与运行前计数一致；临时 0600 凭据清单随后删除。

本聊天产物根目录：
`/Users/kenyu/.codex/visualizations/2026/10/09/01a12111-72b3-7130-b4f1-936a8ba03fb9/`

- `retest-d5afb3d-fixed/regression-result.json` 与专项截图：17 项确定性检查。
- `retest-d5afb3d-hosted/result.json` 与 375px 截图：21 项真实云端检查。
- `retest-d5afb3d-hosted/restore-result.json`：6 项重启/故障/历史检查。

截图与临时账号结果未提交 Git，仓库不包含密码、访问令牌或浏览器会话存储。
