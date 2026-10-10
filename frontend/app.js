(() => {
  "use strict";

  const core = window.MealPrepCore;
  const WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const CATEGORY_LABELS = { meat: "肉禽", seafood: "水产", dairy: "蛋奶", vegetable: "蔬菜", fruit: "水果", carb: "碳水", seasoning: "调料", other: "其他" };

  let catalog = [];
  const defaultBaseline = { target_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };
  const dateFormatter = new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" });
  const longDateFormatter = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" });
  const dom = { toast: document.querySelector("#toast"), healthDot: document.querySelector("#health-dot"), healthText: document.querySelector("#health-text"), nutritionForm: document.querySelector("#nutrition-form"), nutritionResult: document.querySelector("#nutrition-result"), savedBaseline: document.querySelector("#saved-baseline"), recipeEditor: document.querySelector("#recipe-editor"), recipeList: document.querySelector("#recipe-list"), weekStart: document.querySelector("#week-start"), planTarget: document.querySelector("#plan-target"), plannerGrid: document.querySelector("#planner-grid"), mealEditor: document.querySelector("#meal-editor"), plannerSummary: document.querySelector("#planner-summary"), shoppingWeek: document.querySelector("#shopping-week"), shoppingCount: document.querySelector("#shopping-count"), shoppingContent: document.querySelector("#shopping-content") };

  let state = freshState();
  const scope = window.MealPrepApi.createSessionScope();
  const api = window.MealPrepApi.createClient(() => window.MealPrepAuth?.getAccessToken());
  let toastTimer;
  let pendingNutrition = null;
  let weekLoadVersion = 0;

  function mondayOf(date = new Date()) { const value = new Date(date); value.setHours(12, 0, 0, 0); const day = value.getDay() || 7; value.setDate(value.getDate() - day + 1); return isoDate(value); }
  function isoDate(date) { const value = new Date(date); return [value.getFullYear(), String(value.getMonth() + 1).padStart(2, "0"), String(value.getDate()).padStart(2, "0")].join("-"); }
  function addDays(dateString, amount) { const value = new Date(`${dateString}T12:00:00`); value.setDate(value.getDate() + amount); return isoDate(value); }
  function freshState() { return { view: "baseline", baseline: null, recipes: [], historicalRecipes: [], plans: {}, summaries: {}, shopping: {}, weekStart: mondayOf(), recipeEditingId: null, mealEditingId: null, pendingMeal: null, ready: false, busy: false }; }

  function currentPlan() { return state.plans[state.weekStart] || core.createPlan(state.weekStart, state.baseline || defaultBaseline); }
  function esc(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }
  function shortNumber(value) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 1 }); }
  function recipeNutrition(recipe) { return recipe.nutrition || core.calculateRecipeNutrition(recipe.ingredients, catalog); }
  function getRecipe(id) { return [...state.recipes, ...state.historicalRecipes].find(recipe => String(recipe.id) === String(id)); }
  function showToast(message, tone = "success") { dom.toast.textContent = message; dom.toast.dataset.tone = tone; dom.toast.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => dom.toast.classList.remove("show"), 2600); }

  function setView(view) { state.view = view; state.recipeEditingId = null; state.mealEditingId = null;  render(); window.scrollTo({ top: 0, behavior: "smooth" }); }
  function render() { renderBaselineStatus(); renderRecipes(); renderPlanner(); renderShopping(); document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== `${state.view}-view`; section.classList.toggle("active", !section.hidden); }); document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === state.view)); }

  function renderBaselineStatus() { if (!state.baseline) { dom.savedBaseline.innerHTML = `<div class="empty-state compact-empty"><span class="empty-icon">✦</span><div><strong>还没有确认营养基线</strong><p>完成上方计算后，你的每日目标会出现在这里。</p></div></div>`; return; } const target = state.baseline; dom.savedBaseline.innerHTML = `<div class="baseline-summary"><div class="calorie-focus"><span class="metric-label">每日目标</span><strong>${shortNumber(target.target_kcal)}</strong><span>kcal</span><div class="target-bar"><i style="width:${Math.min(100, (target.target_kcal / 2400) * 100)}%"></i></div></div><div class="macro-mini"><span class="metric-label">蛋白质</span><strong>${shortNumber(target.protein_g)}<small>g</small></strong></div><div class="macro-mini"><span class="metric-label">碳水</span><strong>${shortNumber(target.carbs_g)}<small>g</small></strong></div><div class="macro-mini"><span class="metric-label">脂肪</span><strong>${shortNumber(target.fat_g)}<small>g</small></strong></div></div><div class="baseline-foot"><span>基于 TDEE ${shortNumber(target.tdee_kcal)} kcal · 可随时重新计算</span><button class="text-button" data-action="edit-baseline" type="button">调整目标 <span>→</span></button></div>`; }
  function targetField(name, label, value, unit) { return `<label>${label}<div class="input-with-unit"><input name="${name}" type="number" min="0" step="0.1" value="${value ?? ""}" required /><span>${unit}</span></div></label>`; }
  function renderNutritionResult(payload) { pendingNutrition = core.normalizeNutritionResponse(payload); const normalized = pendingNutrition; dom.nutritionResult.hidden = false; dom.nutritionResult.innerHTML = `<div class="result-intro"><div><span class="result-kicker">YOUR STARTING POINT</span><strong>推荐目标已生成</strong></div><span class="result-check">✓ 计算完成</span></div><div class="result-calculated"><div><span>BMR 基础代谢</span><strong>${shortNumber(normalized.bmr_kcal)} <small>kcal</small></strong></div><div><span>TDEE 日常消耗</span><strong>${shortNumber(normalized.tdee_kcal)} <small>kcal</small></strong></div></div><p class="edit-hint">可以根据你的真实状态微调，确认后会用于周计划。</p><form id="baseline-confirm-form" class="target-edit-grid">${targetField("target_kcal", "每日热量", normalized.target_kcal, "kcal")}${targetField("protein_g", "蛋白质", normalized.protein_g, "g")}${targetField("carbs_g", "碳水", normalized.carbs_g, "g")}${targetField("fat_g", "脂肪", normalized.fat_g, "g")}<button class="primary-button full-span" type="submit">确认并保存基线 <span>→</span></button></form>`; }

  function renderRecipes() { if (state.recipeEditingId) renderRecipeEditor(); else dom.recipeEditor.hidden = true; if (!state.recipes.length) { dom.recipeList.innerHTML = `<div class="empty-state"><span class="empty-icon">＋</span><strong>还没有菜谱</strong><p>从一盘菜开始，把你的工作日午餐安排起来。</p></div>`; return; } dom.recipeList.innerHTML = `<div class="section-meta"><span>${state.recipes.length} 道私房菜</span><span>每道都是一盘的份量</span></div><div class="recipe-cards">${state.recipes.map(recipeCard).join("")}</div>`; }
  function recipeCard(recipe) { const nutrition = recipeNutrition(recipe); const tags = recipe.ingredients.slice(0, 3).map((item) => { const ingredient = catalog.find((candidate) => String(candidate.id) === String(item.ingredient_id)); return ingredient ? `<span>${esc(ingredient.name)} ${shortNumber(item.raw_weight_g)}g</span>` : ""; }).join(""); return `<article class="recipe-card"><div class="recipe-visual ${esc(recipe.id.slice(-1))}"><span>${esc(recipe.name.slice(0, 1))}</span><div class="recipe-orbit"></div></div><div class="recipe-card-body"><div class="card-topline"><span class="recipe-label">ONE PLATE</span><div class="card-actions"><button class="icon-button subtle" data-action="edit-recipe" data-id="${esc(recipe.id)}" type="button" aria-label="编辑">✎</button><button class="icon-button subtle danger-icon" data-action="delete-recipe" data-id="${esc(recipe.id)}" type="button" aria-label="删除">×</button></div></div><h3>${esc(recipe.name)}</h3><p>${esc(recipe.description || "一盘按生重计算的工作日菜谱")}</p><div class="ingredient-tags">${tags}</div><div class="recipe-nutrition"><div><strong>${shortNumber(nutrition.kcal)}</strong><span>kcal</span></div><div><strong>${shortNumber(nutrition.protein_g)}g</strong><span>蛋白质</span></div><div><strong>${shortNumber(nutrition.carbs_g)}g</strong><span>碳水</span></div><div><strong>${shortNumber(nutrition.fat_g)}g</strong><span>脂肪</span></div></div><button class="recipe-cta" data-action="add-to-plan" data-id="${esc(recipe.id)}" type="button">加入本周计划 <span>↗</span></button></div></article>`; }
  function renderRecipeEditor() { const recipe = state.recipeEditingId === "new" ? { name: "", description: "", ingredients: [{ ingredient_id: catalog[0]?.id, raw_weight_g: 150 }] } : getRecipe(state.recipeEditingId); if (!recipe) return; dom.recipeEditor.hidden = false; const nutrition = recipeNutrition({ ...recipe, ingredients: recipe.ingredients || [] }); dom.recipeEditor.innerHTML = `<div class="editor-heading"><div><span class="eyebrow">RECIPE WORKSHOP</span><h2>${state.recipeEditingId === "new" ? "做一盘新菜" : "编辑这道菜"}</h2></div><button class="icon-button" data-action="close-editor" type="button" aria-label="关闭">×</button></div><form id="recipe-form"><div class="form-grid recipe-form-grid"><label class="full-span">菜谱名称<input name="name" value="${esc(recipe.name)}" placeholder="例如：照烧鸡腿饭" required /></label><label class="full-span">一句描述<input name="description" value="${esc(recipe.description)}" placeholder="给未来的自己留一句提示" /></label></div><div class="ingredient-heading"><div><strong>这盘用了什么</strong><span>所有重量都按生重</span></div><button class="outline-button small-button" data-action="add-ingredient" type="button">＋ 添加食材</button></div><div id="ingredient-rows">${(recipe.ingredients || []).map((item, index) => ingredientRow(item, index)).join("")}</div><div class="editor-footer"><div class="live-nutrition"><span>实时营养估算</span><strong>${shortNumber(nutrition.kcal)} <small>kcal</small></strong><em>${shortNumber(nutrition.protein_g)}g 蛋白质 · ${shortNumber(nutrition.carbs_g)}g 碳水 · ${shortNumber(nutrition.fat_g)}g 脂肪</em></div><button class="primary-button" type="submit">保存菜谱 <span>→</span></button></div></form>`; }
  function ingredientRow(item, index) { return `<div class="ingredient-row"><span class="row-number">${String(index + 1).padStart(2, "0")}</span><select name="ingredient_id" aria-label="食材">${catalog.map((ingredient) => `<option value="${ingredient.id}" ${String(item.ingredient_id) === String(ingredient.id) ? "selected" : ""}>${ingredient.name} · ${CATEGORY_LABELS[ingredient.category] || ingredient.category}</option>`).join("")}</select><div class="input-with-unit"><input name="raw_weight_g" type="number" min="0" step="1" value="${item.raw_weight_g || ""}" aria-label="生重" required /><span>g</span></div><button class="icon-button subtle danger-icon remove-ingredient" type="button" aria-label="删除食材">×</button></div>`; }

  function renderPlanner() { dom.weekStart.value = state.weekStart; const plan = currentPlan(); const target = plan.target || state.baseline || defaultBaseline; dom.planTarget.innerHTML = `<div class="target-copy"><span class="eyebrow">THIS WEEK'S NORTH STAR</span><strong>每天 ${shortNumber(target.target_kcal)} kcal</strong><span>午餐和晚餐由你安排，早餐暂不计入缺口判断</span></div><div class="target-stats"><div><strong>${plan.items.length}</strong><span>已排餐项</span></div><div><strong>${new Set(plan.items.map((item) => item.planned_date)).size}<small>/7</small></strong><span>覆盖天数</span></div></div>`; dom.plannerGrid.innerHTML = Array.from({ length: 7 }, (_, index) => plannerDay(addDays(state.weekStart, index), index, plan)).join(""); if (state.mealEditingId) renderMealEditor(); else dom.mealEditor.hidden = true; renderPlannerSummary(plan, target); }
  function plannerDay(date, index, plan) { const isToday = date === isoDate(new Date()); const dayItems = plan.items.filter((item) => item.planned_date === date); const summary = state.summaries[state.weekStart]?.days[date] || core.aggregatePlanNutrition({ ...plan, items: dayItems }, [...state.recipes, ...state.historicalRecipes], catalog).total; return `<article class="planner-day ${isToday ? "today" : ""}"><div class="day-heading"><div><span>${WEEKDAY_LABELS[index]}</span><strong>${date.slice(8)}<small>${dateFormatter.format(new Date(`${date}T12:00:00`)).split(" ").pop() || ""}</small></strong></div>${isToday ? '<span class="today-chip">今天</span>' : ""}</div><div class="meal-slot"><div class="slot-label"><span>午餐</span><button class="add-meal" data-action="add-meal" data-date="${date}" data-meal="lunch" type="button">＋</button></div>${mealItems(dayItems, "lunch", date)}</div><div class="meal-slot"><div class="slot-label"><span>晚餐</span><button class="add-meal" data-action="add-meal" data-date="${date}" data-meal="dinner" type="button">＋</button></div>${mealItems(dayItems, "dinner", date)}</div><div class="day-total">${dayItems.length ? `<strong>${shortNumber(summary.kcal)} <small>kcal</small></strong><span>${shortNumber(summary.protein_g)}g 蛋白质</span>` : `<span class="empty-day">还没安排 · 点击 ＋ 添加</span>`}</div></article>`; }
  function mealItems(items, mealType, date) { const matches = items.filter((item) => item.meal_type === mealType); if (!matches.length) return `<button class="empty-meal" data-action="add-meal" data-date="${date}" data-meal="${mealType}" type="button">添加一盘菜 <span>＋</span></button>`; return matches.map((item) => { const recipe = getRecipe(item.recipe_id); return `<div class="planned-meal"><div class="meal-dot ${mealType}"></div><div class="planned-meal-copy"><strong>${esc(recipe?.name || "已删除菜谱")}</strong><span>${item.quantity} 盘 · ${shortNumber(recipe ? recipeNutrition(recipe).kcal * item.quantity : 0)} kcal</span></div><button class="meal-remove" data-action="remove-meal" data-id="${esc(item.id)}" type="button" aria-label="移除">×</button></div>`; }).join(""); }
  function renderMealEditor() { const plan = currentPlan(); const item = plan.items.find((candidate) => candidate.id === state.mealEditingId); const isNew = state.mealEditingId === "new"; const date = state.pendingMeal?.date || item?.planned_date || state.weekStart; const meal = state.pendingMeal?.meal || item?.meal_type || "lunch"; dom.mealEditor.hidden = false; dom.mealEditor.innerHTML = `<div class="editor-heading"><div><span class="eyebrow">ADD TO THE WEEK</span><h2>${isNew ? "安排一顿饭" : "调整这顿饭"}</h2></div><button class="icon-button" data-action="close-editor" type="button" aria-label="关闭">×</button></div><form id="meal-form" class="meal-form"><label>日期<select name="planned_date">${Array.from({ length: 7 }, (_, index) => { const value = addDays(state.weekStart, index); return `<option value="${value}" ${value === date ? "selected" : ""}>${longDateFormatter.format(new Date(`${value}T12:00:00`))}</option>`; }).join("")}</select></label><label>餐次<select name="meal_type"><option value="lunch" ${meal === "lunch" ? "selected" : ""}>午餐</option><option value="dinner" ${meal === "dinner" ? "selected" : ""}>晚餐</option></select></label><label class="recipe-select">选择菜谱<select name="recipe_id">${state.recipes.map((recipe) => `<option value="${recipe.id}" ${recipe.id === (state.pendingMeal?.recipe_id || item?.recipe_id) ? "selected" : ""}>${esc(recipe.name)}</option>`).join("")}</select></label><label>吃几盘<div class="input-with-unit"><input name="quantity" type="number" min="0.5" step="0.5" value="${item?.quantity || 1}" required /><span>盘</span></div></label><button class="primary-button full-span" type="submit">${isNew ? "加入计划" : "保存调整"} <span>→</span></button></form>`; }
  function renderPlannerSummary(plan, target) { const summary = state.summaries[state.weekStart] || core.aggregatePlanNutrition(plan, [...state.recipes, ...state.historicalRecipes], catalog); const days = new Set(plan.items.map(item => item.planned_date)).size; const targetWeek = target.target_kcal * 7; const kcalPercent = targetWeek ? Math.min(100, Math.round((summary.total.kcal / targetWeek) * 100)) : 0; dom.plannerSummary.innerHTML = `<div class="summary-overview"><div class="summary-score"><span>本周已规划</span><strong>${shortNumber(summary.total.kcal)}<small>kcal</small></strong><div class="progress-line"><i style="width:${kcalPercent}%"></i></div><em>按每日目标的午晚餐部分估算</em></div><div class="summary-stats"><div><strong>${shortNumber(core.plateCount(plan))}</strong><span>盘菜</span></div><div><strong>${days}<small>/7</small></strong><span>覆盖天数</span></div><div><strong>${shortNumber(summary.total.protein_g)}<small>g</small></strong><span>蛋白质</span></div></div></div><div class="daily-breakdown">${Array.from({ length: 7 }, (_, index) => { const day = summary.days[addDays(state.weekStart, index)]; const kcal = day?.kcal || 0; return `<div class="breakdown-day ${kcal ? "filled" : ""}"><span>${WEEKDAY_LABELS[index].replace("周", "")}</span><i><b style="height:${Math.min(100, Math.max(5, (kcal / Math.max(target.target_kcal, 1)) * 100))}%"></b></i><strong>${kcal ? shortNumber(kcal) : "—"}</strong></div>`; }).join("")}</div>`; }

  function renderShopping() { const plan = currentPlan(); const list = state.shopping[state.weekStart] || []; const categories = [...new Set(list.map((item) => item.category))]; dom.shoppingWeek.textContent = `${dateFormatter.format(new Date(`${state.weekStart}T12:00:00`))} — ${dateFormatter.format(new Date(`${addDays(state.weekStart, 6)}T12:00:00`))}`; dom.shoppingCount.textContent = `${list.length} 种食材 · ${shortNumber(core.plateCount(plan))} 盘菜`; if (!list.length) { dom.shoppingContent.innerHTML = `<div class="empty-state shopping-empty"><span class="empty-icon">□</span><strong>清单还是空的</strong><p>先去周计划安排几顿饭，这里会自动按生重合并。</p><button class="primary-button" data-view="planner" type="button">去安排本周 <span>→</span></button></div>`; return; } dom.shoppingContent.innerHTML = `<div class="shopping-progress"><div><span>本周准备进度</span><strong>0 <small>/ ${list.length} 种食材</small></strong></div><div class="progress-track"><i></i></div></div>${categories.map((category) => `<section class="shopping-group"><div class="group-title"><span class="category-mark ${category}">${(CATEGORY_LABELS[category] || category).slice(0, 1)}</span><h2>${esc(CATEGORY_LABELS[category] || category)}</h2><span>${list.filter((item) => item.category === category).length} 种</span></div><div class="shopping-items">${list.filter((item) => item.category === category).map((item) => `<label class="shopping-item"><input type="checkbox" /><span class="checkmark"></span><span class="shopping-name"><strong>${esc(item.name)}</strong><small>来自本周菜谱汇总</small></span><b>${shortNumber(item.raw_weight_g)}<small>g</small></b></label>`).join("")}</div></section>`).join("")}<div class="shopping-note"><span>◎</span><p>所有重量都是下锅前的生重。称好、分装，工作日就能直接带走。</p></div>`; }


  async function calculateNutrition(values, context) { return request(context, "POST", "/nutrition/calculate", core.buildNutritionRequest(values)); }


  document.addEventListener("click", (event) => { const actionTarget = event.target.closest("[data-action]"); const viewTarget = event.target.closest("[data-view]"); if (viewTarget && !actionTarget) { setView(viewTarget.dataset.view); return; } if (!actionTarget) return; const { action, id, date, meal } = actionTarget.dataset; if (action === "retry-load") { bootstrap(scope.capture()); return; } if (!state.ready || state.busy) return; if (action === "go-planner") setView("planner"); if (action === "edit-baseline") { dom.nutritionForm.scrollIntoView({ behavior: "smooth", block: "center" }); showToast("在上方重新计算，或直接调整结果", "info"); } if (action === "new-recipe") { state.recipeEditingId = "new"; renderRecipes(); dom.recipeEditor.scrollIntoView({ behavior: "smooth", block: "start" }); } if (action === "edit-recipe") { state.recipeEditingId = id; renderRecipes(); dom.recipeEditor.scrollIntoView({ behavior: "smooth", block: "start" }); } if (action === "close-editor") { state.recipeEditingId = null; state.mealEditingId = null; state.pendingMeal = null; render(); } if (action === "delete-recipe") deleteRecipe(id); if (action === "add-to-plan") { setView("planner"); state.mealEditingId = "new"; state.pendingMeal = { recipe_id: id }; renderPlanner(); } if (action === "add-ingredient") addIngredientRow(); if (action === "remove-ingredient") { actionTarget.closest(".ingredient-row")?.remove(); updateIngredientNumbers(); updateRecipeNutritionPreview(); } if (action === "add-meal") { state.mealEditingId = "new"; state.pendingMeal = { date, meal }; renderPlanner(); dom.mealEditor.scrollIntoView({ behavior: "smooth", block: "center" }); } if (action === "remove-meal") removeMeal(id); if (action === "previous-week") changeWeek(-7); if (action === "next-week") changeWeek(7); if (action === "current-week") { selectWeek(mondayOf()); } });
  document.addEventListener("change", (event) => { if (event.target.matches(".shopping-item input")) { event.target.closest(".shopping-item").classList.toggle("checked", event.target.checked); updateShoppingProgress(); } if (event.target.id === "week-start" && event.target.value) { selectWeek(mondayOf(new Date(`${event.target.value}T12:00:00`))); } });
  document.addEventListener("input", (event) => { if (event.target.closest("#recipe-form") && (event.target.name === "ingredient_id" || event.target.name === "raw_weight_g")) updateRecipeNutritionPreview(); });
  dom.nutritionForm.addEventListener("submit", event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    return mutate(async context => {
      const payload = await calculateNutrition(values, context);
      renderNutritionResult(payload);
      pendingNutrition = { ...pendingNutrition, inputs: core.buildNutritionRequest(values) };
    });
  });
  document.addEventListener("submit", event => {
    if (event.target.id === "baseline-confirm-form") {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(event.target).entries());
      const result = core.applyNutritionTargets(pendingNutrition || {}, values);
      if (!result.ok) return showToast("请检查目标数值", "error");
      const inputs = pendingNutrition?.inputs;
      if (!inputs) return showToast("请先计算推荐目标", "error");
      mutate(async context => {
        state.baseline = await request(context, "PUT", "/profile/baseline", { ...inputs, ...Object.fromEntries(["target_kcal", "protein_g", "carbs_g", "fat_g"].map(field => [field, result.value[field]])) });
        dom.nutritionResult.hidden = true;
        showToast("营养基线已保存，下一步可以排一周午餐了。");
      });
    }
    if (event.target.id === "recipe-form") { event.preventDefault(); saveRecipe(event.target); }
    if (event.target.id === "meal-form") { event.preventDefault(); saveMeal(event.target); }
  });

  function updateRecipeNutritionPreview() { const form = document.querySelector("#recipe-form"); if (!form) return; const ingredients = [...form.querySelectorAll(".ingredient-row")].map((row) => ({ ingredient_id: row.querySelector('[name="ingredient_id"]').value, raw_weight_g: Number(row.querySelector('[name="raw_weight_g"]').value) || 0 })); const nutrition = core.calculateRecipeNutrition(ingredients, catalog); const target = form.querySelector(".live-nutrition"); if (target) target.innerHTML = `<span>实时营养估算</span><strong>${shortNumber(nutrition.kcal)} <small>kcal</small></strong><em>${shortNumber(nutrition.protein_g)}g 蛋白质 · ${shortNumber(nutrition.carbs_g)}g 碳水 · ${shortNumber(nutrition.fat_g)}g 脂肪</em>`; }
  function addIngredientRow() { const rows = document.querySelector("#ingredient-rows"); if (!rows) return; const index = rows.children.length; rows.insertAdjacentHTML("beforeend", ingredientRow({ ingredient_id: catalog[0]?.id, raw_weight_g: 100 }, index)); updateRecipeNutritionPreview(); }
  function updateIngredientNumbers() { document.querySelectorAll("#ingredient-rows .row-number").forEach((item, index) => { item.textContent = String(index + 1).padStart(2, "0"); }); }
  function updateShoppingProgress() { const checked = document.querySelectorAll(".shopping-item input:checked").length; const total = document.querySelectorAll(".shopping-item input").length; const progress = document.querySelector(".shopping-progress"); if (progress) { progress.querySelector("strong").innerHTML = `${checked} <small>/ ${total} 种食材</small>`; progress.querySelector("i").style.width = `${total ? (checked / total) * 100 : 0}%`; } }
  function saveRecipe(form) {
    const ingredients = [...form.querySelectorAll(".ingredient-row")].map(row => ({ ingredient_id: Number(row.querySelector('[name="ingredient_id"]').value), raw_weight_g: Number(row.querySelector('[name="raw_weight_g"]').value) }));
    const values = { name: form.querySelector('[name="name"]').value, description: form.querySelector('[name="description"]').value, ingredients };
    const errors = core.validateRecipeInput(values);
    if (Object.keys(errors).length) return showToast(Object.values(errors)[0], "error");
    const editingId = state.recipeEditingId;
    return mutate(async context => {
      await request(context, editingId === "new" ? "POST" : "PATCH", editingId === "new" ? "/recipes" : `/recipes/${editingId}`, values);
      state.recipes = (await request(context, "GET", "/recipes")).items;
      state.recipeEditingId = null;
      await loadWeek(context, state.weekStart);
      showToast("菜谱已保存，可以加入本周计划了。");
    });
  }
  function deleteRecipe(id) {
    const recipe = getRecipe(id);
    if (!recipe || !window.confirm(`确定归档「${recipe.name}」吗？已有计划会保留这道菜。`)) return;
    return mutate(async context => {
      await request(context, "DELETE", `/recipes/${id}`);
      state.recipes = (await request(context, "GET", "/recipes")).items;
      state.recipeEditingId = null;
      await loadWeek(context, state.weekStart);
      showToast("菜谱已归档", "info");
    });
  }
  function saveMeal(form) {
    const values = Object.fromEntries(new FormData(form).entries());
    const payload = { planned_date: values.planned_date, meal_type: values.meal_type, input_mode: "recipe", recipe_id: values.recipe_id, quantity: Number(values.quantity), sort_order: 0 };
    const errors = core.validatePlanItem(payload);
    if (Object.keys(errors).length) return showToast(Object.values(errors)[0], "error");
    const week = state.weekStart, editingId = state.mealEditingId;
    return mutate(async context => {
      let plan = state.plans[week];
      if (!plan) {
        if (!state.baseline) throw new Error("请先确认并保存营养基线");
        const baseline = state.baseline;
        try { plan = mapPlan(await request(context, "POST", "/meal-plans", { week_start: week, target_kcal: baseline.target_kcal, target_protein_g: baseline.protein_g, target_carbs_g: baseline.carbs_g, target_fat_g: baseline.fat_g })); }
        catch (error) { if (error.status !== 409) throw error; plan = mapPlan(await request(context, "GET", `/meal-plans/${week}`)); }
      }
      if (editingId === "new") await request(context, "POST", `/meal-plans/${week}/items`, payload);
      else await request(context, "PUT", `/meal-plans/${week}/items`, { expected_revision: plan.revision, items: plan.items.map(item => item.id === editingId ? itemInput({ ...item, ...payload }) : itemInput(item)) });
      state.mealEditingId = null; state.pendingMeal = null;
      await loadWeek(context, week);
      showToast("计划已保存");
    });
  }
  function removeMeal(id) {
    const week = state.weekStart, plan = currentPlan();
    return mutate(async context => {
      await request(context, "PUT", `/meal-plans/${week}/items`, { expected_revision: plan.revision, items: plan.items.filter(item => item.id !== id).map(itemInput) });
      await loadWeek(context, week);
      showToast("已从计划移除", "info");
    });
  }
  function changeWeek(days) { selectWeek(addDays(state.weekStart, days)); }

  async function request(context, method, path, body) {
    scope.assert(context);
    const payload = await api(method, path, body, context.signal);
    scope.assert(context);
    return payload;
  }
  function mapPlan(plan) {
    return { ...plan, weekStart: plan.week_start, target: { ...plan.target, target_kcal: plan.target.kcal } };
  }
  function itemInput(item) {
    const common = { ...(item.id ? { id: item.id } : {}), planned_date: item.planned_date, meal_type: item.meal_type, input_mode: item.input_mode, meal_name: item.meal_name || null, sort_order: item.sort_order || 0 };
    return item.input_mode === "manual" ? { ...common, meal_name: item.meal_name, ...Object.fromEntries(Object.entries(item.manual_nutrition).map(([key, value]) => [`manual_${key}`, value])) } : { ...common, recipe_id: item.recipe_id, quantity: Number(item.quantity) };
  }
  async function optional(context, path) {
    try { return await request(context, "GET", path); } catch (error) { if (error.status === 404) return null; throw error; }
  }
  async function loadWeek(context, week) {
    const loadVersion = ++weekLoadVersion;
    const plan = await optional(context, `/meal-plans/${week}`);
    if (week !== state.weekStart || loadVersion !== weekLoadVersion) return;
    if (!plan) { delete state.plans[week]; delete state.summaries[week]; delete state.shopping[week]; render(); return; }
    const [nutrition, shopping] = await Promise.all([request(context, "GET", `/meal-plans/${week}/nutrition`), request(context, "GET", `/meal-plans/${week}/shopping-list`)]);
    if (week !== state.weekStart || loadVersion !== weekLoadVersion) return;
    const missing = [...new Set(plan.items.filter(item => item.input_mode === "recipe" && !getRecipe(item.recipe_id)).map(item => item.recipe_id))];
    const historical = await Promise.all(missing.map(id => request(context, "GET", `/recipes/${id}`)));
    if (week !== state.weekStart || loadVersion !== weekLoadVersion) return;
    state.historicalRecipes.push(...historical);
    state.plans[week] = mapPlan(plan);
    state.summaries[week] = { total: nutrition.total, days: Object.fromEntries(nutrition.days.map(day => [day.planned_date, day.nutrition])) };
    state.shopping[week] = shopping.items.map(item => ({ id: String(item.ingredient_id), name: item.ingredient_name, category: item.category, raw_weight_g: item.total_raw_weight_g }));
    render();
  }
  function controlsDisabled(disabled) {
    document.querySelectorAll('.app-shell button[type="submit"], .app-shell [data-action], #week-start').forEach(button => { button.disabled = disabled; });
  }
  function reportError(error, context) {
    if (error.name === "AbortError") return;
    try { scope.assert(context); } catch (_) { return; }
    const message = error.status === 401 ? "登录已过期，请重新登录" : error.message || "服务暂不可用，请稍后重试";
    showToast(message, "error");
    dom.healthDot.classList.remove("online"); dom.healthDot.classList.add("offline");
    dom.healthText.textContent = message;
    if (!state.ready) dom.savedBaseline.innerHTML = `<div class="empty-state"><strong>数据加载失败</strong><p>${esc(message)}</p><button type="button" class="primary-button" data-action="retry-load">重新加载</button></div>`;
  }
  async function mutate(operation) {
    if (!state.ready || state.busy) return;
    const context = scope.capture(); state.busy = true; controlsDisabled(true);
    try { await operation(context); scope.assert(context); render(); }
    catch (error) { reportError(error, context); }
    finally {
      try { scope.assert(context); state.busy = false; controlsDisabled(!state.ready); } catch (_) { /* Previous account cannot update this view. */ }
    }
  }
  async function bootstrap(context) {
    if (!context.userId) return;
    state.ready = false; controlsDisabled(true);
    dom.healthText.textContent = "正在读取你的数据…";
    try {
      const [ingredients, baseline, recipes] = await Promise.all([request(context, "GET", "/ingredients"), optional(context, "/profile/baseline"), request(context, "GET", "/recipes")]);
      catalog = ingredients.items; state.baseline = baseline; state.recipes = recipes.items;
      await loadWeek(context, state.weekStart);
      scope.assert(context); state.ready = true;
      if (baseline) Object.entries(baseline).forEach(([key, value]) => { const input = dom.nutritionForm.elements.namedItem(key); if (input) input.value = value; });
      dom.healthDot.classList.remove("offline"); dom.healthDot.classList.add("online");
      dom.healthText.textContent = "已连接 · 云端保存";
      render(); controlsDisabled(false);
    } catch (error) { try { scope.assert(context); } catch (_) { return; } reportError(error, context); controlsDisabled(true); const retry = document.querySelector('[data-action="retry-load"]'); if (retry) retry.disabled = false; }
  }
  function syncSession() {
    const userId = window.MealPrepAuth?.getSession()?.user?.id || null;
    if (!scope.setUser(userId)) return;
    state = freshState(); catalog = []; pendingNutrition = null;
    dom.recipeEditor.innerHTML = ""; dom.mealEditor.innerHTML = "";
    dom.nutritionForm.reset(); dom.nutritionResult.innerHTML = ""; dom.nutritionResult.hidden = true;
    dom.toast.textContent = ""; dom.toast.classList.remove("show");
    dom.healthDot.classList.remove("online", "offline"); dom.healthText.textContent = "请先登录";
    render(); controlsDisabled(true);
    if (userId) bootstrap(scope.capture());
  }
  async function selectWeek(week) {
    state.weekStart = week; state.mealEditingId = null; state.pendingMeal = null; render();
    if (!state.ready) return;
    const context = scope.capture();
    try { await loadWeek(context, week); } catch (error) { reportError(error, context); }
  }
  window.addEventListener("mealprep:authchange", syncSession);
  syncSession();
  render();
})();
