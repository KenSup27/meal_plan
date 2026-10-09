# ADR 0004：邮箱＋密码 MVP，暂缓验证码

状态：已接受（2026-10-09）；云端邮箱验证已关闭，真实 Auth/Data API 冒烟通过。

## 最新决定

用户决定先完成 MVP 和端到端验收，再增加邮件/短信验证码，并明确选择
“邮箱＋密码，关闭邮箱验证，保留多用户隔离”。本决定取代 ADR 0003 及旧计划中
“验证码必需、禁止密码”的要求。邮件 OTP、Magic Link、短信和邮件找回密码不在本次交付范围；
SMTP、Resend 发信域名及相关资质不阻塞当前 MVP。

## 数据库边界与安全影响

沿用 `auth.users.id → profiles.id`、`handle_new_user()` 自动建档、幂等补档和现有 RLS。
身份所有权始终取自有效 JWT 的用户 UUID，不取自客户端邮箱、昵称或 metadata。
匿名不能读写业务数据，已登录用户仅能操作自己的数据；食材登录后只读。
不增加密码、验证码或会话业务表，不通过 SQL 插入用户来实现正式注册。
密码存储与校验、注册、登录和令牌由 Supabase Auth 管理。

关闭邮箱验证只是跳过邮箱所有权证明，**不是取消登录或开放 RLS**。
他人可能用不属于自己的邮箱抢先注册；不能把 Auth 中的邮箱确认状态作为已验证邮箱所有权的证据。
MVP 不承诺通过邮箱自助找回密码，也不能以“知道邮箱”为凭据重置密码。
公开发布前应重新评估此风险并完成发信与账号恢复方案。

## 云端配置与复核

`supabase/auth-policy.json` 仅是期望策略，不是已应用的 Supabase 配置。
其中 `otp_login=false`/`magic_link_login=false` 表示产品不提供或调用这些流程，
不代表关闭邮箱验证便会禁用 Supabase 的全部 passwordless API。

在项目 `meal_plan` 的 [Auth Providers](https://supabase.com/dashboard/project/ziusvgtrmarbkmrvnpyq/auth/providers)
中保持 Email 开启，关闭 **Confirm email** 并保存；保留允许新用户注册，Phone 与匿名登录关闭。
以 Dashboard 当前布局为准，可在 Authentication 的 Sign In / Providers 中查找 Email 设置。
不修改现有密码强度、会话时长或刷新令牌等其他保护设置。

2026-10-09 用户在 Dashboard 关闭开关后，公开 `/auth/v1/settings` 已复核：
`mailer_autoconfirm=true`，邮箱开启、允许注册、Phone/匿名关闭。
该开关由用户操作，本工作流仅核验，没有修改其他认证保护设置。
不要通过直接改 Auth 数据表来伪装配置已生效。

## 前后端交接（本数据库工作流不修改前后端）

使用 Supabase 客户端正常接口：

```js
// 注册：关闭 Confirm email 后，应拿到可用会话。
const signup = await supabase.auth.signUp({
  email,
  password,
  options: { data: { display_name } },
})

// 已有账号登录；不得继续调用 signInWithOtp / verifyOtp。
const login = await supabase.auth.signInWithPassword({ email, password })
```

处理错误及空 session，不能仅凭返回 user 就显示登录成功。错误密码或不存在账号给出
统一失败提示。前端不保存明文密码，不展示发码/填码/找回密码入口；注册、登录应分别处理。
后端验证 Bearer Token 后按用户身份访问数据库，不能信任请求中传入的用户 UUID。
不得把 `service_role`/secret key 交给前端；后端用高权限角色访问会绕过 RLS。

已有未确认账号可能需要额外处理，不能假设切换开关会追溯确认全部历史账号；
不要批量更新或删除真实用户。发现历史账号登录受阻时再单独核查。

## 按模块测试与验收边界

先运行配置契约测试，再建档生命周期、权限隔离，最后全库回归，命令见
`supabase/tests/README.md`。本轮不改变数据库 DDL，只更新认证策略与交接说明。
SQL 行为测试覆盖自动建档、补档不覆盖基线、非法 metadata、匿名与跨用户拒绝、
菜谱营养、目标快照、同餐多菜、购物清单及派生视图隔离；事务最终回滚。
保留 OTP 模板仅供未来迭代，不能作为当前认证验收。

2026-10-09 上轮结果：配置契约 4 项、建档 1 组、权限 1 组、业务工作流 1 组
依次通过；最后本地 PostgreSQL 18 全库回归 **34 passed、0 skipped**。
当时 Security Advisor 无告警，没有云端 DDL 变更或创建真实登录账号。

本轮在开关生效后运行 `supabase/tests/hosted/password-smoke.mjs`，通过真实 HTTP 调用
Supabase Auth 和 Data API，共 **13 项检查通过**，不是通过 SQL 插入用户或模拟 JWT：

- 两个随机邮箱＋独立强密码注册立即获得会话；错误密码拒绝，密码登录保持同一 UUID。
- 刷新令牌和 `/auth/v1/user` 身份恢复成功；全局登出后刷新令牌拒绝。
- 自动建档、初始昵称、当前用户基线更新、重复登录不覆盖基线正常。
- 两用户 Profile 隔离、越权更新/计划插入拒绝、无 Token/伪造 Token 拒绝。
- 食材登录后可读不可写；周计划、同餐两条人工餐记录、700 kcal 汇总与目标快照正常。
- 另一用户不能读取已有计划、餐次和营养视图；人工餐不进入采购清单。

两个临时账号已全局登出，SQL 复核会话为 0 后，使用 UUID＋精确邮箱＋本轮标记约束清理。
最终 Auth 用户/Profile/菜谱/周计划/餐次均为 0，保留原有 34 条食材。
密码与令牌只在测试进程内存中，不打印或持久化。
最后本地全库回归再次 **34 passed、0 skipped**。

本轮 Security Advisor 出现 `auth_leaked_password_protection` 警告：泄露密码检测未开启。
未自动改变该保护或开通付费能力；上线前按
[官方说明](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection)
评估并配置。此检查结果取代此前“无告警”的现状描述。

以上不包含浏览器页面、FastAPI 的登录集成或菜谱原子写入的 HTTP 验收。
菜谱明细和非空约束的跨表事务仍由现有 SQL 行为测试覆盖，不能把人工餐 API 测试
当成完整菜谱/购物清单 HTTP 闭环。应用仍需以下端到端测试：

1. 通过页面完成注册、登出及重新登录，确认 UI 错误提示与会话状态正确。
2. 通过应用后端验证 JWT，原子保存菜谱及明细，完成排餐与非空采购汇总的整条链路。
3. 浏览器刷新页面恢复会话；登出后客户端清理会话，无 Token 的业务请求被拒绝。

数据库 SQL 测试不代替真实 Auth/API/浏览器端到端测试；登出也不意味着旧 Access Token
立即失效。未完成上述验收前不宣称整个应用端到端通过。

依据：[Supabase 密码认证](https://supabase.com/docs/guides/auth/passwords)、
[signUp](https://supabase.com/docs/reference/javascript/auth-signup)、
[signInWithPassword](https://supabase.com/docs/reference/javascript/auth-signinwithpassword)。
