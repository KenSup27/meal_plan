# main@d5afb3d 复测报告复核与统一修复方案

## 状态与基线

2026-10-10，先完成代码复核、问题复现和方案制定，随后按用户指示在修复分支实施。
下文复现与 102 项基线测试记录属于修改前状态；修复后的验收见
`2026-10-10-d5afb3d-retest-fixes-validation.md`。

主项目 `/Users/kenyu/Documents/Codex/meal_prep_project` 当前为干净的
`main@d5afb3d7e30bcc3383d7d6c7b3691d4366d1befd`。
从该基线在本聊天工作区建立新分支 `codex/retest-d5afb3d-fixes`，不修改主项目 main。

用户给出的报告路径 `主项目/docs/reviews/main-d5afb3d-e2e-retest-2026-10-10.md` 不存在。
实际读取的同名报告位于：

`/Users/kenyu/.codex/visualizations/2026/10/09/01a11f64-c5fa-7ec0-8189-1ad049678441/main-d5afb3d-e2e-retest-2026-10-10.md`

报告 SHA-256：`3e595b29b57fe206322e4cfdb4829d41b014e1563d2e4ea6224196326bd3f812`。

本轮复核工作区相关源码与主项目 main 无差异。使用隔离的本地 8022 服务，未加载云端配置，
未操作报告中保留的 8017 服务，未创建真实账号或部署数据库改动。

## 逐项判定

| 报告问题 | 当前 main 判定 | 本轮证据 |
| --- | --- | --- |
| P2：登录成功后直接退出，提交按钮卡在处理中 | 确认仍存在 | Chrome 375px：成功登录→退出，不点击模式标签；会话已清空，但按钮 disabled=true、文本为“处理中…” |
| P3：连接失败显示英文 Failed to fetch | 确认仍存在 | Chrome 拒绝菜谱 POST 连接后提示原始英文，编辑器和草稿仍保留 |
| P3：Swagger Authorization 参数未发送 | 确认仍存在 | OpenAPI 3.1.0 无 securitySchemes/operation security；在真实 /docs 填入合成 Bearer 后执行，请求没有 Authorization 头 |

另外核对了 P2 的相邻边界：缺少配置时初始按钮正确禁用，但点击“登录”标签会将按钮错误启用。
提交处理器仍会拦住真实认证请求；这是同一按钮状态管理不统一的问题，应随 P2 一并修复。

认证和业务响应使用明确的合成数据，以复现页面逻辑；Swagger 使用当前 FastAPI 真实生成的文档。
本轮没有把这些隔离浏览器检查描述成真实 Supabase 端到端复测。
原报告中核心持久化与 RLS 已通过的结果保留为该报告结论，不冒充本轮重新执行的云端结果。

## 根因与漏检原因

### 1. 认证表单状态缺少统一出口

`frontend/auth.js:47` 的 setLoading 同时控制文本和禁用状态；`:136` 提交时设为 true。
成功登录后 `:153` 的 finally 因存在 session 而跳过恢复，`:102` 的 showUnauthenticated
又不恢复按钮，因此退出后遗留提交状态。`:52` 的 setMode 无条件 setLoading(false)，
既能绕过卡住，也会覆盖缺配置禁用规则。

现有 `tests/e2e/hosted.cjs:32` 的 login 辅助函数总是先点击“登录”标签，
所以 A→B→A 虽然通过，却自动执行了这个绕过动作，没有覆盖直接重登。

### 2. 连接失败没有进入统一错误类型

`frontend/api.js:13` 直接 await fetch，连接拒绝时抛出的浏览器错误未被包装。
`frontend/app.js:182` 的 reportError 直接采用 error.message，因此显示 Failed to fetch。
HTTP 状态错误已有 ApiError，主动取消也已有 AbortError 处理；问题在传输失败分支。

现有 `tests/e2e/restore.cjs:39` 使用带中文 detail 的 HTTP 503 响应。
该场景能证明 HTTP 错误提示和草稿保留，不能覆盖 fetch 因连接失败而 reject 的路径。

### 3. 认证头被当成普通参数描述

`backend/app/core/auth.py:38`、`backend/app/repositories/dependencies.py:10`，以及
`backend/app/api/routes.py:134` 的 logout、`:152` 的 me 都直接声明 Header。
生成的文档只有普通 authorization 参数，没有 HTTP Bearer 安全方案。
这影响所有使用相关依赖的受保护接口，不只菜谱详情。

OpenAPI 的 Authorization 需要通过安全方案表达；普通 Authorization Header 参数应被忽略。
本轮 Swagger 的实际请求头也验证了该行为。测试直接向 TestClient/fetch 注入头，
无法证明 Swagger 生成请求时真的发送了该头。
缺头 401 只能证明未认证请求被拒绝，不能作为携带 B 凭据越权访问 A 被拒绝的证据。

## 统一修复方案

### 阶段 1：先修认证表单状态（P2）

修改 `frontend/auth.js`，用显式的“是否正在提交”状态统一渲染按钮文本和可用性。
禁用条件为缺 SDK/配置或正在提交，不能由模式标签单独覆盖。
成功登录、正常退出、会话清空、认证失败均结束相应提交状态；同账号 token 刷新不影响业务草稿。
保留提交中的防重复行为，处理初始会话恢复与认证回调重复触发时的按钮一致性。
沿用当前 SDK 退出范围，本次不改 Auth 开关、会话授权或密码认证流程。

验收必须直接执行“登录→退出→填写邮箱密码→再次提交”，中间不点击登录/注册标签或刷新。
同时覆盖注册成功后退出、错误密码后重试、缺配置/缺 SDK 下切换模式及提交中的模式切换。
测试应操作原页面 DOM，不能只测试抽出的状态函数。

### 阶段 2：在请求边界统一网络错误（P3）

修改 `frontend/api.js`，只在 fetch 调用边界捕获传输失败，并包装成有明确类别的 ApiError。
保留 AbortError 原样抛出，以免退出/切账号取消请求被显示成网络故障。
不要把整个业务处理中的任意 TypeError 都当成断网，也不要只匹配 Chrome 的英文文案。

`frontend/app.js` 对读取失败给出中文连接提示；对写入连接中断提示保存结果尚未确认，
应先重新读取确认再重试。保留草稿，不自动重放写请求，不显示保存成功。
保留 HTTP 401/409/422/503 的现有语义；认证 SDK 的同类连接错误使用同一中文提示口径。
如需要共享格式化逻辑，保持为小型纯函数，不引入新的前端框架。

分别覆盖 fetch reject、服务停止/连接拒绝、浏览器离线、HTTP 503，以及账号切换 AbortError。
检查提示、草稿、提交按钮恢复及未出现成功提示，不能用 HTTP 503 代替传输失败测试。

### 阶段 3：统一 Bearer 依赖与 OpenAPI（P3）

在 `backend/app/core/auth.py` 声明 HTTPBearer 安全方案，使用 auto_error=False，
在共享凭据处理层保留当前中文 401 和 WWW-Authenticate 行为；不能把它理解为允许匿名业务访问。
让用户验证、请求仓储、/auth/me 和 /auth/logout 复用该凭据依赖，移除重复的普通 Header 声明，
避免只改一处后另一依赖仍生成无效参数。

SDK/普通前端继续发送 Authorization: Bearer，后端继续调用 Supabase 验证用户，再按用户 JWT 执行 RLS。
注册、登录、刷新和 health 保持公开；缺配置仍明确返回 503。
本应用登录接口使用 JSON，不应为了文档误接成 OAuth2 password form 流程。

补充 OpenAPI 契约测试及实际 Swagger 浏览器测试：Authorize 输入纯 token，发出的请求包含且只包含
一个正确的 Bearer 头；受保护接口带 security 声明，公开接口不要求 Bearer，不能保留普通 authorization 参数。
后端同步补齐缺头/错误 scheme/空 token/失效 token/合法 token 的回归，以及同一 token 传给用户校验和仓储的验证。
如复测跨用户拒绝，必须先确认请求确实携带 B token，再以 404/权限结果及数据未变更判定。

### 阶段 4：修正验收脚本并完整回归

调整 `tests/e2e/hosted.cjs`：模式选择仅用于需要明确切换模式的场景；
增加不切标签的直接重登场景，并在退出后立即断言按钮可用及文本恢复。
调整 `tests/e2e/restore.cjs`：保留 HTTP 503 测试，增加真实传输失败场景。
为 Swagger 增加浏览器请求头断言，不能只依赖 OpenAPI JSON 静态断言。

上述确定性场景先在本地合成认证/业务响应下运行，形成稳定回归；
实现完成后再执行真实邮箱密码业务主流程、A→B→A、刷新/重启恢复和 375px 检查，
真实测试继续使用专用临时账号、精确 UUID＋邮箱核对、退出会话及精确清理流程。

本次三个问题都位于前端状态/错误展示及后端认证声明层，无需数据库迁移、增表或调整 RLS。

## 修改前基线测试与复核阶段边界

本轮重新执行：

```bash
MEAL_PLAN_TEST_DB_URL=meal_plan_auth_test pytest backend/tests supabase/tests -o addopts='' -p no:cacheprovider -q
node --test frontend/tests/*.test.js
```

结果为后端＋真实 PostgreSQL 87 passed、0 skipped；前端 15 passed，共 102 项通过。
保留一条既有 Starlette/httpx TestClient 弃用提示，不属于本次功能缺陷。
这些测试尚未覆盖本次三项失败路径，不能据此把新增问题标记为通过。

最初复核阶段只新增此方案文档，当时尚未实施功能修复、补充正式测试、推送与合并。
验收时逐项记录当前运行证据，不直接把此前其他轮次的通过数量算成本轮结果。

隔离复现结果和截图保存在本聊天产物目录的 `retest-d5afb3d-review/`，包括
result.json、logout-reproduced-375.png、network-reproduced-375.png、swagger-reproduced.png。
产物使用合成值，无真实密码或访问令牌。

## 官方依据

- [Supabase signOut](https://supabase.com/docs/reference/javascript/auth-signout)：退出会触发 SIGNED_OUT（others 范围除外），表单应响应会话变化。
- [OpenAPI 3.1 Parameter Object](https://spec.openapis.org/oas/v3.1.0.html#parameter-object)：Authorization 不应作为普通 Header 参数。
- [FastAPI HTTPBearer](https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer)：安全依赖、OpenAPI scheme 及 auto_error 行为。

已读取 Supabase 技能并核对官方更新日志；本次无需更换 SDK 版本或部署云端变更。
