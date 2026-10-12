/* Filesystem-only E2E output management; never imports browser or database clients. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');
const {spawnSync} = require('node:child_process');
const projectRoot = path.resolve(__dirname, '../..');
function runId(value) {
  if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) throw new Error('Invalid E2E run ID');
  return value;
}
function outputRoot(env = process.env) {
  return path.resolve(projectRoot, env.MEAL_PREP_E2E_ARTIFACTS || 'reports/e2e');
}
// Resolve existing ancestors, including symlinks, before creating any output.
function physicalPath(filename) {
  try { return fs.realpathSync(filename); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    // A dangling symlink must not be treated as an ordinary missing directory.
    try { if (fs.lstatSync(filename).isSymbolicLink()) throw new Error('Dangling artifact symlink'); }
    catch (inner) { if (inner.code !== 'ENOENT') throw inner; }
    return path.join(physicalPath(path.dirname(filename)), path.basename(filename));
  }
}
function inside(root, filename) {
  const relative = path.relative(root, filename);
  return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}
function assertSafeDirectory(filename, root = projectRoot) {
  const actualRoot = fs.realpathSync(root);
  const actual = physicalPath(path.resolve(filename));
  if (!inside(actualRoot, actual)) return actual;
  const git = args => {
    const result = spawnSync('git', ['--no-optional-locks', '-C', actualRoot, ...args], {encoding:'utf8'});
    if (result.error || result.status === null) throw new Error('Cannot verify Git artifact protection');
    return result;
  };
  const tracked = git(['ls-files', '--cached', '-z']);
  if (tracked.status !== 0) throw new Error('Cannot verify tracked artifact files');
  for (const entry of tracked.stdout.split('\0').filter(Boolean)) {
    const file = path.join(actualRoot, entry);
    if (inside(actual, file) || inside(actual, physicalPath(file))) throw new Error('E2E output contains Git-tracked files: ' + filename);
  }
  // Require the directory itself to be ignored, not just selected extensions.
  const relative = path.relative(actualRoot, actual).split(path.sep).join('/');
  const ignored = git(['check-ignore', '--quiet', '--', relative + '/']);
  if (!relative || ignored.status !== 0) throw new Error('E2E output inside the worktree must be Git-ignored: ' + filename + '. Use reports/e2e or an external directory.');
  return actual;
}
function createRun(kind, env = process.env) {
  const run = crypto.randomUUID();
  assertSafeDirectory(outputRoot(env));
  const artifacts = assertSafeDirectory(path.join(outputRoot(env), run));
  fs.mkdirSync(path.dirname(artifacts), {recursive: true});
  fs.mkdirSync(artifacts); // Refuse collisions instead of overwriting old reports.
  fs.writeFileSync(path.join(artifacts, 'run.json'), JSON.stringify({run, kind}, null, 2), {flag: 'wx'});
  return {run, artifacts};
}
function assertPrivateManifest(filename) {
  const actual = fs.realpathSync(filename);
  const relative = path.relative(fs.realpathSync(projectRoot), actual);
  if (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative)) throw new Error('Credential manifest must be outside the project');
  return actual;
}
function createManifestFile(run) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'meal-prep-e2e-private-'));
  fs.chmodSync(directory, 0o700);
  const filename = path.join(directory, `${runId(run)}.json`);
  fs.writeFileSync(filename, '{}', {mode: 0o600, flag: 'wx'});
  assertPrivateManifest(filename);
  return filename;
}
function restoreRun(env = process.env) {
  if (!env.MEAL_PREP_E2E_MANIFEST) throw new Error('MEAL_PREP_E2E_MANIFEST is required; run hosted.cjs first');
  const filename = assertPrivateManifest(path.resolve(projectRoot, env.MEAL_PREP_E2E_MANIFEST));
  const manifest = JSON.parse(fs.readFileSync(filename, 'utf8'));
  const run = runId(manifest.run);
  const parent = env.MEAL_PREP_E2E_ARTIFACTS
    ? path.join(outputRoot(env), run)
    : manifest.artifacts || path.join(outputRoot(env), run);
  if (!path.isAbsolute(parent) || path.basename(parent) !== run) throw new Error('Invalid hosted artifact directory');
  assertSafeDirectory(parent);
  const metadata = JSON.parse(fs.readFileSync(path.join(parent, 'run.json'), 'utf8'));
  if (metadata.run !== run || metadata.kind !== 'hosted') throw new Error('Manifest does not match a hosted run');
  const restoreRoot = assertSafeDirectory(path.join(parent, 'restore'));
  fs.mkdirSync(restoreRoot, {recursive: true});
  const artifacts = assertSafeDirectory(path.join(restoreRoot, crypto.randomUUID()));
  fs.mkdirSync(artifacts);
  return {manifest, artifacts};
}
module.exports = {assertSafeDirectory, projectRoot, outputRoot, createRun, createManifestFile, restoreRun};
