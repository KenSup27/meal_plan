(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MealPrepApi = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  class ApiError extends Error {
    constructor(status, message, kind = "http") { super(message); this.name = "ApiError"; this.status = status; this.kind = kind; }
  }
  function networkErrorMessage(method = "GET") {
    return ["GET", "HEAD"].includes(method.toUpperCase())
      ? "无法连接服务，请检查网络后重新加载。"
      : "连接中断，保存结果尚未确认。请先重新加载确认，再决定是否重试；当前草稿已保留。";
  }
  function createClient(getToken, fetcher = fetch) {
    return async function request(method, path, body, signal) {
      const token = getToken();
      if (!token) throw new ApiError(401, "请先登录");
      const options = {
        method, signal, headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      };
      let response;
      try { response = await fetcher(`/api/v1${path}`, options); }
      catch (error) {
        if (error.name === "AbortError") throw error;
        throw new ApiError(0, networkErrorMessage(method), "network");
      }
      if (response.status === 204) return null;
      let payload;
      try { payload = await response.json(); } catch (error) {
        if (error.name === "AbortError") throw error;
        throw new ApiError(response.status, "服务响应异常，请稍后重试");
      }
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
  return { ApiError, networkErrorMessage, createClient, createSessionScope };
});
