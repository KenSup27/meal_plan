const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildRecipe,
  calculateRecipeNutrition,
  validateRecipeInput,
} = require("../app-core.js");

const catalog = [
  { id: "chicken", kcal_per_100g: 165, protein_per_100g: 31, carbs_per_100g: 0, fat_per_100g: 3.6 },
  { id: "broccoli", kcal_per_100g: 34, protein_per_100g: 2.8, carbs_per_100g: 6.6, fat_per_100g: 0.4 },
];

test("validateRecipeInput requires a name and at least one positive ingredient", () => {
  assert.deepEqual(validateRecipeInput({ name: "", ingredients: [] }), {
    name: "请填写菜谱名称",
    ingredients: "至少添加一种食材",
  });

  assert.deepEqual(validateRecipeInput({
    name: "鸡肉",
    ingredients: [{ ingredient_id: "chicken", raw_weight_g: 0 }],
  }), { weight_0: "生重必须大于 0" });
});

test("calculateRecipeNutrition aggregates raw weights per 100g", () => {
  assert.deepEqual(calculateRecipeNutrition([
    { ingredient_id: "chicken", raw_weight_g: 150 },
    { ingredient_id: "broccoli", raw_weight_g: 200 },
  ], catalog), {
    kcal: 315.5,
    protein_g: 52.1,
    carbs_g: 13.2,
    fat_g: 6.2,
  });
});

test("buildRecipe stores one-dish semantics without a servings field", () => {
  const recipe = buildRecipe({
    name: "鸡肉西兰花",
    description: "工作日午餐",
    ingredients: [{ ingredient_id: "chicken", raw_weight_g: "150" }],
  }, "recipe-1");

  assert.deepEqual(recipe, {
    id: "recipe-1",
    name: "鸡肉西兰花",
    description: "工作日午餐",
    ingredients: [{ ingredient_id: "chicken", raw_weight_g: 150 }],
  });
  assert.equal(Object.hasOwn(recipe, "servings"), false);
});
