(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MealPrepApi = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; }
  }
  function createClient(getToken, fetcher = fetch) {
    return async function request(method, path, body, signal) {
      const token = getToken();
      if (!token) throw new ApiError(401, "请先登录");
      const response = await fetcher(`/api/v1${path}`, {
        method, signal, headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (response.status === 204) return null;
      let payload;
      try { payload = await response.json(); } catch (_) { throw new ApiError(response.status, "服务响应异常，请稍后重试"); }
      if (!response.ok) throw new ApiError(response.status, typeof payload.detail === "string" ? payload.detail : "保存内容无效，请检查后重试");
      return payload;
    };
  }
  function createSessionScope() {
    let userId = null, generation = 0, controller = new AbortController();
    return {
      setUser(nextId) {
        if (userId === nextId) return false;
        controller.abort(); controller = new AbortController(); userId = nextId; generation += 1;
        return true;
      },
      capture() { return { userId, generation, signal: controller.signal }; },
      assert(context) {
        if (!context.userId || context.userId !== userId || context.generation !== generation) {
          const error = new Error("会话已切换"); error.name = "AbortError"; throw error;
        }
      },
    };
  }
  return { ApiError, createClient, createSessionScope };
});
