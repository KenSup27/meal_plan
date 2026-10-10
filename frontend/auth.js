(() => {
  "use strict";

  const body = document.body;
  const authGate = document.querySelector("#auth-gate");
  const appShell = document.querySelector(".app-shell");
  const authForm = document.querySelector("#auth-form");
  const feedback = document.querySelector("#auth-feedback");
  const configNote = document.querySelector("#auth-config-note");
  const authTitle = document.querySelector("#auth-title");
  const emailInput = document.querySelector("#auth-email");
  const passwordInput = document.querySelector("#auth-password");
  const passwordConfirmField = document.querySelector("#password-confirm-field");
  const passwordConfirmInput = document.querySelector("#auth-password-confirm");
  const togglePassword = document.querySelector("#toggle-password");
  const submitButton = document.querySelector("#auth-submit-button");
  const accountMenu = document.querySelector("#account-menu");
  const accountLabel = document.querySelector("#account-label");
  const logoutButton = document.querySelector("#logout-button");

  const injectedConfig = window.MEAL_PREP_SUPABASE || window.MEAL_PREP_SUPABASE_CONFIG || {};
  const config = {
    url: String(injectedConfig.url || "").trim(),
    publishableKey: String(injectedConfig.publishableKey || injectedConfig.anonKey || "").trim(),
  };
  const client = config.url && config.publishableKey && window.supabase?.createClient
    ? window.supabase.createClient(config.url, config.publishableKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
    : null;

  const state = { mode: "login", session: null, passwordVisible: false, submitting: false };
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

  function renderSubmission() {
    submitButton.disabled = !client || state.submitting;
    submitButton.innerHTML = state.submitting ? "处理中…" : `${state.mode === "signup" ? "创建账号" : "登录"} <span>→</span>`;
    document.querySelectorAll("[data-auth-mode]").forEach(button => { button.disabled = state.submitting; });
  }

  function setLoading(loading) {
    state.submitting = loading;
    renderSubmission();
  }

  function setMode(mode) {
    if (state.submitting) return;
    state.mode = mode;
    const isSignup = mode === "signup";
    document.querySelectorAll("[data-auth-mode]").forEach((button) => {
      const active = button.dataset.authMode === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    authTitle.textContent = isSignup ? "创建账号" : "登录 / 注册";
    passwordConfirmField.hidden = !isSignup;
    passwordConfirmInput.required = isSignup;
    passwordInput.autocomplete = isSignup ? "new-password" : "current-password";
    setFeedback();
    renderSubmission();
  }

  function authErrorMessage(error) {
    if (error?.name === "AuthRetryableFetchError") return window.MealPrepApi.networkErrorMessage();
    const message = String(error?.message || "");
    const lower = message.toLowerCase();
    if (lower.includes("invalid login") || lower.includes("invalid credentials")) return "邮箱或密码不正确，请检查后重试。";
    if (lower.includes("already registered") || lower.includes("already exists")) return "该邮箱已注册，请直接登录。";
    if (lower.includes("password") && (lower.includes("short") || lower.includes("weak") || lower.includes("least"))) return "密码强度不足，请使用至少 8 位密码。";
    if (lower.includes("email") && (lower.includes("invalid") || lower.includes("valid"))) return "请输入有效的邮箱地址。";
    if (lower.includes("email not confirmed") || lower.includes("confirm your email")) return "当前 Supabase 仍要求邮箱验证，请在 Auth 设置中关闭 Email Confirmations。";
    if (error?.status === 429 || lower.includes("rate limit") || lower.includes("too many")) return "操作太频繁了，请稍后再试。";
    return message || "操作失败，请稍后再试。";
  }

  function showConfigurationState() {
    const hasSdk = Boolean(window.supabase?.createClient);
    configNote.hidden = false;
    configNote.innerHTML = hasSdk
      ? "<strong>还差一步配置</strong><span>请在部署环境注入 <code>window.MEAL_PREP_SUPABASE</code>，填写 Supabase 项目 URL 和 publishable key。</span>"
      : "<strong>Supabase SDK 未加载</strong><span>请检查网络或将固定版本的 @supabase/supabase-js 加入部署资源。</span>";
    renderSubmission();
  }

  function showAuthenticated(session) {
    state.session = session;
    setLoading(false);
    passwordInput.value = "";
    passwordConfirmInput.value = "";
    body.classList.remove("auth-pending", "auth-required");
    authGate.hidden = true;
    appShell.hidden = false;
    accountMenu.hidden = false;
    const user = session.user || {};
    accountLabel.textContent = user.email || "已登录";
    window.dispatchEvent(new CustomEvent("mealprep:authchange"));
  }

  function showUnauthenticated(resetSubmission = true) {
    state.session = null;
    if (resetSubmission) setLoading(false);
    body.classList.remove("auth-pending");
    body.classList.add("auth-required");
    authGate.hidden = false;
    appShell.hidden = true;
    accountMenu.hidden = true;
    window.dispatchEvent(new CustomEvent("mealprep:authchange"));
    if (!client) showConfigurationState();
  }

  async function submitAuth() {
    if (state.submitting) return;
    if (!client) {
      showConfigurationState();
      return;
    }
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!emailInput.checkValidity()) {
      setFeedback("请输入有效的邮箱地址。", "error");
      emailInput.focus();
      return;
    }
    if (password.length < 8) {
      setFeedback("密码至少 8 位，请换一个更强的密码。", "error");
      passwordInput.focus();
      return;
    }
    if (state.mode === "signup" && password !== passwordConfirmInput.value) {
      setFeedback("两次输入的密码不一致。", "error");
      passwordConfirmInput.focus();
      return;
    }

    setLoading(true);
    setFeedback();
    const mode = state.mode;
    try {
      const result = mode === "signup"
        ? await client.auth.signUp({ email, password })
        : await client.auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      if (result.data?.session) {
        showAuthenticated(result.data.session);
      } else if (mode === "signup") {
        setLoading(false);
        setMode("login");
        setFeedback("注册成功，请使用邮箱和密码登录。", "success");
      } else {
        setFeedback("登录成功，但还没有拿到有效会话，请重试。", "error");
      }
    } catch (error) {
      setFeedback(authErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }

  function togglePasswordVisibility() {
    state.passwordVisible = !state.passwordVisible;
    passwordInput.type = state.passwordVisible ? "text" : "password";
    togglePassword.textContent = state.passwordVisible ? "隐藏" : "显示";
    togglePassword.setAttribute("aria-label", state.passwordVisible ? "隐藏密码" : "显示密码");
  }

  authForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuth();
  });
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.authMode));
  });
  togglePassword.addEventListener("click", togglePasswordVisibility);
  logoutButton.addEventListener("click", async () => {
    if (!client) return;
    logoutButton.disabled = true;
    try {
      const { error } = await client.auth.signOut();
      if (error) throw error;
    } catch (error) {
      setFeedback(authErrorMessage(error), "error");
    } finally {
      logoutButton.disabled = false;
    }
  });

  async function boot() {
    if (!client) {
      showUnauthenticated();
      return;
    }
    let authRevision = 0;
    client.auth.onAuthStateChange((event, session) => {
      authRevision += 1;
      if (session) showAuthenticated(session);
      else showUnauthenticated(event !== "INITIAL_SESSION");
    });
    const initialRevision = authRevision;
    try {
      const { data, error } = await client.auth.getSession();
      if (initialRevision !== authRevision) return;
      if (error) throw error;
      if (data.session) showAuthenticated(data.session);
      else showUnauthenticated(false);
    } catch (error) {
      if (initialRevision !== authRevision) return;
      setFeedback(authErrorMessage(error), "error");
      showUnauthenticated(false);
    }
  }

  setMode("login");
  boot();
})();
