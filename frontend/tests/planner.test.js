const test = require("node:test");
const assert = require("node:assert/strict");

const {
  addPlanItem,
  aggregatePlanNutrition,
  buildShoppingList,
  createPlan,
  missingMealTypes,
} = require("../app-core.js");

const catalog = [
  { id: "chicken", name: "鸡胸肉", category: "meat", kcal_per_100g: 165, protein_per_100g: 31, carbs_per_100g: 0, fat_per_100g: 3.6 },
  { id: "broccoli", name: "西兰花", category: "vegetable", kcal_per_100g: 34, protein_per_100g: 2.8, carbs_per_100g: 6.6, fat_per_100g: 0.4 },
];
const recipes = [
  { id: "chicken-dish", name: "鸡肉西兰花", ingredients: [
    { ingredient_id: "chicken", raw_weight_g: 150 },
    { ingredient_id: "broccoli", raw_weight_g: 200 },
  ] },
];

test("addPlanItem permits multiple recipe items for the same date and meal", () => {
  let plan = createPlan("2026-10-12", { target_kcal: 1800 });
  plan = addPlanItem(plan, { planned_date: "2026-10-12", meal_type: "lunch", recipe_id: "chicken-dish", quantity: 1 }, "meal-1").plan;
  plan = addPlanItem(plan, { planned_date: "2026-10-12", meal_type: "lunch", recipe_id: "chicken-dish", quantity: 2 }, "meal-2").plan;
  assert.equal(plan.items.length, 2);
  assert.equal(plan.items[0].quantity, 1);
  assert.equal(plan.items[1].quantity, 2);
});

test("aggregatePlanNutrition multiplies recipe nutrition by quantity per day", () => {
  let plan = createPlan("2026-10-12");
  plan = addPlanItem(plan, { planned_date: "2026-10-12", meal_type: "lunch", recipe_id: "chicken-dish", quantity: 2 }, "meal-1").plan;
  const summary = aggregatePlanNutrition(plan, recipes, catalog);
  assert.deepEqual(summary.days["2026-10-12"], {
    kcal: 631,
    protein_g: 104.2,
    carbs_g: 26.4,
    fat_g: 12.4,
    mealTypes: new Set(["lunch"]),
  });
  assert.equal(summary.total.kcal, 631);
});

test("missingMealTypes reports lunch and dinner without treating breakfast as a failure", () => {
  let plan = createPlan("2026-10-12");
  plan = addPlanItem(plan, { planned_date: "2026-10-12", meal_type: "lunch", recipe_id: "chicken-dish", quantity: 1 }).plan;
  assert.deepEqual(missingMealTypes(plan, "2026-10-12"), ["dinner"]);
  assert.deepEqual(missingMealTypes(plan, "2026-10-13"), ["lunch", "dinner"]);
});

test("buildShoppingList merges raw weights by ingredient and ignores manual meals", () => {
  let plan = createPlan("2026-10-12");
  plan = addPlanItem(plan, { planned_date: "2026-10-12", meal_type: "lunch", recipe_id: "chicken-dish", quantity: 2 }).plan;
  plan.items.push({ planned_date: "2026-10-12", meal_type: "dinner", input_mode: "manual", manual_kcal: 500 });
  assert.deepEqual(buildShoppingList(plan, recipes, catalog), [
    { id: "chicken", name: "鸡胸肉", category: "meat", raw_weight_g: 300 },
    { id: "broccoli", name: "西兰花", category: "vegetable", raw_weight_g: 400 },
  ]);
});
