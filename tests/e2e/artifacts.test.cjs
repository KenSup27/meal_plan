const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {projectRoot, outputRoot, createRun, createManifestFile, restoreRun} = require('./artifacts.cjs');
test('default and relative custom paths are independent of working directory', () => {
  const previous = process.cwd();
  try {
    process.chdir(os.tmpdir());
    assert.equal(outputRoot({}), path.join(projectRoot, 'reports/e2e'));
    assert.equal(outputRoot({MEAL_PREP_E2E_ARTIFACTS:'reports/custom'}), path.join(projectRoot, 'reports/custom'));
  } finally {process.chdir(previous);}
});
test('unique outputs, private manifest, and linked repeated restores', () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-path-test-'));
  let filename;
  try {
    const env = {MEAL_PREP_E2E_ARTIFACTS:base};
    const first = createRun('hosted', env), second = createRun('hosted', env);
    assert.notEqual(first.artifacts, second.artifacts);
    fs.writeFileSync(path.join(first.artifacts,'result.json'), 'preserved');
    filename = createManifestFile(first.run);
    assert.equal(fs.statSync(filename).mode & 0o777, 0o600);
    assert.equal(fs.statSync(path.dirname(filename)).mode & 0o777, 0o700);
    fs.writeFileSync(filename, JSON.stringify({...first, accounts:[]}));
    const restoreEnv = {MEAL_PREP_E2E_MANIFEST:filename};
    const a = restoreRun(restoreEnv), b = restoreRun(restoreEnv);
    assert.equal(path.dirname(a.artifacts), path.join(first.artifacts,'restore'));
    assert.notEqual(a.artifacts,b.artifacts);
    assert.equal(fs.readFileSync(path.join(first.artifacts,'result.json'),'utf8'), 'preserved');
    assert.equal(restoreRun({...restoreEnv,...env}).manifest.run,first.run);
    assert.throws(()=>restoreRun({}), /required/);
    assert.throws(()=>restoreRun({...restoreEnv,MEAL_PREP_E2E_ARTIFACTS:path.join(base,'missing')}));
    const marker = path.join(first.artifacts,'run.json');
    fs.writeFileSync(marker,JSON.stringify({run:second.run,kind:'hosted'}));
    assert.throws(()=>restoreRun(restoreEnv), /does not match/);
    fs.writeFileSync(filename, JSON.stringify({run:'../../escape'}));
    assert.throws(()=>restoreRun(restoreEnv), /Invalid E2E run ID/);
    assert.throws(()=>restoreRun({MEAL_PREP_E2E_MANIFEST:path.join(projectRoot,'README.md')}), /outside the project/);
  } finally {
    fs.rmSync(base,{recursive:true,force:true});
    if(filename)fs.rmSync(path.dirname(filename),{recursive:true,force:true});
  }
});

test('default and ignored custom runs are created; unignored traversal is rejected before writes', () => {
  const {assertSafeDirectory} = require('./artifacts.cjs');
  const first = createRun('regressions', {});
  let second;
  try {
    assert.equal(path.dirname(first.artifacts), fs.realpathSync(path.join(projectRoot,'reports/e2e')));
    second = createRun('regressions', {MEAL_PREP_E2E_ARTIFACTS:'reports/e2e/custom'});
    assert.ok(fs.existsSync(path.join(second.artifacts,'run.json')));
    const unsafe = 'unignored-e2e-' + require('node:crypto').randomUUID();
    assert.throws(()=>createRun('hosted',{MEAL_PREP_E2E_ARTIFACTS:unsafe}), /must be Git-ignored/);
    assert.throws(()=>createRun('hosted',{MEAL_PREP_E2E_ARTIFACTS:'reports/../'+unsafe}), /must be Git-ignored/);
    assert.equal(fs.existsSync(path.join(projectRoot,unsafe)),false);
    assert.throws(()=>assertSafeDirectory(path.join(projectRoot,'frontend/reports')), /must be Git-ignored/);
  } finally {
    fs.rmSync(first.artifacts,{recursive:true,force:true});
    if(second)fs.rmSync(second.artifacts,{recursive:true,force:true});
  }
});

test('physical paths, ignored directories and tracked files are checked in an isolated Git fixture', () => {
  const {assertSafeDirectory} = require('./artifacts.cjs');
  const {execFileSync} = require('node:child_process');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(),'e2e-git-safety-'));
  const repo = path.join(temp,'repo');
  fs.mkdirSync(repo);
  const git = args => execFileSync('git',['-C',repo,...args],{stdio:'pipe'});
  try {
    git(['init','--quiet']);
    fs.writeFileSync(path.join(repo,'.gitignore'), '/reports/\n');
    fs.mkdirSync(path.join(repo,'reports'));
    fs.mkdirSync(path.join(repo,'unsafe'));
    assert.doesNotThrow(()=>assertSafeDirectory(path.join(repo,'reports/new/run'),repo));
    fs.symlinkSync(path.join(repo,'unsafe'),path.join(repo,'reports/link'),'dir');
    assert.throws(()=>assertSafeDirectory(path.join(repo,'reports/link/run'),repo), /must be Git-ignored/);
    fs.symlinkSync(path.join(repo,'unsafe'),path.join(temp,'external-link'),'dir');
    assert.throws(()=>assertSafeDirectory(path.join(temp,'external-link/run'),repo), /must be Git-ignored/);
    fs.symlinkSync(path.join(temp,'missing'),path.join(repo,'reports/dangling'),'dir');
    assert.throws(()=>assertSafeDirectory(path.join(repo,'reports/dangling/run'),repo), /Dangling/);
    assert.equal(assertSafeDirectory(path.join(temp,'external/new'),repo),path.join(fs.realpathSync(temp),'external/new'));
    fs.writeFileSync(path.join(repo,'reports/tracked.json'),'{}');
    git(['add','-f','--','reports/tracked.json']);
    assert.throws(()=>assertSafeDirectory(path.join(repo,'reports'),repo), /Git-tracked/);
    assert.throws(()=>assertSafeDirectory(path.join(repo,'reports/tracked.json'),repo), /Git-tracked/);
    assert.doesNotThrow(()=>assertSafeDirectory(path.join(repo,'reports/untracked-run'),repo));
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('restore rejects an unignored manifest output before creating restore artifacts', () => {
  let filename;
  const directory = fs.mkdtempSync(path.join(projectRoot,'e2e-unsafe-fixture-'));
  try {
    const run = require('node:crypto').randomUUID();
    const parent = path.join(directory,run);
    fs.mkdirSync(parent);
    fs.writeFileSync(path.join(parent,'run.json'),JSON.stringify({run,kind:'hosted'}));
    filename = createManifestFile(run);
    fs.writeFileSync(filename,JSON.stringify({run,artifacts:parent}));
    assert.throws(()=>restoreRun({MEAL_PREP_E2E_MANIFEST:filename}), /must be Git-ignored/);
    assert.equal(fs.existsSync(path.join(parent,'restore')),false);
  } finally {
    fs.rmSync(directory,{recursive:true,force:true});
    if(filename)fs.rmSync(path.dirname(filename),{recursive:true,force:true});
  }
});
