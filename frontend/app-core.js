(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MealPrepCore = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const NUTRITION_FIELDS = ["target_kcal", "protein_g", "carbs_g", "fat_g"];

  function toFiniteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function buildNutritionRequest(formValues) {
    return {
      sex: formValues.sex,
      age: Number(formValues.age),
      height_cm: Number(formValues.height_cm),
      weight_kg: Number(formValues.weight_kg),
      activity_factor: Number(formValues.activity_factor),
      goal: formValues.goal,
    };
  }

  function normalizeNutritionResponse(payload) {
    const normalized = {};
    ["bmr_kcal", "tdee_kcal", ...NUTRITION_FIELDS].forEach((field) => {
      normalized[field] = toFiniteNumber(payload && payload[field]);
    });
    return normalized;
  }

  function validateNutritionTargets(values) {
    const errors = {};
    NUTRITION_FIELDS.forEach((field) => {
      const value = toFiniteNumber(values && values[field]);
      if (value === null || value < 0) {
        errors[field] = "请输入不小于 0 的数字";
      }
    });
    return errors;
  }

  function applyNutritionTargets(calculation, editableValues) {
    const normalized = normalizeNutritionResponse(calculation);
    const errors = validateNutritionTargets(editableValues);
    if (Object.keys(errors).length > 0) {
      return { ok: false, errors };
    }
    return {
      ok: true,
      value: {
        ...normalized,
        ...NUTRITION_FIELDS.reduce((result, field) => {
          result[field] = Number(editableValues[field]);
          return result;
        }, {}),
      },
    };
  }

  function round1(value) {
    return Math.round((value + Number.EPSILON) * 10) / 10;
  }

  function validateRecipeInput(values) {
    const errors = {};
    if (!String(values && values.name || "").trim()) {
      errors.name = "请填写菜谱名称";
    }
    const ingredients = Array.isArray(values && values.ingredients) ? values.ingredients : [];
    if (ingredients.length === 0) {
      errors.ingredients = "至少添加一种食材";
    }
    ingredients.forEach((ingredient, index) => {
      if (!ingredient.ingredient_id) {
        errors[`ingredient_${index}`] = "请选择食材";
      }
      const weight = Number(ingredient.raw_weight_g);
      if (!Number.isFinite(weight) || weight <= 0) {
        errors[`weight_${index}`] = "生重必须大于 0";
      }
    });
    return errors;
  }

  function calculateRecipeNutritionRaw(ingredients, catalog) {
    const byId = new Map((catalog || []).map((ingredient) => [String(ingredient.id), ingredient]));
    const totals = { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };
    (ingredients || []).forEach((item) => {
      const ingredient = byId.get(String(item.ingredient_id));
      const weight = Number(item.raw_weight_g);
      if (!ingredient || !Number.isFinite(weight) || weight <= 0) return;
      const ratio = weight / 100;
      totals.kcal += Number(ingredient.kcal_per_100g) * ratio;
      totals.protein_g += Number(ingredient.protein_per_100g) * ratio;
      totals.carbs_g += Number(ingredient.carbs_per_100g) * ratio;
      totals.fat_g += Number(ingredient.fat_per_100g) * ratio;
    });
    return totals;
  }

  function calculateRecipeNutrition(ingredients, catalog) {
    const totals = calculateRecipeNutritionRaw(ingredients, catalog);
    return Object.fromEntries(Object.entries(totals).map(([field, value]) => [field, round1(value)]));
  }

  function plateCount(plan) {
    return round1((plan?.items || []).filter(item => item.input_mode === "recipe")
      .reduce((sum, item) => sum + Number(item.quantity || 0), 0));
  }

  function buildRecipe(values, id) {
    const ingredients = (values.ingredients || []).map((ingredient) => ({
      ingredient_id: String(ingredient.ingredient_id),
      raw_weight_g: Number(ingredient.raw_weight_g),
    }));
    return {
      id: id || `recipe-${Date.now()}`,
      name: String(values.name || "").trim(),
      description: String(values.description || "").trim(),
      ingredients,
    };
  }

  const PLANNED_MEAL_TYPES = ["lunch", "dinner"];

  function createPlan(weekStart, target) {
    return {
      weekStart,
      target: target ? { ...target } : null,
      items: [],
    };
  }

  function validatePlanItem(item) {
    const errors = {};
    if (!item || !item.planned_date) errors.planned_date = "请选择日期";
    if (!PLANNED_MEAL_TYPES.includes(item && item.meal_type)) errors.meal_type = "餐次无效";
    if (!item || !item.recipe_id) errors.recipe_id = "请选择菜谱";
    if (!Number.isFinite(Number(item && item.quantity)) || Number(item.quantity) <= 0) {
      errors.quantity = "数量必须大于 0";
    }
    return errors;
  }

  function addPlanItem(plan, item, id) {
    const errors = validatePlanItem(item);
    if (Object.keys(errors).length > 0) return { ok: false, errors };
    return {
      ok: true,
      plan: {
        ...plan,
        items: [
          ...(plan.items || []),
          {
            id: id || `meal-${Date.now()}`,
            planned_date: item.planned_date,
            meal_type: item.meal_type,
            input_mode: "recipe",
            recipe_id: String(item.recipe_id),
            quantity: Number(item.quantity),
          },
        ],
      },
    };
  }

  function recipeNutritionById(recipeId, recipes, catalog) {
    const recipe = (recipes || []).find((item) => String(item.id) === String(recipeId));
    return recipe ? calculateRecipeNutritionRaw(recipe.ingredients, catalog) : null;
  }

  function aggregatePlanNutrition(plan, recipes, catalog) {
    const days = {};
    const total = { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };
    (plan && plan.items || []).forEach((item) => {
      const nutrition = item.input_mode === "manual" ? item.manual_nutrition : recipeNutritionById(item.recipe_id, recipes, catalog);
      if (!nutrition) return;
      const quantity = item.input_mode === "manual" ? 1 : Number(item.quantity) || 0;
      const day = days[item.planned_date] || {
        kcal: 0,
        protein_g: 0,
        carbs_g: 0,
        fat_g: 0,
        mealTypes: new Set(),
      };
      day.mealTypes.add(item.meal_type);
      ["kcal", "protein_g", "carbs_g", "fat_g"].forEach((field) => {
        day[field] += nutrition[field] * quantity;
        total[field] += nutrition[field] * quantity;
      });
      days[item.planned_date] = day;
    });
    Object.values(days).forEach((day) => {
      ["kcal", "protein_g", "carbs_g", "fat_g"].forEach((field) => {
        day[field] = round1(day[field]);
      });
    });
    return {
      days,
      total: Object.fromEntries(Object.entries(total).map(([field, value]) => [field, round1(value)])),
    };
  }

  function missingMealTypes(plan, plannedDate) {
    const mealTypes = new Set((plan && plan.items || [])
      .filter((item) => item.planned_date === plannedDate)
      .map((item) => item.meal_type));
    return PLANNED_MEAL_TYPES.filter((mealType) => !mealTypes.has(mealType));
  }

  function buildShoppingList(plan, recipes, catalog) {
    const byId = new Map((catalog || []).map((ingredient) => [String(ingredient.id), ingredient]));
    const merged = new Map();
    (plan && plan.items || []).forEach((item) => {
      if (item.input_mode !== "recipe") return;
      const recipe = (recipes || []).find((candidate) => String(candidate.id) === String(item.recipe_id));
      if (!recipe) return;
      recipe.ingredients.forEach((ingredientItem) => {
        const ingredient = byId.get(String(ingredientItem.ingredient_id));
        if (!ingredient) return;
        const current = merged.get(String(ingredient.id)) || {
          id: String(ingredient.id),
          name: ingredient.name,
          category: ingredient.category,
          raw_weight_g: 0,
        };
        current.raw_weight_g += Number(ingredientItem.raw_weight_g) * Number(item.quantity);
        merged.set(String(ingredient.id), current);
      });
    });
    return [...merged.values()]
      .map((item) => ({ ...item, raw_weight_g: round1(item.raw_weight_g) }))
      .sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name));
  }

  return {
    NUTRITION_FIELDS,
    buildNutritionRequest,
    normalizeNutritionResponse,
    validateNutritionTargets,
    applyNutritionTargets,
    round1,
    plateCount,
    validateRecipeInput,
    calculateRecipeNutrition,
    buildRecipe,
    PLANNED_MEAL_TYPES,
    createPlan,
    validatePlanItem,
    addPlanItem,
    aggregatePlanNutrition,
    missingMealTypes,
    buildShoppingList,
  };
});
