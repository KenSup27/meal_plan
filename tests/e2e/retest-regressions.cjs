/* Deterministic DOM/browser regressions. Synthetic accounts only; no cloud writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.env.MEAL_PREP_E2E_URL || 'http://127.0.0.1:8022';
const artifacts = process.env.MEAL_PREP_E2E_ARTIFACTS;
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
if (artifacts) fs.mkdirSync(artifacts, {recursive:true});
const checks = [];
const check = name => { checks.push(name); console.log(`PASS ${name}`); };
const browserErrors = [];
let browser;

function syntheticSdk(options) {
  window.supabase = {createClient() {
    let callback, session = null;
    const control = window.__syntheticAuth = {calls:[], error:null, delay:false, noSession:false};
    control.refresh = () => callback?.('TOKEN_REFRESHED', {...session,access_token:'synthetic-refreshed-token'});
    async function authenticate(kind, {email}) {
      control.calls.push(kind);
      if (control.delay) await new Promise(resolve => { control.release = resolve; });
      if (control.error) { const error = control.error; control.error = null; return {error}; }
      if (control.noSession) return {data:{session:null},error:null};
      session = {access_token:'synthetic-token',user:{id:email,email}};
      callback?.('SIGNED_IN', session);
      return {data:{session},error:null};
    }
    return {auth:{
      onAuthStateChange(fn) { callback = fn; fn('INITIAL_SESSION', null); return {data:{subscription:{unsubscribe(){}}}}; },
      async getSession() {
        if (options.bootDelay) await new Promise(resolve => { control.releaseBoot = resolve; });
        return {data:{session:null},error:null};
      },
      signInWithPassword: credentials => authenticate('login', credentials),
      signUp: credentials => authenticate('signup', credentials),
      async signOut() { session = null; callback?.('SIGNED_OUT', null); return {error:null}; },
    }};
  }};
}

async function fixture(options = {}) {
  const context = await browser.newContext({viewport:{width:375,height:812}});
  const page = await context.newPage();
  page.on('pageerror', error => browserErrors.push(error.message));
  await page.route('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@*', route => route.fulfill({contentType:'application/javascript',body:options.noSdk ? '' : `(${syntheticSdk})(${JSON.stringify(options)});`}));
  await page.route('**/runtime-config.js', route => route.fulfill({contentType:'application/javascript',body:`window.MEAL_PREP_SUPABASE=${options.noConfig ? '{}' : JSON.stringify({url:'https://synthetic.invalid',publishableKey:'sb_publishable_synthetic'})};`}));
  const control = {write:'503',readFailure:false,writes:0,hold:false};
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    if (request.method() === 'POST' && pathname === '/api/v1/recipes') {
      control.writes++;
      if (control.hold) await new Promise(resolve => { control.releaseWrite = resolve; });
      if (control.write === 'refused') return route.continue({url:`http://127.0.0.1:${control.closedPort}/api/v1/recipes`});
      if (control.write === 'offline') return route.continue();
      return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'服务暂不可用，请稍后重试'})}).catch(() => {});
    }
    if (control.readFailure) return route.abort('connectionrefused');
    let status = 200, body;
    if (pathname === '/api/v1/ingredients') body = {total:1,items:[{id:1,name:'鸡胸肉',category:'meat',kcal_per_100g:133,protein_per_100g:23.3,carbs_per_100g:0,fat_per_100g:4.7}]};
    else if (pathname === '/api/v1/recipes') body = {total:0,items:[]};
    else { status = 404; body = {detail:'not created'}; }
    return route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto(base);
  await page.locator('#auth-gate').waitFor({state:'visible'});
  return {context,page,control};
}
async function fill(page) {
  await page.locator('#auth-email').fill('synthetic@example.invalid');
  await page.locator('#auth-password').fill('SyntheticOnly123!');
}
async function ready(page) {
  await page.waitForFunction(() => document.querySelector('#health-text').textContent === '已连接 · 云端保存');
}
async function login(page) { await fill(page); await page.locator('#auth-submit-button').click(); await ready(page); }
async function logout(page) {
  await page.locator('#logout-button').click();
  await page.locator('#auth-gate').waitFor({state:'visible'});
  assert.equal(await page.locator('#auth-submit-button').isDisabled(), false);
  assert.ok(!(await page.locator('#auth-submit-button').textContent()).includes('处理中'));
}
async function screenshot(page, name) {
  if (artifacts) await page.screenshot({path:path.join(artifacts, name),fullPage:true});
}

(async () => {
  browser = await chromium.launch({channel:process.env.MEAL_PREP_E2E_BROWSER || 'chrome',headless:true});
  const {page,context,control} = await fixture();
  await login(page); await logout(page); await login(page);
  assert.deepEqual(await page.evaluate(() => window.__syntheticAuth.calls), ['login','login']);
  check('login logout direct relogin without mode selection or refresh');
  await logout(page);
  await page.locator('[data-auth-mode="signup"]').click(); await fill(page);
  await page.locator('#auth-password-confirm').fill('SyntheticOnly123!');
  await page.locator('#auth-submit-button').click(); await ready(page); await logout(page);
  assert.ok((await page.locator('#auth-submit-button').textContent()).includes('创建账号'));
  check('successful signup then logout resets the submit button');
  await page.locator('[data-auth-mode="login"]').click();
  await page.evaluate(() => { window.__syntheticAuth.error = {message:'Invalid login credentials'}; });
  await fill(page); await page.locator('#auth-submit-button').click();
  await page.waitForFunction(() => document.querySelector('#auth-feedback').textContent.includes('邮箱或密码不正确'));
  assert.equal(await page.locator('#auth-submit-button').isDisabled(), false);
  await login(page); await logout(page); check('wrong password followed by direct retry');
  await page.evaluate(() => { window.__syntheticAuth.error = {name:'AuthRetryableFetchError',message:'Failed to fetch'}; });
  await fill(page); await page.locator('#auth-submit-button').click();
  await page.waitForFunction(() => document.querySelector('#auth-feedback').textContent.includes('无法连接服务'));
  assert.equal(await page.locator('#auth-submit-button').isDisabled(), false);
  check('SDK connection failures use Chinese feedback and release submit');
  const callsBeforePending = await page.evaluate(() => window.__syntheticAuth.calls.length);
  await page.evaluate(() => { window.__syntheticAuth.delay = true; });
  await fill(page); await page.locator('#auth-submit-button').click();
  await page.waitForFunction(() => Boolean(window.__syntheticAuth.release));
  assert.equal(await page.locator('[data-auth-mode="signup"]').isDisabled(), true);
  await page.evaluate(() => {
    document.querySelector('[data-auth-mode="signup"]').dispatchEvent(new MouseEvent('click', {bubbles:true}));
    document.querySelector('#auth-form').dispatchEvent(new Event('submit', {cancelable:true,bubbles:true}));
  });
  assert.equal(await page.locator('#auth-password-confirm').isVisible(), false);
  assert.equal(await page.locator('#auth-submit-button').textContent(), '处理中…');
  assert.equal(await page.evaluate(() => window.__syntheticAuth.calls.length), callsBeforePending + 1);
  await page.evaluate(() => { window.__syntheticAuth.delay = false; window.__syntheticAuth.release(); });
  await ready(page); check('pending submission blocks duplicate submits and mode changes');
  await screenshot(page, 'authenticated-375.png');
  await page.locator('.nav-item[data-view="recipes"]').click();
  await page.locator('[data-action="new-recipe"]').click();
  const draft = '连接中断时保留的合成草稿';
  await page.locator('#recipe-form [name="name"]').fill(draft);
  await page.evaluate(() => window.__syntheticAuth.refresh());
  assert.equal(await page.locator('#recipe-form [name="name"]').inputValue(), draft);
  check('same-account token refresh preserves the open recipe draft');
  await page.locator('#recipe-form button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('#toast').textContent === '服务暂不可用，请稍后重试');
  assert.equal(await page.locator('#toast').getAttribute('data-tone'), 'error');
  check('HTTP 503 keeps its existing server message');
  // A real TCP listener is stopped; Chrome then connects to that now-closed port.
  const listener = http.createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  control.closedPort = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  for (const mode of ['refused','offline']) {
    control.write = mode;
    if (mode === 'offline') await context.setOffline(true);
    const before = control.writes;
    const failed = page.waitForEvent('requestfailed', {predicate:request => request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/recipes'});
    await page.locator('#recipe-form button[type="submit"]').click();
    assert.equal((await failed).failure().errorText, mode === 'refused' ? 'net::ERR_CONNECTION_REFUSED' : 'net::ERR_INTERNET_DISCONNECTED');
    await page.waitForFunction(() => document.querySelector('#toast').textContent.includes('保存结果尚未确认'));
    await page.waitForFunction(() => !document.querySelector('#recipe-form button[type="submit"]').disabled);
    assert.equal(await page.locator('#toast').getAttribute('data-tone'), 'error');
    assert.equal(await page.locator('#recipe-form [name="name"]').inputValue(), draft);
    assert.equal(control.writes, before + 1);
    if (mode === 'offline') await context.setOffline(false);
    check(`${mode}: Chinese uncertain-write feedback, preserved draft, no retry or success`);
    await screenshot(page, `${mode}-375.png`);
  }
  control.write = '503'; control.hold = true;
  await page.locator('#recipe-form button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('#recipe-form button[type="submit"]').disabled);
  while (!control.releaseWrite) await new Promise(resolve => setImmediate(resolve));
  await logout(page); control.releaseWrite();
  assert.equal(await page.locator('#health-text').textContent(), '请先登录');
  assert.equal(await page.locator('#toast').textContent(), '');
  check('logout cancels a pending business request without stale error feedback');
  await context.close();

  for (const option of ['noConfig','noSdk']) {
    const {page,context} = await fixture({[option]:true});
    for (const mode of ['signup','login']) {
      await page.locator(`[data-auth-mode="${mode}"]`).click();
      assert.equal(await page.locator('#auth-submit-button').isDisabled(), true);
    }
    check(`${option}: mode selection cannot enable authentication`);
    await context.close();
  }
  {
    const {page,context,control} = await fixture({bootDelay:true});
    await login(page); await page.evaluate(() => window.__syntheticAuth.releaseBoot());
    await ready(page); assert.equal(await page.locator('#auth-gate').isVisible(), false);
    check('late initial getSession result cannot overwrite successful login');
    await logout(page); control.readFailure = true;
    await fill(page); await page.locator('#auth-submit-button').click();
    await page.waitForFunction(() => document.querySelector('#health-text').textContent.includes('无法连接服务'));
    assert.equal(await page.locator('[data-action="retry-load"]').isDisabled(), false);
    control.readFailure = false; await page.locator('[data-action="retry-load"]').click(); await ready(page);
    check('read connection failure has Chinese feedback and retry restores data');
    await context.close();
  }
  {
    const {page,context} = await fixture();
    await page.locator('[data-auth-mode="signup"]').click();
    await page.evaluate(() => { window.__syntheticAuth.noSession = true; });
    await fill(page); await page.locator('#auth-password-confirm').fill('SyntheticOnly123!');
    await page.locator('#auth-submit-button').click();
    await page.waitForFunction(() => document.querySelector('#auth-feedback').textContent.includes('注册成功'));
    assert.equal(await page.locator('#auth-password-confirm').isVisible(), false);
    assert.equal(await page.locator('#auth-submit-button').isDisabled(), false);
    check('confirmation-only registration restores login mode and button');
    await context.close();
  }
  const docs = await browser.newPage();
  docs.on('pageerror', error => browserErrors.push(error.message));
  await docs.goto(`${base}/docs`);
  await docs.locator('.auth-wrapper .authorize').click();
  await docs.locator('.dialog-ux input').fill('synthetic-swagger-token');
  await docs.locator('.dialog-ux').getByRole('button', {name:'Apply credentials',exact:true}).click();
  await docs.locator('.dialog-ux').getByRole('button', {name:'Close',exact:true}).click();
  const operation = docs.locator('#operations-default-recipe_get_api_v1_recipes__recipe_id__get');
  await operation.locator('.opblock-summary').click();
  await operation.getByRole('button', {name:'Try it out'}).click();
  await operation.locator('input[placeholder="recipe_id"]').fill('00000000-0000-0000-0000-000000000001');
  const sent = docs.waitForRequest(request => request.url().includes('/api/v1/recipes/00000000-0000-0000-0000-000000000001'));
  await operation.getByRole('button', {name:'Execute',exact:true}).click();
  assert.equal((await sent).headers().authorization, 'Bearer synthetic-swagger-token');
  check('actual Swagger Authorize request sends exactly one correct Bearer prefix');
  await screenshot(docs, 'swagger-authorized.png');
  assert.deepEqual(browserErrors, []); check('no browser script errors');
  if (artifacts) fs.writeFileSync(path.join(artifacts,'regression-result.json'), JSON.stringify({mode:'synthetic Auth/business responses, actual DOM and Swagger UI',checks},null,2));
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); });
