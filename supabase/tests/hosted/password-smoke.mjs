// Explicitly opt-in hosted Auth + Data API test. Never prints passwords or tokens.
// Test accounts are logged out in finally; delete only the emitted IDs via MCP.
import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';

const project = 'ziusvgtrmarbkmrvnpyq';
const base = process.env.SUPABASE_PROJECT_URL;
const key = process.env.SUPABASE_ANON_KEY;
assert.equal(process.env.MEAL_PLAN_HOSTED_TEST_PROJECT, project, 'explicit test project opt-in required');
assert.equal(base, `https://${project}.supabase.co`, 'unexpected project URL');
assert.ok(key, 'publishable key required');

const runId = randomUUID();
const accounts = [];
let passed = 0;
const check = name => { passed++; console.log(`PASS ${name}`); };

async function request(path, { method = 'GET', body, token, prefer } = {}) {
  const headers = { apikey: key, 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (prefer) headers.Prefer = prefer;
  const response = await fetch(`${base}${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const raw = await response.text();
  let data;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = null; }
  return { ok: response.ok, status: response.status, data };
}

async function success(path, options) {
  const result = await request(path, options);
  // Deliberately don't print Auth responses, which contain credentials.
  assert.ok(result.ok, `${options?.method ?? 'GET'} ${path.split('?')[0]} HTTP ${result.status}`);
  return result.data;
}

const rest = (resource, account, options = {}) => success(`/rest/v1/${resource}`, {
  ...options, token: account?.session.access_token,
});

try {
  const settings = await success('/auth/v1/settings');
  assert.equal(settings.mailer_autoconfirm, true, 'Confirm email is still enabled; no signup attempted');
  assert.equal(settings.external.email, true);
  assert.equal(settings.external.phone, false);
  assert.equal(settings.external.anonymous_users, false);
  assert.equal(settings.disable_signup, false);
  check('hosted policy: password signup without email confirmation');

  // Module 1: real Auth. Do not proceed to DB writes unless this module passes.
  for (const label of ['a', 'b']) {
    const account = {
      email: `meal-plan-smoke-${runId}-${label}@example.com`,
      password: `Mp9!${randomBytes(24).toString('base64url')}`,
      label,
    };
    accounts.push(account); // Keep cleanup information even if signup later fails.
    account.session = await success('/auth/v1/signup', {
      method: 'POST', body: { email: account.email, password: account.password,
        data: { display_name: `  smoke-${label}  `, meal_plan_test_run: runId } },
    });
    account.id = account.session.user?.id;
    assert.ok(account.id && account.session.access_token && account.session.refresh_token);
  }
  assert.notEqual(accounts[0].id, accounts[1].id);
  check('two email/password signups return immediate sessions');

  const wrong = await request('/auth/v1/token?grant_type=password', {
    method: 'POST', body: { email: accounts[0].email, password: 'DeliberatelyWrong9!' },
  });
  assert.equal(wrong.status, 400);
  assert.equal(wrong.data?.error_code, 'invalid_credentials');
  check('incorrect password rejected');

  for (const account of accounts) {
    account.session = await success('/auth/v1/token?grant_type=password', {
      method: 'POST', body: { email: account.email, password: account.password },
    });
    assert.equal(account.session.user.id, account.id);
  }
  check('password login preserves user identity');

  const a = accounts[0], b = accounts[1];
  a.session = await success('/auth/v1/token?grant_type=refresh_token', {
    method: 'POST', body: { refresh_token: a.session.refresh_token },
  });
  assert.ok(a.session.access_token && a.session.refresh_token);
  const restored = await success('/auth/v1/user', { token: a.session.access_token });
  assert.equal(restored.id, a.id);
  check('refresh and server-validated user restoration');

  // Module 2: Data API with real JWTs, not simulated SQL JWT claims.
  for (const account of accounts) {
    const profiles = await rest('profiles?select=id,display_name,target_kcal', account);
    assert.equal(profiles.length, 1);
    assert.equal(profiles[0].id, account.id);
    assert.equal(profiles[0].display_name, `smoke-${account.label}`);
    assert.equal(profiles[0].target_kcal, null);
  }
  check('automatic profile creation and non-vacuous per-user reads');

  await rest(`profiles?id=eq.${a.id}`, a, { method: 'PATCH', body: {
    target_kcal: 2000, protein_g: 150, carbs_g: 220, fat_g: 60,
    baseline_confirmed_at: new Date().toISOString(),
  } });
  const foreign = await rest(`profiles?id=eq.${a.id}&select=id`, b);
  assert.deepEqual(foreign, []);
  const foreignUpdate = await rest(`profiles?id=eq.${a.id}`, b, {
    method: 'PATCH', body: { target_kcal: 9999 }, prefer: 'return=representation',
  });
  assert.deepEqual(foreignUpdate, []);
  const own = await rest(`profiles?id=eq.${a.id}&select=target_kcal`, a);
  assert.equal(Number(own[0].target_kcal), 2000);
  check('own baseline writable, foreign profile hidden and unmodifiable');

  const foods = await rest('ingredients?select=id', a);
  assert.ok(foods.length > 0);
  const foodWrite = await request(`/rest/v1/ingredients?id=eq.${foods[0].id}`, {
    method: 'PATCH', token: a.session.access_token, body: { is_active: false },
  });
  assert.equal(foodWrite.status, 403);
  check('ingredients readable but not writable by clients');

  const planId = randomUUID();
  await rest('meal_plans', a, { method: 'POST', body: {
    id: planId, user_id: a.id, week_start: '2026-10-05',
    target_kcal: 2000, target_protein_g: 150, target_carbs_g: 220, target_fat_g: 60,
  } });
  await rest('meal_plan_items', a, { method: 'POST', body: [
    { meal_plan_id: planId, planned_date: '2026-10-05', meal_type: 'lunch',
      input_mode: 'manual', meal_name: 'smoke-one', manual_kcal: 500,
      manual_protein_g: 30, manual_carbs_g: 40, manual_fat_g: 20 },
    { meal_plan_id: planId, planned_date: '2026-10-05', meal_type: 'lunch',
      input_mode: 'manual', meal_name: 'smoke-two', manual_kcal: 200,
      manual_protein_g: 10, manual_carbs_g: 20, manual_fat_g: 8 },
  ] });
  const totals = await rest(`meal_plan_totals?meal_plan_id=eq.${planId}`, a);
  assert.equal(totals.length, 1);
  assert.equal(Number(totals[0].planned_kcal), 700);
  assert.equal(Number(totals[0].planned_item_count), 2);
  assert.deepEqual(await rest(`shopping_list_items?meal_plan_id=eq.${planId}`, a), []);
  await rest(`profiles?id=eq.${a.id}`, a, { method: 'PATCH', body: { target_kcal: 1900 } });
  const plans = await rest(`meal_plans?id=eq.${planId}&select=target_kcal`, a);
  assert.equal(Number(plans[0].target_kcal), 2000);
  check('weekly plan, multiple manual dishes, nutrition and stable target snapshot');

  for (const table of ['meal_plans', 'meal_plan_items', 'meal_plan_item_nutrition',
    'meal_plan_nutrition', 'meal_plan_totals', 'shopping_list_items']) {
    assert.deepEqual(await rest(`${table}?select=*`, b), [], `cross-user leak: ${table}`);
  }
  const crossInsert = await request('/rest/v1/meal_plans', {
    method: 'POST', token: b.session.access_token, body: {
      user_id: a.id, week_start: '2026-10-12', target_kcal: 2000,
      target_protein_g: 150, target_carbs_g: 220, target_fat_g: 60,
    },
  });
  assert.equal(crossInsert.status, 403);
  check('foreign plans and derived views hidden; cross-user insert rejected');

  const anonymous = await request('/rest/v1/profiles?select=id');
  assert.ok([401, 403].includes(anonymous.status));
  const forged = await request('/rest/v1/profiles?select=id', { token: 'invalid.jwt.token' });
  assert.equal(forged.status, 401);
  check('missing and invalid access tokens rejected');

  // Re-login after data updates must not recreate/overwrite the profile.
  a.session = await success('/auth/v1/token?grant_type=password', {
    method: 'POST', body: { email: a.email, password: a.password },
  });
  const again = await rest('profiles?select=id,target_kcal', a);
  assert.equal(again.length, 1);
  assert.equal(again[0].id, a.id);
  assert.equal(Number(again[0].target_kcal), 1900);
  check('re-login does not overwrite profile or baseline');

  // Module 3: revoke temporary sessions before privileged account cleanup.
  const refresh = a.session.refresh_token;
  await success('/auth/v1/logout?scope=global', { method: 'POST', token: a.session.access_token });
  a.loggedOut = true;
  const revoked = await request('/auth/v1/token?grant_type=refresh_token', {
    method: 'POST', body: { refresh_token: refresh },
  });
  assert.equal(revoked.status, 400);
  check('global logout revokes refresh token');
  console.log(`RESULT ${passed} checks passed`);
} catch (error) {
  // Error messages contain only our assertions/statuses, never response bodies.
  console.error(`FAIL ${error.message}`);
  process.exitCode = 1;
} finally {
  for (const account of accounts) {
    if (account.session?.access_token && !account.loggedOut) {
      try {
        await success('/auth/v1/logout?scope=global', {
          method: 'POST', token: account.session.access_token,
        });
        account.loggedOut = true;
      } catch { console.error(`WARN logout failed for temporary user ${account.id}`); process.exitCode = 1; }
    }
  }
  console.log(`CLEANUP ${JSON.stringify({ run_id: runId, accounts: accounts.map(a => ({
    id: a.id ?? null, email: a.email, logged_out: Boolean(a.loggedOut),
  })) })}`);
}
