(() => {
  "use strict";

  const body = document.body;
  const authGate = document.querySelector("#auth-gate");
  const appShell = document.querySelector(".app-shell");
  const requestForm = document.querySelector("#auth-request-form");
  const verifyForm = document.querySelector("#auth-verify-form");
  const feedback = document.querySelector("#auth-feedback");
  const configNote = document.querySelector("#auth-config-note");
  const emailField = document.querySelector("#email-field");
  const phoneField = document.querySelector("#phone-field");
  const emailInput = document.querySelector("#auth-email");
  const phoneInput = document.querySelector("#auth-phone");
  const countryInput = document.querySelector("#auth-country");
  const tokenInput = document.querySelector("#auth-token");
  const destination = document.querySelector("#auth-destination");
  const sendButton = document.querySelector("#auth-send-button");
  const verifyButton = document.querySelector("#auth-verify-button");
  const resendButton = document.querySelector("#auth-resend-button");
  const countdown = document.querySelector("#auth-countdown");
  const accountMenu = document.querySelector("#account-menu");
  const accountLabel = document.querySelector("#account-label");
  const logoutButton = document.querySelector("#logout-button");

  const injectedConfig = window.MEAL_PREP_SUPABASE || window.MEAL_PREP_SUPABASE_CONFIG || {};
  const config = {
    url: String(injectedConfig.url || "").trim(),
    publishableKey: String(injectedConfig.publishableKey || injectedConfig.anonKey || "").trim(),
  };
  const client = config.url && config.publishableKey && window.supabase?.createClient
    ? window.supabase.createClient(config.url, config.publishableKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } })
    : null;

  const state = { method: "email", step: "request", pending: null, session: null, countdownTimer: null };
  body.classList.add("auth-pending");

  window.MealPrepAuth = {
    client,
    getSession: () => state.session,
    getAccessToken: () => state.session?.access_token || null,
    isAuthenticated: () => Boolean(state.session?.access_token),
  };

  function setFeedback(message = "", tone = "") {
    feedback.textContent = message;
    feedback.dataset.tone = tone;
  }

  function setLoading(button, loading, idleText) {
    button.disabled = loading;
    button.innerHTML = loading ? "处理中…" : `${idleText} <span>→</span>`;
  }

  function normalizePhone() {
    const localNumber = phoneInput.value.replace(/[^0-9]/g, "");
    return `${countryInput.value}${localNumber}`;
  }

  function displayDestination() {
    if (!state.pending) return;
    destination.textContent = `验证码已发送至 ${state.pending.label}`;
  }

  function setMethod(method) {
    state.method = method;
    document.querySelectorAll("[data-auth-method]").forEach((button) => {
      const active = button.dataset.authMethod === method;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    emailField.hidden = method !== "email";
    phoneField.hidden = method !== "phone";
    emailInput.required = method === "email";
    phoneInput.required = method === "phone";
    setFeedback();
  }

  function setStep(step) {
    state.step = step;
    requestForm.hidden = step !== "request";
    verifyForm.hidden = step !== "verify";
    if (step === "verify") { displayDestination(); tokenInput.value = ""; window.setTimeout(() => tokenInput.focus(), 0); }
  }

  function startCountdown() {
    window.clearInterval(state.countdownTimer);
    let seconds = 60;
    resendButton.disabled = true;
    countdown.textContent = `${seconds} 秒后可重新发送`;
    state.countdownTimer = window.setInterval(() => {
      seconds -= 1;
      if (seconds <= 0) { window.clearInterval(state.countdownTimer); countdown.textContent = "可以重新发送验证码"; resendButton.disabled = false; return; }
      countdown.textContent = `${seconds} 秒后可重新发送`;
    }, 1000);
  }

  function authErrorMessage(error) {
    const message = String(error?.message || "");
    const lower = message.toLowerCase();
    if (error?.status === 429 || lower.includes("rate limit") || lower.includes("too many")) return "发送太频繁了，请稍后再试。";
    if (lower.includes("captcha")) return "需要完成 Supabase CAPTCHA 验证后才能发送验证码。";
    if (lower.includes("invalid phone")) return "手机号格式不正确，请检查国家/地区码和号码。";
    if (lower.includes("expired") || lower.includes("invalid token")) return "验证码已过期或不正确，请重新获取一组。";
    if (lower.includes("sms provider") || lower.includes("smtp")) return "验证码服务尚未完成配置，请联系管理员。";
    return message || "操作失败，请稍后再试。";
  }

  function showConfigurationState() {
    const hasSdk = Boolean(window.supabase?.createClient);
    configNote.hidden = false;
    configNote.innerHTML = hasSdk
      ? "<strong>还差一步配置</strong><span>请在部署环境注入 <code>window.MEAL_PREP_SUPABASE</code>，填写 Supabase 项目 URL 和 publishable key。</span>"
      : "<strong>Supabase SDK 未加载</strong><span>请检查网络或将固定版本的 @supabase/supabase-js 加入部署资源。</span>";
    sendButton.disabled = true;
  }

  function showAuthenticated(session) {
    state.session = session;
    body.classList.remove("auth-pending", "auth-required");
    authGate.hidden = true;
    appShell.hidden = false;
    accountMenu.hidden = false;
    const user = session.user || {};
    accountLabel.textContent = user.email || user.phone || "已登录";
  }

  function showUnauthenticated() {
    state.session = null;
    body.classList.remove("auth-pending");
    body.classList.add("auth-required");
    authGate.hidden = false;
    appShell.hidden = true;
    accountMenu.hidden = true;
    if (!client) showConfigurationState();
  }

  async function sendCode() {
    if (!client) { showConfigurationState(); return; }
    const isEmail = state.method === "email";
    const email = emailInput.value.trim();
    const phone = normalizePhone();
    const label = isEmail ? email : phone;
    if (!label || (isEmail && !emailInput.checkValidity())) { setFeedback(isEmail ? "请输入有效的邮箱地址。" : "请输入手机号。", "error"); return; }
    setLoading(sendButton, true, "发送验证码");
    setFeedback();
    try {
      const payload = isEmail
        ? { email, options: { shouldCreateUser: true } }
        : { phone };
      const { error } = await client.auth.signInWithOtp(payload);
      if (error) throw error;
      state.pending = { method: state.method, email, phone, label };
      setStep("verify");
      startCountdown();
      setFeedback("验证码已发送，请检查收件箱或短信。", "success");
    } catch (error) {
      setFeedback(authErrorMessage(error), "error");
    } finally {
      setLoading(sendButton, false, "发送验证码");
    }
  }

  async function verifyCode() {
    if (!client || !state.pending) return;
    const token = tokenInput.value.trim();
    if (!/^\d{6}$/.test(token)) { setFeedback("请输入 6 位数字验证码。", "error"); return; }
    setLoading(verifyButton, true, "验证并进入");
    setFeedback();
    try {
      const payload = state.pending.method === "email"
        ? { email: state.pending.email, token, type: "email" }
        : { phone: state.pending.phone, token, type: "sms" };
      const { data, error } = await client.auth.verifyOtp(payload);
      if (error) throw error;
      if (data?.session) showAuthenticated(data.session);
      else {
        const { data: sessionData } = await client.auth.getSession();
        if (sessionData?.session) showAuthenticated(sessionData.session);
      }
      if (!state.session) setFeedback("验证完成，但还没有拿到有效会话，请重试。", "error");
    } catch (error) {
      setFeedback(authErrorMessage(error), "error");
    } finally {
      setLoading(verifyButton, false, "验证并进入");
    }
  }

  requestForm.addEventListener("submit", (event) => { event.preventDefault(); sendCode(); });
  verifyForm.addEventListener("submit", (event) => { event.preventDefault(); verifyCode(); });
  document.querySelectorAll("[data-auth-method]").forEach((button) => button.addEventListener("click", () => setMethod(button.dataset.authMethod)));
  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "auth-back") { setStep("request"); setFeedback(); }
  });
  resendButton.addEventListener("click", sendCode);
  logoutButton.addEventListener("click", async () => {
    if (!client) return;
    logoutButton.disabled = true;
    const { error } = await client.auth.signOut();
    logoutButton.disabled = false;
    if (error) setFeedback(authErrorMessage(error), "error");
  });

  async function boot() {
    if (!client) { showUnauthenticated(); return; }
    client.auth.onAuthStateChange((_event, session) => {
      if (session) showAuthenticated(session); else showUnauthenticated();
    });
    const { data, error } = await client.auth.getSession();
    if (error) { setFeedback(authErrorMessage(error), "error"); showUnauthenticated(); return; }
    if (data.session) showAuthenticated(data.session); else showUnauthenticated();
  }

  setMethod("email");
  boot();
})();
