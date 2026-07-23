#!/usr/bin/env node
/**
 * Cross-platform MCP server launcher for war3-tester
 *
 * Resolves Python interpreter intelligently:
 * - Windows native: python3 is often a Microsoft Store alias (App Execution Alias)
 *   that may open Store or exit abnormally. Skip WindowsApps paths, try python / py.
 * - Linux/macOS: python3 is the real interpreter, used directly.
 *
 * Resolution order: python3 (non-Store) -> python (non-Store) -> py launcher
 * Override: set PYTHON_BIN environment variable to force a specific interpreter.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

// --- Python interpreter resolution ----------------------------------------

function isWindowsStoreAlias(exePath) {
  if (!exePath) return true;
  const lower = exePath.toLowerCase();
  return lower.includes('windowsapps');
}

function findInPath(name) {
  try {
    const cmd = process.platform === 'win32'
      ? `where ${name} 2>nul`
      : `command -v ${name} 2>/dev/null`;
    const result = execSync(cmd, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
    const lines = result.split(/\r?\n/).filter(l => l.trim());

    if (process.platform === 'win32') {
      // Windows: `where python` may return multiple lines; Microsoft Store
      // aliases (WindowsApps) can appear at ANY position including the first.
      // Iterate all lines, return the first non-Store path.
      for (const line of lines) {
        if (!isWindowsStoreAlias(line)) return line;
      }
      return null; // all candidates are Store aliases
    }

    return lines[0] || null;
  } catch {
    return null;
  }
}

function resolvePython() {
  // 1. Environment variable override
  const envBin = process.env.PYTHON_BIN;
  if (envBin) return envBin;

  // 2. Try python3, python (skip Windows Store aliases)
  //    Return the FULL resolved path so spawn uses it directly — never let
  //    spawn re-search PATH (which could hit a WindowsApps Store alias).
  for (const cand of ['python3', 'python']) {
    const exePath = findInPath(cand);
    if (exePath && !isWindowsStoreAlias(exePath)) {
      return exePath;
    }
  }

  // 3. Try py launcher (Windows) — also return full path
  const pyPath = findInPath('py');
  if (pyPath) {
    return pyPath;
  }

  // 4. Fallback: let the error be visible
  return 'python3';
}

// --- 自动清理端口占用(避免多 Claude Code 实例 war3-tester MCP 8766 冲突) ---
// v0.19.5(候选④配套): spawn mcp_server 前,netstat 找占 8766 LISTENING 的旧进程并 taskkill。
// 这样多开 Claude Code 时,新实例自动接管 8766,旧实例 MCP 被 kill(单活,游戏端 8766 写死无法多实例)。
function cleanupPortOccupiers(port) {
  if (process.platform !== 'win32') return;
  try {
    const out = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`,
      { encoding: 'utf8', shell: 'cmd.exe' });
    const myPid = process.pid;
    out.trim().split(/\r?\n/).forEach(line => {
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && /^\d+$/.test(pid) && parseInt(pid, 10) !== myPid) {
        try {
          execSync(`taskkill /PID ${pid} /F`, { shell: 'cmd.exe' });
          console.error(`[war3-tester] 自动清理占用 ${port} 的旧 MCP 进程 PID=${pid}`);
        } catch (e) { /* 进程可能已退出,忽略 */ }
      }
    });
  } catch (e) {
    // netstat 无 LISTENING 输出(端口空闲)正常,忽略
  }
}

// --- Main -----------------------------------------------------------------

const pythonBin = resolvePython();
const serverScript = path.join(__dirname, '..', 'server', 'mcp_server.py');

// Build args: for py launcher, prepend -3 to select Python 3
// Detect py launcher by checking if the basename (without .exe) is 'py'
const binLower = path.basename(pythonBin).toLowerCase().replace(/\.exe$/i, '');
const isPyLauncher = binLower === 'py';
const args = isPyLauncher
  ? ['-3', serverScript]
  : [serverScript];

// spawn mcp_server 前,清理 8766 旧占用(多实例自动接管,不用手动杀进程)
cleanupPortOccupiers(8766);

const proc = spawn(pythonBin, args, {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env, PYTHONUTF8: '1', WAR3_PROJECT_ROOT: process.cwd() },
});

// 双向转发泵：node <-> python，保证 MCP 协议完整 + node 死亡时 python 收 EOF
// 使用 stream.pipe 自动处理背压（大响应不截断）
process.stdin.pipe(proc.stdin);
proc.stdout.pipe(process.stdout);
proc.stderr.pipe(process.stderr);

// 流 end/error 处理：父进程 stdin 关闭时关闭 python stdin，触发 python readline EOF
process.stdin.on('end', () => {
  try { proc.stdin.end(); } catch (_) {}
});
process.stdin.on('error', (err) => {
  console.error(`[war3-tester] stdin error: ${err.message}`);
  try { proc.stdin.end(); } catch (_) {}
});

proc.on('error', (err) => {
  console.error(`[war3-tester] Failed to start MCP server: ${err.message}`);
  console.error(`[war3-tester] Attempted interpreter: ${pythonBin}`);
  console.error(`[war3-tester] Set PYTHON_BIN env var to override (e.g. PYTHON_BIN=python)`);
  process.exit(1);
});

proc.on('exit', (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0));
});

// Forward termination signals
['SIGINT', 'SIGTERM'].forEach((sig) => {
  process.on(sig, () => {
    if (!proc.killed) proc.kill(sig);
  });
});
