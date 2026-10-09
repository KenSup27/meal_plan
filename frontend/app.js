const healthBadge = document.querySelector("#health-badge");
const healthText = document.querySelector("#health-text");
const result = document.querySelector("#nutrition-result");

async function checkHealth() {
  try {
    const response = await fetch("/api/v1/health");
    if (!response.ok) throw new Error("health check failed");
    healthBadge.textContent = "运行正常";
    healthBadge.classList.add("success");
    healthText.textContent = "FastAPI 已启动，前端静态页面可正常访问。";
  } catch (error) {
    healthBadge.textContent = "未连接";
    healthBadge.classList.add("danger");
    healthText.textContent = "暂时无法连接 API，请确认服务已启动。";
  }
}

function formPayload(form) {
  const data = new FormData(form);
  return {
    sex: data.get("sex"),
    age: Number(data.get("age")),
    height_cm: Number(data.get("height_cm")),
    weight_kg: Number(data.get("weight_kg")),
    activity_factor: Number(data.get("activity_factor")),
    goal: data.get("goal"),
  };
}

document.querySelector("#nutrition-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  button.textContent = "计算中…";

  try {
    const response = await fetch("/api/v1/nutrition/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload(event.currentTarget)),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "计算失败");
    result.hidden = false;
    result.innerHTML = [
      ["目标热量", `${payload.target_kcal} kcal`],
      ["蛋白质", `${payload.protein_g} g`],
      ["碳水", `${payload.carbs_g} g`],
      ["脂肪", `${payload.fat_g} g`],
    ].map(([label, value]) => `<div><small>${label}</small><strong>${value}</strong></div>`).join("");
  } catch (error) {
    result.hidden = false;
    result.innerHTML = `<p class="error">${error.message}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "计算推荐值";
  }
});

checkHealth();
