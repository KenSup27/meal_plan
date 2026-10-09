# ADR 0003：邮箱验证码注册登录与数据库职责

状态：已被 [ADR 0004](0004-email-password-mvp.md) 取代（2026-10-09）。以下保留此前方案及测试记录；邮箱 OTP 与 SMTP 不再是当前 MVP 的发布前提。

## 需求来源与最新范围

本工作树的 `PLAN.md` 尚未同步 Auth 更新。本次依据
`/Users/kenyu/Documents/Codex/meal_plan-database/PLAN.md` 第 0.6、12.1 节，
并以用户最新指示“先不要短信验证码登录，先用邮箱吧”覆盖其中的短信硬性要求。
本阶段仅启用邮箱 OTP；手机号登录、短信服务商和 Send SMS Hook 暂缓。

## 数据库实现

继续采用 `auth.users.id → profiles.id` 的一对一关联，不增加密码、验证码、
手机号或登录会话业务表。Supabase Auth 负责 OTP 生成、发送、验证、会话和刷新令牌。
邮箱只存于 Auth，不能把用户输入的邮箱用作业务所有权判断。

`handle_new_user()` 在 Auth 创建账号时自动建档。注意这可能发生在 OTP 验证前；
Profile 的存在不代表已验证邮箱，也不授予匿名访问权限。客户端只有完成 OTP 验证
取得有效 Access Token 后才能访问个人业务数据。

可选的 `raw_user_meta_data.display_name` 仅作为初始展示昵称，去除首尾空白；
空值、JSON 非字符串忽略。metadata 中的 role、目标热量等不会影响权限或营养基线。
昵称之后通过 `profiles` 编辑；重复登录或 Auth metadata 修改不覆盖业务 Profile。

Schema 和增量 `supabase/auth.sql` 都包含幂等补档，修复触发器部署前已有的账号，
且不覆盖已有昵称和营养基线。函数固定空 `search_path`、限定对象 schema，
撤销 `PUBLIC/anon/authenticated` 执行权限，仅供内部触发器调用。

现有 RLS 保持用户主键所有权：匿名角色不能读写业务表/视图；已登录用户只能操作
自己的 Profile、菜谱和计划；食材登录后只读。所有聚合视图使用 `security_invoker`。

云端测试发现 Supabase 默认 ACL 会保留本地干净库没有的宽权限。因此在 Schema 和
增量 SQL 中先撤销六张业务表及五个视图对 `PUBLIC/anon/authenticated` 的权限，
再仅授予所需 SELECT/INSERT/UPDATE/DELETE；食材及视图只授予 SELECT。
尤其禁止客户端拥有不受 RLS 保护的 TRUNCATE 权限。保留服务端角色权限。

## 配置规范与云端现状

`supabase/auth-policy.json` 是目标策略说明，不是 Supabase CLI 配置，也不会自动写入云端。
目标：6 位邮箱 OTP、10 分钟有效、至少 60 秒重发间隔；JWT 1 小时；开启刷新令牌轮换。
这些时长属于本项目的初始策略，须在 Dashboard/Management API 配置后核验，
不要把 Supabase 默认值当成已经应用的值。

2026-10-09 通过项目公开 `/auth/v1/settings` 只读核验：邮箱认证启用、允许注册、
邮箱验证未自动跳过、手机认证关闭、匿名登录关闭。该公开接口不能证明 SMTP 配置、
模板、OTP 有效期或全局小时配额，以上值的云端状态仍待核验。

建议邮件使用 Resend，先验证发信域名，再在 Supabase Authentication 的 SMTP 配置中
填写 host `smtp.resend.com`、port `465`、user `resend`，SMTP password 为 Resend API key，
以及该域名的发件地址。密钥仅填 Dashboard 或受控本地环境，不提交到 Git。
配置全局邮件小时额度时，应同时符合邮件服务商套餐；本次未购买服务或设置付费额度。

将 `supabase/templates/email-otp.html` 用于 **Magic Link** 和 **Confirm signup** 邮件模板，
保留 `{{ .Token }}`；仅调用 `signInWithOtp` 而不修改模板可能仍发送 Magic Link。
上线站点 URL、跳转白名单和 SMTP 发信域名由部署环境确定。

## 前后端交接

发送邮箱 OTP：`signInWithOtp({ email, options: { shouldCreateUser: true } })`。
首次请求创建账号，已有账号走登录；验证使用 `verifyOtp({ email, token, type: 'email' })`。
前端负责会话恢复、刷新与登出，FastAPI 负责验证 Bearer Token，然后传递用户身份访问数据库。
不得以 SQL 插入 Auth 用户作为实际注册接口；测试插入仅验证触发器和 RLS 的数据库契约。

客户端角色不能直接调用触发器函数。服务端若使用 `service_role`，会绕过 RLS；
业务访问优先使用用户 Access Token，不能将服务端密钥发送给浏览器。
登出撤销刷新会话不保证已经签发的 Access Token 立即失效，应遵守 Supabase Auth 的会话语义。

## 测试与实际发送验收边界

可重复运行的 PostgreSQL 测试见 `supabase/tests/README.md`：先建档模块，再权限模块，
最后全库回归；每项均使用事务、生成测试 UUID，最终强制检查延迟约束并回滚。
数据库测试覆盖初始昵称、非法 metadata、补档幂等性、匿名拒绝、跨用户拒绝、
营养计算、目标快照、同餐多菜、购物清单及视图隔离。

数据库测试不会发送真实邮件，不能据此宣称验证码生成/失效/重放、真实 JWT 签名验证、
刷新令牌和真实登出已经端到端通过。SMTP 和收件测试账号准备好后，需进一步验收：

1. 新邮箱收到 6 位码，验证后能查询自己的 Profile，首次基线为空。
2. 已有邮箱再次登录不产生新 Profile、不覆盖基线。
3. 错码、过期码、已经使用的码被拒绝；60 秒内重发受限。
4. 刷新页面保持登录；登出后前端停止使用旧会话，业务 API 拒绝无 Token 请求。

2026-10-09 验证记录：本地 PostgreSQL 18 上 33 项测试全部通过（27 项原有契约检查、
3 项 Auth 配置/一致性检查、3 组真实数据库行为测试）。建档、权限和全库回归按顺序通过后，
已通过 Supabase MCP 同步 `auth.sql`，并在云端运行同三组事务测试，均通过并回滚。
最终 Auth 用户/Profile/菜谱/计划数均为 0，食材 34 条；Security Advisor 无告警。
Performance Advisor 仅有 3 条新库索引尚未使用的信息级提示，保留用于正式业务查询。
以上结果仅表示数据库部分验收，不表示实际验证码邮件投递验收完成。

官方依据：[用户建档](https://supabase.com/docs/guides/auth/managing-user-data)、
[邮箱 OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless)、
[Resend SMTP](https://resend.com/docs/send-with-smtp)、
[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)。
