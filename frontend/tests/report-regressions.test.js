const test = require('node:test');
const assert = require('node:assert/strict');
const { createClient, createSessionScope } = require('../api.js');
const { aggregatePlanNutrition, plateCount } = require('../app-core.js');

test('account switches invalidate late results and abort prior requests', async () => {
  const scope = createSessionScope();
  assert.equal(scope.setUser('a'), true);
  const old = scope.capture();
  assert.equal(scope.setUser('a'), false);
  scope.assert(old);
  scope.setUser(null); scope.setUser('b');
  assert.equal(old.signal.aborted, true);
  assert.throws(() => scope.assert(old), { name: 'AbortError' });
  scope.assert(scope.capture());
});

test('business API sends current token and accepts empty DELETE responses', async () => {
  let token = 'a'; const calls = [];
  const request = createClient(() => token, async (url, options) => { calls.push([url, options]); return { status: 204 }; });
  assert.equal(await request('DELETE', '/recipes/1'), null);
  token = 'b'; await request('DELETE', '/recipes/2');
  assert.deepEqual(calls.map(call => call[1].headers.Authorization), ['Bearer a', 'Bearer b']);
});

test('failed server writes reject and never become local success', async () => {
  const request = createClient(() => 'a', async () => ({ ok: false, status: 503, json: async () => ({ detail: 'unavailable' }) }));
  await assert.rejects(request('POST', '/recipes', {}), { status: 503, message: 'unavailable' });
});

test('week totals round raw detail once, include manual nutrition, and count quantities', () => {
  const catalog = [{id: 1, kcal_per_100g: 133, protein_per_100g: 23.3, carbs_per_100g: 0, fat_per_100g: 4.7}, {id: 12, kcal_per_100g: 34, protein_per_100g: 2.8, carbs_per_100g: 4.3, fat_per_100g: 0.4}, {id: 30, kcal_per_100g: 884, protein_per_100g: 0, carbs_per_100g: 0, fat_per_100g: 100}];
  const recipes = [{ id: 'sample', ingredients: [{ingredient_id: 1, raw_weight_g: 150}, {ingredient_id: 12, raw_weight_g: 200}, {ingredient_id: 30, raw_weight_g: 5}] }];
  const plan = { items: [2,1].map((quantity, i) => ({ input_mode: 'recipe', recipe_id: 'sample', quantity, planned_date: `2026-10-0${5+i}`, meal_type: 'lunch' })) };
  assert.deepEqual(aggregatePlanNutrition(plan, recipes, catalog).total, { kcal: 935.1, protein_g: 121.7, carbs_g: 25.8, fat_g: 38.6 });
  assert.equal(plateCount(plan), 3);
  plan.items.push({input_mode: 'manual', planned_date: '2026-10-05', meal_type: 'breakfast', manual_nutrition: {kcal: 500, protein_g: 25, carbs_g: 60, fat_g: 15}});
  assert.equal(plateCount(plan), 3);
  assert.equal(aggregatePlanNutrition(plan, recipes, catalog).total.kcal, 1435.1);
  plan.items[0].quantity = 0.5;
  assert.equal(plateCount(plan), 1.5);
});
