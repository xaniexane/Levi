// LEVI VS Code extension — thin, local-first shell over the `levi` CLI.
// Zero telemetry, zero network: every command spawns the local CLI binary
// and streams its output into the "LEVI" output channel. Nothing leaves
// the machine except what the CLI itself does.
//
// Only requires: vscode, child_process. Plain JS — no build step.

const vscode = require('vscode');
const { spawn } = require('child_process');

let channel = null;

function out() {
  if (!channel) channel = vscode.window.createOutputChannel('LEVI');
  return channel;
}

function cliPath() {
  const v = vscode.workspace.getConfiguration('levi').get('cliPath');
  return (v && String(v).trim()) || 'levi';
}

function shellish(arg) {
  return /\s/.test(arg) ? JSON.stringify(arg) : arg;
}

function failStartup(ch, cli, err) {
  ch.appendLine(`[levi] failed to start '${cli}': ${err && err.message}`);
  if (err && err.code === 'ENOENT') {
    vscode.window.showErrorMessage(
      `LEVI: CLI not found at '${cli}'. Install LEVI and make sure it is on PATH, ` +
        `or set the 'levi.cliPath' setting to its full path.`
    );
  } else {
    vscode.window.showErrorMessage(
      `LEVI: could not start the CLI ('${cli}'): ${err && err.message}`
    );
  }
  return 127;
}

/**
 * Spawn `levi <args...>`, stream stdio into the LEVI output channel,
 * and report the outcome. Never fails silently.
 *
 * @param {string} label human-readable command label for messages
 * @param {string[]} args argv for the CLI
 * @param {string} missingHint shown when the CLI predates this subcommand
 */
function runLevi(label, args, missingHint) {
  const cli = cliPath();
  const ch = out();
  ch.show(true);
  ch.appendLine('');
  ch.appendLine(`$ ${[cli, ...args].map(shellish).join(' ')}`);

  return new Promise((resolve) => {
    let proc;
    try {
      proc = spawn(cli, args, { shell: false });
    } catch (err) {
      return resolve(failStartup(ch, cli, err));
    }
    let stderr = '';
    proc.stdout.on('data', (d) => ch.append(d.toString()));
    proc.stderr.on('data', (d) => {
      stderr += d.toString();
      ch.append(d.toString());
    });
    proc.on('error', (err) => resolve(failStartup(ch, cli, err)));
    proc.on('close', (code) => {
      ch.appendLine(`\n[levi] exit code ${code}`);
      if (code === 0) {
        vscode.window.showInformationMessage(
          `LEVI ${label}: done — receipt in the LEVI output channel.`
        );
      } else if (code === 2 && /invalid choice/i.test(stderr)) {
        vscode.window.showErrorMessage(
          `LEVI ${label}: your 'levi' CLI does not have this subcommand yet. ` +
            `Upgrade LEVI to a version that includes it, then retry. (${missingHint})`
        );
      } else {
        vscode.window.showErrorMessage(
          `LEVI ${label} failed (exit ${code}). See the LEVI output channel for details.`
        );
      }
      resolve(code);
    });
  });
}

async function councilBuild() {
  const task = await vscode.window.showInputBox({
    prompt: 'LEVI Council Build — describe the code task',
    placeHolder: 'e.g. add retry with backoff to the http client',
    ignoreFocusOut: true,
  });
  if (!task) return;
  await runLevi(
    'council build',
    ['council', 'build', '--task', task],
    'needs a LEVI CLI with the council feature (core/levi/council)'
  );
}

async function buildApp() {
  const desc = await vscode.window.showInputBox({
    prompt: 'LEVI Build App — describe the app to build',
    placeHolder: 'e.g. a habit tracker with a web UI and local storage',
    ignoreFocusOut: true,
  });
  if (!desc) return;
  await runLevi(
    'build',
    ['build', desc],
    'needs a LEVI CLI with the builder feature (core/levi/builder)'
  );
}

async function generateImage() {
  const prompt = await vscode.window.showInputBox({
    prompt: 'LEVI Generate Image — describe the image',
    placeHolder: 'e.g. a lighthouse at dusk, cinematic',
    ignoreFocusOut: true,
  });
  if (!prompt) return;
  const backend = await vscode.window.showQuickPick(
    ['auto', 'local', 'pollinations', 'sd'],
    { placeHolder: 'Image backend — auto/local is the offline procedural core (local-first)' }
  );
  if (!backend) return;
  const args = ['image', '--prompt', prompt, '--backend', backend];
  if (backend === 'pollinations') {
    const style = await vscode.window.showQuickPick(
      ['none', 'photo', 'anime', 'painting', 'product', 'cinematic'],
      { placeHolder: 'Style preset (pollinations quality tier)' }
    );
    if (!style) return;
    if (style !== 'none') args.push('--style', style);
  }
  await runLevi(
    'image',
    args,
    'needs a LEVI CLI with the media feature (core/levi/media)'
  );
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand('levi.councilBuild', councilBuild),
    vscode.commands.registerCommand('levi.buildApp', buildApp),
    vscode.commands.registerCommand('levi.generateImage', generateImage)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
