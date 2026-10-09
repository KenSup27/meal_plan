const test = require("node:test");
const assert = require("node:assert/strict");

const {
  applyNutritionTargets,
  buildNutritionRequest,
  normalizeNutritionResponse,
  validateNutritionTargets,
} = require("../app-core.js");

test("buildNutritionRequest converts form values to API types", () => {
  assert.deepEqual(
    buildNutritionRequest({
      sex: "female",
      age: "30",
      height_cm: "165",
      weight_kg: "60",
      activity_factor: "1.375",
      goal: "cut",
    }),
    {
      sex: "female",
      age: 30,
      height_cm: 165,
      weight_kg: 60,
      activity_factor: 1.375,
      goal: "cut",
    },
  );
});

test("normalizeNutritionResponse turns numeric strings into numbers", () => {
  assert.deepEqual(
    normalizeNutritionResponse({
      bmr_kcal: "1320.0",
      tdee_kcal: 1815,
      target_kcal: "1415",
      protein_g: 108,
      carbs_g: "154.2",
      fat_g: 39.3,
    }),
    {
      bmr_kcal: 1320,
      tdee_kcal: 1815,
      target_kcal: 1415,
      protein_g: 108,
      carbs_g: 154.2,
      fat_g: 39.3,
    },
  );
});

test("validateNutritionTargets rejects missing and negative editable values", () => {
  assert.deepEqual(validateNutritionTargets({ target_kcal: 1400, protein_g: -1 }), {
    carbs_g: "请输入不小于 0 的数字",
    fat_g: "请输入不小于 0 的数字",
    protein_g: "请输入不小于 0 的数字",
  });
});

test("applyNutritionTargets keeps calculated values and replaces editable targets", () => {
  const result = applyNutritionTargets(
    {
      bmr_kcal: 1320,
      tdee_kcal: 1815,
      target_kcal: 1415,
      protein_g: 108,
      carbs_g: 154.2,
      fat_g: 39.3,
    },
    { target_kcal: "1500", protein_g: "120", carbs_g: "160", fat_g: "42" },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.value, {
    bmr_kcal: 1320,
    tdee_kcal: 1815,
    target_kcal: 1500,
    protein_g: 120,
    carbs_g: 160,
    fat_g: 42,
  });
});
