/* Explicit hosted E2E: creates two temporary accounts. See README for cleanup. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.MEAL_PREP_E2E_URL || 'http://127.0.0.1:8021';
const projectUrl = process.env.SUPABASE_URL || process.env.SUPABASE_PROJECT_URL;
const project = process.env.MEAL_PREP_E2E_PROJECT;
assert.ok(project && new URL(projectUrl).hostname.split('.')[0] === project, 'Select the exact hosted test project');
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname), 'E2E must target a local application');
const run = crypto.randomUUID();
const artifacts = process.env.MEAL_PREP_E2E_ARTIFACTS || `/private/tmp/meal-prep-e2e-${run}`;
fs.mkdirSync(artifacts, { recursive: true });
const manifestFile = `/private/tmp/meal-prep-e2e-${run}.json`;
const accounts = ['a','b'].map(letter => ({ email: `meal-plan-e2e-${run}-${letter}@example.com`, password: `E2e!${crypto.randomBytes(18).toString('hex')}`, id: null }));
const results = [], errors = [];
const manifest = () => fs.writeFileSync(manifestFile, JSON.stringify({run, project, accounts}, null, 2), {mode:0o600});
manifest();
console.log(JSON.stringify({run, manifest:manifestFile, artifacts}));
const check = (name, detail=true) => { results.push({name,detail}); console.log(`PASS ${name}`); };
let browser;
const pages = [];
async function ready(page) { await page.waitForFunction(() => document.querySelector('#health-text').textContent === '已连接 · 云端保存', null, {timeout:60000}); }
async function view(page, name) { await page.locator(`.nav-item[data-view="${name}"]`).click(); }
async function api(page, method, route, body) {
  return page.evaluate(async ({method,route,body}) => {
    const response = await fetch('/api/v1'+route, {method, headers:{Authorization:`Bearer ${window.MealPrepAuth.getAccessToken()}`, 'Content-Type':'application/json'}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    return {status:response.status, body:response.status===204 ? null : await response.json()};
  }, {method,route,body});
}
async function login(page, account, selectMode = false) {
  if (selectMode) await page.locator('[data-auth-mode="login"]').click();
  await page.locator('#auth-email').fill(account.email);
  await page.locator('#auth-password').fill(account.password);
  await page.locator('#auth-submit-button').click();
  await ready(page);
}
async function logout(page) {
  await page.locator('#logout-button').click();
  await page.locator('#auth-gate').waitFor({state:'visible'});
  assert.equal(await page.locator('#auth-submit-button').isDisabled(), false);
  assert.ok(!(await page.locator('#auth-submit-button').textContent()).includes('处理中'));
}
async function createRecipe(page, name, rows) {
  await view(page,'recipes');
  await page.locator('[data-action="new-recipe"]').click();
  await page.locator('#recipe-form [name="name"]').fill(name);
  for (let i=0;i<rows.length;i++) {
    if (i) await page.locator('[data-action="add-ingredient"]').click();
    const row=page.locator('.ingredient-row').nth(i);
    await row.locator('select').selectOption({label:rows[i][0]});
    await row.locator('input').fill(String(rows[i][1]));
  }
  const saved = page.waitForResponse(r => r.url().endsWith('/api/v1/recipes') && r.request().method()==='POST');
  await page.locator('#recipe-form button[type="submit"]').click();
  const response=await saved; assert.equal(response.status(),201);
  const recipe=await response.json();
  await page.locator('#recipe-editor').waitFor({state:'hidden'});
  await page.waitForFunction(()=>!document.querySelector('[data-action="new-recipe"]').disabled);
  return recipe;
}
async function swaggerCrossAccount(page, recipeId) {
  const token = await page.evaluate(() => window.MealPrepAuth.getAccessToken());
  const docs = await browser.newPage();
  try {
    await docs.goto(`${base}/docs`);
    await docs.locator('.auth-wrapper .authorize').click();
    await docs.locator('.dialog-ux input').fill(token);
    await docs.locator('.dialog-ux').getByRole('button',{name:'Apply credentials',exact:true}).click();
    await docs.locator('.dialog-ux').getByRole('button',{name:'Close',exact:true}).click();
    const operation = docs.locator('#operations-default-recipe_get_api_v1_recipes__recipe_id__get');
    await operation.locator('.opblock-summary').click();
    await operation.getByRole('button',{name:'Try it out'}).click();
    await operation.locator('input[placeholder="recipe_id"]').fill(recipeId);
    const received = docs.waitForResponse(response => response.url().endsWith(`/api/v1/recipes/${recipeId}`));
    await operation.getByRole('button',{name:'Execute',exact:true}).click();
    const response = await received;
    assert.ok(response.request().headers().authorization === `Bearer ${token}`, 'Swagger must send the current B Bearer token');
    assert.equal(response.status(),404);
    check('Swagger sends real B Bearer token and rejects access to A recipe');
  } finally { await docs.close(); }
}
async function addMeal(page, recipe, quantity, meal) {
  await view(page,'recipes');
  await page.locator(`[data-action="add-to-plan"][data-id="${recipe.id}"]`).click();
  assert.equal(await page.locator('#meal-form [name="recipe_id"]').inputValue(), recipe.id);
  await page.locator('#meal-form [name="quantity"]').fill(String(quantity));
  await page.locator('#meal-form [name="meal_type"]').selectOption(meal);
  const saved=page.waitForResponse(r=>r.url().endsWith('/items')&&r.request().method()==='POST');
  await page.locator('#meal-form button[type="submit"]').click();
  assert.equal((await saved).status(),200);
  await page.locator('#meal-editor').waitFor({state:'hidden'});
  await page.waitForFunction(()=>!document.querySelector('[data-action="new-recipe"]').disabled);
}
(async()=>{
  browser=await chromium.launch({channel:process.env.MEAL_PREP_E2E_BROWSER || 'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:375,height:812}});
  const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('meal-prep-planner-demo-v1',JSON.stringify({recipes:[{id:'legacy',name:'UNOWNED-LEGACY-SECRET',ingredients:[]}],plans:{},baseline:{target_kcal:9999}})));
  await page.goto(base);
  const registered=await page.request.post(`${base}/api/v1/auth/register`,{data:{email:accounts[0].email,password:accounts[0].password}});
  assert.equal(registered.status(),201);
  const registration=await registered.json();accounts[0].id=registration.user.id;manifest();
  assert.ok(registration.session.access_token && registration.session.refresh_token);check('backend registration REST session');
  const wrong=await page.request.post(`${base}/api/v1/auth/login`,{data:{email:accounts[0].email,password:'DefinitelyWrong123!'}});
  assert.ok(wrong.status()>=400&&wrong.status()<500);check('wrong password rejected');
  const signed=await page.request.post(`${base}/api/v1/auth/login`,{data:{email:accounts[0].email,password:accounts[0].password}});
  const tokens=await signed.json();assert.ok(tokens.session.access_token);
  const refreshed=await page.request.post(`${base}/api/v1/auth/refresh`,{data:{refresh_token:tokens.session.refresh_token}});
  assert.ok((await refreshed.json()).session.access_token);check('backend login and refresh REST sessions');
  await login(page,accounts[0]);
  await logout(page); await login(page,accounts[0]); check('direct login after logout without mode click or refresh');
  assert.ok(!(await page.locator('.app-shell').textContent()).includes('UNOWNED-LEGACY-SECRET'));check('unowned global cache ignored');
  assert.equal((await api(page,'GET','/recipes')).body.total,0);
  await page.locator('#nutrition-form button[type="submit"]').click();
  await page.locator('#baseline-confirm-form').waitFor();
  const baselineSaved=page.waitForResponse(r=>r.url().endsWith('/profile/baseline')&&r.request().method()==='PUT');
  await page.locator('#baseline-confirm-form button[type="submit"]').click();
  assert.equal((await baselineSaved).status(),200);
  await page.locator('#saved-baseline .baseline-summary').waitFor();
  await page.waitForFunction(()=>!document.querySelector('[data-action="new-recipe"]').disabled);
  const baseline=await api(page,'GET','/profile/baseline');assert.equal(baseline.status,200);assert.ok(baseline.body.baseline_confirmed);check('baseline saved and read through API');
  const chicken=await createRecipe(page,`验收鸡肉-${run.slice(0,8)}`,[['鸡胸肉 · 肉禽',150],['西兰花 · 蔬菜',200],['橄榄油 · 调料',5]]);
  const salmon=await createRecipe(page,`验收三文鱼-${run.slice(0,8)}`,[['三文鱼 · 水产',120]]);
  assert.equal((await api(page,'GET','/recipes')).body.items[0].id,salmon.id);
  await addMeal(page,chicken,2,'lunch');await addMeal(page,chicken,1,'dinner');check('non-first clicked recipe selected and saved');
  const week=await page.locator('#week-start').inputValue();
  let plan=(await api(page,'GET',`/meal-plans/${week}`)).body;
  assert.equal(plan.items.reduce((sum,item)=>sum+item.quantity,0),3);
  assert.equal(await page.locator('#planner-summary .summary-stats > div').first().locator('strong').textContent(),'3');
  let nutrition=(await api(page,'GET',`/meal-plans/${week}/nutrition`)).body;
  assert.deepEqual(nutrition.total,{kcal:935.1,protein_g:121.7,carbs_g:25.8,fat_g:38.6});check('three plates and exact raw-detail totals');
  const shopping=(await api(page,'GET',`/meal-plans/${week}/shopping-list`)).body.items;
  assert.deepEqual(Object.fromEntries(shopping.map(item=>[item.ingredient_name,item.total_raw_weight_g])),{'鸡胸肉':450,'西兰花':600,'橄榄油':15});
  await view(page,'shopping');assert.ok((await page.locator('#shopping-count').textContent()).includes('3 盘菜'));check('shopping raw weights and plate count');
  await page.screenshot({path:path.join(artifacts,'shopping-375px.png'),fullPage:true});
  const addedManual=await api(page,'POST',`/meal-plans/${week}/items`,{planned_date:week,meal_type:'breakfast',input_mode:'manual',meal_name:'验收人工早餐',manual_kcal:500,manual_protein_g:25,manual_carbs_g:60,manual_fat_g:15});assert.equal(addedManual.status,200);
  const stale=await api(page,'PUT',`/meal-plans/${week}/items`,{expected_revision:plan.revision,items:[]});assert.equal(stale.status,409);check('stale plan replacement rejected');
  await page.reload();await ready(page);
  nutrition=(await api(page,'GET',`/meal-plans/${week}/nutrition`)).body;
  assert.deepEqual(nutrition.total,{kcal:1435.1,protein_g:146.7,carbs_g:85.8,fat_g:53.6});
  assert.equal((await api(page,'GET',`/meal-plans/${week}/shopping-list`)).body.items.length,3);check('manual meal affects nutrition and not procurement');
  // Exercise UI replacement and preserve the hidden manual breakfast.
  await view(page,'planner');
  const lunch=page.locator(`.planned-meal`).first();
  await lunch.locator('[data-action="remove-meal"]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-action="new-recipe"]').disabled);
  plan=(await api(page,'GET',`/meal-plans/${week}`)).body;
  assert.ok(plan.items.some(item=>item.input_mode==='manual'));assert.equal(plan.items.length,2);check('UI replacement preserves manual breakfast');
  await addMeal(page,chicken,2,'lunch');
  // Mutating current baseline must leave the previous week's snapshot stable.
  const snapshot=plan.target;
  const changed=await api(page,'PUT','/profile/baseline',{...Object.fromEntries(['sex','age','height_cm','weight_kg','activity_factor','goal'].map(key=>[key,baseline.body[key]])),target_kcal:1800,protein_g:120,carbs_g:200,fat_g:60});assert.equal(changed.status,200);
  assert.deepEqual((await api(page,'GET',`/meal-plans/${week}`)).body.target,snapshot);check('plan target snapshot survives baseline change');
  await page.reload();await ready(page);check('refresh restores cloud data');
  const freshContext=await browser.newContext({viewport:{width:375,height:812}});
  const fresh=await freshContext.newPage();pages.push(fresh);fresh.on('pageerror',e=>errors.push(e.message));
  await fresh.goto(base.replace('127.0.0.1','localhost'));await login(fresh,accounts[0]);
  assert.equal((await api(fresh,'GET','/recipes')).body.total,2);
  assert.equal((await api(fresh,'GET',`/meal-plans/${week}`)).body.items.length,3);check('independent origin and browser storage restore A');
  await logout(page);
  assert.ok(!(await page.locator('.app-shell').textContent()).includes(chicken.name));
  await page.locator('[data-auth-mode="signup"]').click();
  await page.locator('#auth-email').fill(accounts[1].email);
  await page.locator('#auth-password').fill(accounts[1].password);
  await page.locator('#auth-password-confirm').fill(accounts[1].password);
  const signupResponse=page.waitForResponse(r=>r.url().includes('/auth/v1/signup')&&r.request().method()==='POST');
  await page.locator('#auth-submit-button').click();
  const bBody=await (await signupResponse).json();accounts[1].id=bBody.user?.id||bBody.id;manifest();
  await ready(page);
  assert.equal((await api(page,'GET','/recipes')).body.total,0);
  assert.equal((await api(page,'GET','/profile/baseline')).status,404);
  assert.equal((await api(page,'GET',`/meal-plans/${week}`)).status,404);
  assert.ok(!(await page.locator('.app-shell').textContent()).includes(chicken.name));check('A logout then B signup has no A business data');
  const bToken = await page.evaluate(() => window.MealPrepAuth.getAccessToken());
  const bRequest = page.waitForRequest(request => request.url().endsWith(`/api/v1/recipes/${chicken.id}`) && request.method() === 'GET');
  assert.equal((await api(page,'GET',`/recipes/${chicken.id}`)).status,404);
  assert.ok((await bRequest).headers().authorization === `Bearer ${bToken}`, 'Cross-account request must send B Bearer credentials');
  assert.equal((await api(page,'PATCH',`/recipes/${chicken.id}`,{name:'forbidden'})).status,404);
  assert.equal((await api(page,'DELETE',`/recipes/${chicken.id}`)).status,404);check('cross-account API read edit archive rejected');
  await swaggerCrossAccount(page,chicken.id);
  await page.screenshot({path:path.join(artifacts,'account-b-empty-375px.png'),fullPage:true});
  await logout(page);await login(page,accounts[0],true);
  assert.equal((await api(page,'GET','/recipes')).body.total,2);check('A relogin restores own data');
  assert.equal((await api(page,'GET',`/recipes/${chicken.id}`)).body.name,chicken.name);
  await view(page,'planner');
  await page.screenshot({path:path.join(artifacts,'planner-restored-375px.png'),fullPage:true});
  const width=await page.evaluate(()=>({viewport:innerWidth,content:document.documentElement.scrollWidth}));assert.equal(width.content,width.viewport);check('375px planner has no horizontal overflow',width);
  assert.deepEqual(errors,[]);check('no browser script errors');
  fs.writeFileSync(path.join(artifacts,'result.json'),JSON.stringify({run,project,results,week,accounts:accounts.map(({id,email})=>({id,email})),nutrition:nutrition.total,shopping},null,2));
})().catch(error=>{console.error(`FAIL ${error.message}`);process.exitCode=1;}).finally(async()=>{
  // Revoke all test sessions even when an assertion fails. Credentials remain only in the 0600 local manifest for exact cleanup.
  if (browser) {
    for (const page of pages) {
      try { await page.evaluate(async()=>{if(window.MealPrepAuth?.client) await window.MealPrepAuth.client.auth.signOut({scope:'global'});}); } catch (_) {}
    }
    await browser.close();
  }
  for(const account of accounts.filter(a=>a.id)) {
    try {
      const signed=await fetch(`${base}/api/v1/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:account.email,password:account.password})});
      const body=await signed.json();
      if(body.session?.access_token) await fetch(`${base}/api/v1/auth/logout`,{method:'POST',headers:{Authorization:`Bearer ${body.session.access_token}`}});
    } catch (_) {console.error('Session cleanup needs verification');}
  }
  console.log(JSON.stringify({cleanupRequired:true,run,users:accounts.map(({id,email})=>({id,email})),manifest:manifestFile,passed:results.length}));
});
