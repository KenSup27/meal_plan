/* Run after restarting the local backend, against a completed hosted.cjs run. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const manifest = JSON.parse(fs.readFileSync(process.env.MEAL_PREP_E2E_MANIFEST, 'utf8'));
const base = process.env.MEAL_PREP_E2E_URL || 'http://127.0.0.1:8021';
const artifacts = process.env.MEAL_PREP_E2E_ARTIFACTS;
assert.equal(manifest.project, process.env.MEAL_PREP_E2E_PROJECT);
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const account = manifest.accounts[0];
assert.equal(account.email, `meal-plan-e2e-${manifest.run}-a@example.com`);
const checks = [];
const check = name => {checks.push(name); console.log(`PASS ${name}`);};
let browser, page;
async function api(method, route, body) {
  return page.evaluate(async ({method, route, body}) => {
    const response = await fetch('/api/v1'+route, {method, headers:{Authorization:`Bearer ${window.MealPrepAuth.getAccessToken()}`, 'Content-Type':'application/json'}, ...(body===undefined ? {} : {body:JSON.stringify(body)})});
    return {status:response.status, body:response.status===204 ? null : await response.json()};
  }, {method,route,body});
}
(async()=>{
  browser = await chromium.launch({channel:process.env.MEAL_PREP_E2E_BROWSER || 'chrome',headless:true});
  page = await browser.newPage({viewport:{width:375,height:812}});
  await page.goto(base);
  await page.locator('#auth-email').fill(account.email);
  await page.locator('#auth-password').fill(account.password);
  await page.locator('#auth-submit-button').click();
  await page.waitForFunction(()=>document.querySelector('#health-text').textContent==='已连接 · 云端保存', null, {timeout:60000});
  const week = await page.locator('#week-start').inputValue();
  let plan = (await api('GET', `/meal-plans/${week}`)).body;
  const recipes = (await api('GET','/recipes')).body.items;
  assert.equal(recipes.length,2);assert.equal(plan.items.length,3);
  assert.equal((await api('GET','/profile/baseline')).body.target_kcal,1800);
  assert.deepEqual((await api('GET',`/meal-plans/${week}/nutrition`)).body.total,{kcal:1435.1,protein_g:146.7,carbs_g:85.8,fat_g:53.6});
  check('backend restart restores baseline recipes plan and exact nutrition');
  await page.locator('.nav-item[data-view="recipes"]').click();
  await page.locator('[data-action="new-recipe"]').click();
  await page.locator('#recipe-form [name="name"]').fill('必须保留的未保存草稿');
  await page.route('**/api/v1/recipes', async route=>{
    if(route.request().method()==='POST') await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'端到端模拟网络保存失败'})});
    else await route.continue();
  });
  await page.locator('#recipe-form button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#toast').dataset.tone==='error');
  assert.ok((await page.locator('#toast').textContent()).includes('保存失败'));
  assert.equal(await page.locator('#recipe-form [name="name"]').inputValue(),'必须保留的未保存草稿');
  assert.equal((await api('GET','/recipes')).body.total,2);
  await page.unroute('**/api/v1/recipes');
  check('failed server write preserves draft and never reports success');
  await page.locator('[data-action="close-editor"]').click();
  const recipe = recipes.find(r=>plan.items.some(i=>i.recipe_id===r.id));
  page.once('dialog',dialog=>dialog.accept());
  const archived = page.waitForResponse(r=>r.url().endsWith(`/recipes/${recipe.id}`)&&r.request().method()==='DELETE');
  await page.locator(`[data-action="delete-recipe"][data-id="${recipe.id}"]`).click();
  assert.equal((await archived).status(),204);
  await page.waitForFunction(()=>!document.querySelector('[data-action="new-recipe"]').disabled);
  assert.equal((await api('GET','/recipes')).body.total,1);
  assert.equal((await api('GET',`/recipes/${recipe.id}`)).status,200);
  assert.deepEqual((await api('GET',`/meal-plans/${week}/nutrition`)).body.total,{kcal:1435.1,protein_g:146.7,carbs_g:85.8,fat_g:53.6});
  await page.locator('.nav-item[data-view="planner"]').click();
  assert.ok((await page.locator('#planner-grid').textContent()).includes(recipe.name));
  check('archived recipe stays readable in historical plan and nutrition');
  plan = (await api('GET',`/meal-plans/${week}`)).body;
  const items=plan.items.map(({manual_nutrition,...item})=>({...item,...(manual_nutrition ? Object.fromEntries(Object.entries(manual_nutrition).map(([key,value])=>[`manual_${key}`,value])) : {})}));
  assert.equal((await api('PUT',`/meal-plans/${week}/items`,{expected_revision:plan.revision,items})).status,200);
  assert.equal((await api('GET',`/meal-plans/${week}`)).body.items.length,3);
  check('atomic replacement preserves unchanged archived and manual meals');
  const newWeek='2026-10-12';
  await page.locator('#week-start').fill(newWeek);await page.locator('#week-start').dispatchEvent('change');
  await page.waitForFunction(()=>document.querySelector('#planner-summary .summary-stats strong')?.textContent==='0');
  assert.equal((await api('GET',`/meal-plans/${newWeek}`)).status,404);
  check('week navigation never creates an empty plan');
  fs.writeFileSync(`${artifacts}/restore-result.json`, JSON.stringify({run:manifest.run,checks},null,2));
})().catch(error=>{console.error(`FAIL ${error.message}`);process.exitCode=1;}).finally(async()=>{
  if(page) {try {await page.evaluate(()=>window.MealPrepAuth.client.auth.signOut({scope:'global'}));}catch(_){}}
  if(browser) await browser.close();
});
