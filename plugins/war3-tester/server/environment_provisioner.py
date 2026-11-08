#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnvironmentProvisioner - 测试与 Named Pipe Agent 环境安装/诊断/修复模块

职责：
- 支持三种模式（mode）：
  - 'repair'（默认）：检测并安装/覆盖修复所有缺失或损坏的组件
  - 'install'：仅安装缺失组件（已存在的 Lua 脚本不覆盖）
  - 'check'：只读体检（Doctor 模式），检查各组件完整性并输出诊断报告，不改文件
- 支持七大组件（components）：
  1. 'socket'       : 部署 socket.dll + libwinpthread-1.dll 到项目 map/ 目录
  2. 'http'         : 检查/安装 Flask + werkzeug Python 依赖
  3. 'nopause'      : 部署 nopause.asi 到 War3 安装目录
  4. 'agent_bridge' : 部署 agent_bridge.dll 到项目 map/ 目录（及 War3 目录 agent_bridge.asi）
  5. 'agent_lua'    : 部署/修复 <test_dir>/agent/*.lua（含 oracle/*.lua）及 _war3_tester 断言/mock 库
  6. 'entry_hook'   : 检查/修复 <test_dir>/init.lua 的 '-test on' / '-agent on' 聊天热启动钩子并清理残留 _test_off.lua
  7. 'plugin_sync'  : 将插件源码同步至 Claude 插件缓存目录与全局技能目录（可选组件）

零反向依赖：只依赖标准库 + 收 config/plugin_root 参数，不引用 mcp_server / test_batch_runner / http_receiver
"""

import sys
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime


AGENT_LUA_FILES = [
    "init.lua",
    "bridge.lua",
    "protocol.lua",
    "runtime.lua",
    "observe.lua",
    "actions.lua",
    "setup.lua",
    "events.lua",
    "entity_ref.lua",
    "oracle/init.lua",
    "oracle/numeric.lua",
    "oracle/runtime_error.lua",
    "oracle/stuck.lua",
    "oracle/consistency.lua",
    "oracle/leak.lua",
]

CHAT_HOOK_SNIPPET = """-- ============================================================================
-- 全局聊天命令：-test on / -test off / -agent on（由 war3-tester 自动注入/修复）
-- ============================================================================
_G.__auto_test_enabled = false

local _chat_switch_trg = war3.CreateTrigger(function()
    local msg = GetEventPlayerChatString()
    if not msg then return end

    local cmd = msg:match("^%-test%s+(%S+)") or msg:match("^%-agent%s+(%S+)")
    if cmd == 'off' then
        _G.__auto_test_enabled = false
        DisplayTextToPlayer(GetTriggerPlayer(), 0, 0, "[AutoTest] 自动测试已关闭")
    elseif cmd == 'on' then
        _G.__auto_test_enabled = true
        DisplayTextToPlayer(GetTriggerPlayer(), 0, 0, "[AutoTest] 自动测试已开启")
        pcall(function()
            local ag = require('@@AGENT_INIT_MODULE@@')
            if ag and ag.start then
                ag.start(true)
            end
        end)
    end
end)
for i = 0, 15 do
    jass.TriggerRegisterPlayerChatEvent(_chat_switch_trg, Player(i), '', false)
end
"""


class EnvironmentProvisioner:
    """测试与 Agent 环境组件安装、体检与修复器。"""

    DEFAULT_COMPONENTS = [
        "socket",
        "http",
        "nopause",
        "agent_bridge",
        "agent_lua",
        "entry_hook",
    ]

    def __init__(self, config, plugin_root, logger=None):
        self.config = config
        self.plugin_root = Path(plugin_root)
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _safe_copy_binary(src: Path, dst: Path) -> str:
        """
        安全拷贝二进制 DLL/ASI 文件：
        - 若目标文件已存在且内容完全一致，直接跳过写入（避免 War3.exe 运行中锁定文件报 WinError 32）
        - 若目标文件被运行中的 War3.exe 占用锁定，返回提示信息而不抛异常阻断
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            try:
                if src.read_bytes() == dst.read_bytes():
                    return f"{dst} (已是最新)"
            except Exception:
                pass
        try:
            shutil.copy2(src, dst)
            return str(dst)
        except PermissionError as e:
            if dst.exists():
                return f"{dst} (游戏运行中已加载占用，跳过覆盖)"
            raise e

    def _resolve_test_dir(self, project_root: Path) -> Path:
        """解析项目的测试脚本目录（优先走 config.get_test_dir_path，回退常见路径探测）"""
        if hasattr(self.config, "get_test_dir_path"):
            try:
                td = self.config.get_test_dir_path(project_root)
                if td is not None:
                    return Path(td)
            except Exception:
                pass
        # 探测常见测试目录结构
        candidates = [
            project_root / "map" / "script" / "src" / "auto-test",
            project_root / "script" / "src" / "auto-test",
            project_root / "auto-test",
        ]
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    def _resolve_module_prefix(self, project_root: Path, test_dir: Path) -> str:
        """解析项目的 Lua require 模块前缀"""
        prefix = getattr(self.config, "test_module_prefix", None)
        if prefix:
            return prefix
        try:
            rel = test_dir.relative_to(project_root).as_posix()
            if rel.startswith("map/"):
                rel = rel[len("map/"):]
            return rel.replace("/", ".") + "."
        except Exception:
            return "script.src.auto-test."

    def setup(self, arguments: dict) -> dict:
        """
        安装、检查或修复测试环境组件。

        Args:
            arguments:
              - source_dir: 目标项目根目录
              - mode: 'repair'（默认）| 'install' | 'check'
              - components: 组件列表
              - war3_dir: War3 安装目录
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = arguments.get("mode", "repair")
        if mode not in ("repair", "install", "check"):
            mode = "repair"
        is_check = (mode == "check")

        source_dir = arguments.get("source_dir")
        components = arguments.get("components", self.DEFAULT_COMPONENTS)
        war3_dir = arguments.get("war3_dir")

        if source_dir:
            project_root = Path(source_dir)
        elif getattr(self.config, "project_root", None):
            project_root = Path(self.config.project_root)
        else:
            project_root = None

        if not war3_dir and getattr(self.config, "war3_log_dir", None):
            try:
                inferred_war3_dir = Path(self.config.war3_log_dir).parent
                if inferred_war3_dir.exists():
                    war3_dir = str(inferred_war3_dir)
            except Exception:
                pass

        plugin_root = self.plugin_root
        results = []

        # 1. socket 组件
        if "socket" in components:
            try:
                if not project_root:
                    results.append({"component": "socket", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                else:
                    socket_src_dir = plugin_root / "bin" / "socket"
                    socket_dst_dir = project_root / "map"
                    dll_names = ["socket.dll", "libwinpthread-1.dll"]
                    if is_check:
                        missing = [d for d in dll_names if not (socket_dst_dir / d).exists()]
                        if not missing:
                            results.append({"component": "socket", "status": "success", "message": f"检查通过：{socket_dst_dir} 下 socket.dll 与依赖齐全"})
                        else:
                            results.append({"component": "socket", "status": "failed", "message": f"缺失文件：{missing}（位于 {socket_dst_dir}）"})
                    else:
                        if not socket_src_dir.exists():
                            results.append({"component": "socket", "status": "failed", "message": f"插件 bin/socket 目录不存在：{socket_src_dir}"})
                        else:
                            socket_dst_dir.mkdir(parents=True, exist_ok=True)
                            copied_files = []
                            for dll_name in dll_names:
                                src = socket_src_dir / dll_name
                                dst = socket_dst_dir / dll_name
                                if src.exists():
                                    copied_files.append(self._safe_copy_binary(src, dst))
                            if copied_files:
                                results.append({"component": "socket", "status": "success", "message": f"已拷贝 {len(copied_files)} 个文件到 {socket_dst_dir}", "files": copied_files})
                            else:
                                results.append({"component": "socket", "status": "failed", "message": "未找到 socket.dll 或 libwinpthread-1.dll"})
            except Exception as e:
                results.append({"component": "socket", "status": "failed", "message": f"处理失败：{e}"})

        # 2. http 组件
        if "http" in components:
            try:
                if is_check:
                    proc = subprocess.run([sys.executable, "-c", "import flask, werkzeug"], capture_output=True, text=True, timeout=15)
                    if proc.returncode == 0:
                        results.append({"component": "http", "status": "success", "message": "检查通过：flask + werkzeug 已安装"})
                    else:
                        results.append({"component": "http", "status": "failed", "message": "未安装 flask 或 werkzeug"})
                else:
                    proc = subprocess.run([sys.executable, "-m", "pip", "install", "flask", "werkzeug"], capture_output=True, text=True, timeout=120)
                    if proc.returncode == 0:
                        results.append({"component": "http", "status": "success", "message": "flask + werkzeug 已安装（或已是最新）"})
                    else:
                        results.append({"component": "http", "status": "failed", "message": f"pip install 失败：{proc.stderr}"})
            except subprocess.TimeoutExpired:
                results.append({"component": "http", "status": "failed", "message": "pip 操作超时"})
            except Exception as e:
                results.append({"component": "http", "status": "failed", "message": f"http 组件异常：{e}"})

        # 3. nopause 组件
        if "nopause" in components:
            try:
                if not war3_dir:
                    results.append({"component": "nopause", "status": "skipped", "message": "未指定 war3_dir 且无法从 config.war3_log_dir 反推，请传参 war3_dir"})
                else:
                    nopause_src = plugin_root / "bin" / "nopause.asi"
                    nopause_dst = Path(war3_dir) / "nopause.asi"
                    if is_check:
                        if nopause_dst.exists():
                            results.append({"component": "nopause", "status": "success", "message": f"检查通过：{nopause_dst} 已存在"})
                        else:
                            results.append({"component": "nopause", "status": "failed", "message": f"缺失文件：{nopause_dst}"})
                    else:
                        if not nopause_src.exists():
                            results.append({"component": "nopause", "status": "failed", "message": f"插件 bin/nopause.asi 不存在：{nopause_src}"})
                        else:
                            info = self._safe_copy_binary(nopause_src, nopause_dst)
                            results.append({"component": "nopause", "status": "success", "message": f"已就绪：{info}"})
            except Exception as e:
                results.append({"component": "nopause", "status": "failed", "message": f"处理失败：{e}"})

        # 4. agent_bridge 组件
        if "agent_bridge" in components:
            try:
                if not project_root:
                    results.append({"component": "agent_bridge", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                else:
                    bridge_src = plugin_root / "bin" / "agent_bridge.dll"
                    bridge_dst = project_root / "map" / "agent_bridge.dll"
                    if is_check:
                        if bridge_dst.exists():
                            results.append({"component": "agent_bridge", "status": "success", "message": f"检查通过：{bridge_dst} 已存在 ({bridge_dst.stat().st_size} bytes)"})
                        else:
                            results.append({"component": "agent_bridge", "status": "failed", "message": f"缺失文件：{bridge_dst}"})
                    else:
                        if not bridge_src.exists():
                            results.append({"component": "agent_bridge", "status": "failed", "message": f"插件 bin/agent_bridge.dll 不存在：{bridge_src}"})
                        else:
                            copied = [self._safe_copy_binary(bridge_src, bridge_dst)]
                            if war3_dir and Path(war3_dir).exists():
                                asi_dst = Path(war3_dir) / "agent_bridge.asi"
                                copied.append(self._safe_copy_binary(bridge_src, asi_dst))
                            results.append({"component": "agent_bridge", "status": "success", "message": f"已部署/校验 agent_bridge.dll 到 {bridge_dst}", "files": copied})
            except Exception as e:
                results.append({"component": "agent_bridge", "status": "failed", "message": f"处理失败：{e}"})

        # 5. agent_lua 组件（游戏内 Lua Agent 运行时 + 五大 Oracle + 断言/mock 库）
        if "agent_lua" in components:
            try:
                if not project_root:
                    results.append({"component": "agent_lua", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                else:
                    test_dir = self._resolve_test_dir(project_root)
                    prefix = self._resolve_module_prefix(project_root, test_dir)
                    agent_src_dir = plugin_root / "assets" / "agent"
                    agent_dst_dir = test_dir / "agent"
                    wt_dst_dir = test_dir / "_war3_tester"

                    if is_check:
                        missing_lua = [rel for rel in AGENT_LUA_FILES if not (agent_dst_dir / rel).exists()]
                        if not missing_lua:
                            results.append({"component": "agent_lua", "status": "success", "message": f"检查通过：{agent_dst_dir} 下 {len(AGENT_LUA_FILES)} 个 Lua Agent 模块齐全"})
                        else:
                            results.append({"component": "agent_lua", "status": "failed", "message": f"缺失 Agent Lua 模块 ({len(missing_lua)} 个)：{missing_lua}"})
                    else:
                        if not agent_src_dir.exists():
                            results.append({"component": "agent_lua", "status": "failed", "message": f"插件 assets/agent 目录不存在：{agent_src_dir}"})
                        else:
                            deployed_files = []
                            skipped_existing = 0
                            for rel in AGENT_LUA_FILES:
                                src_file = agent_src_dir / rel
                                dst_file = agent_dst_dir / rel
                                if not src_file.exists():
                                    continue
                                if mode == "install" and dst_file.exists():
                                    skipped_existing += 1
                                    continue
                                dst_file.parent.mkdir(parents=True, exist_ok=True)
                                content = src_file.read_text(encoding="utf-8")
                                if prefix != "script.src.auto-test.":
                                    content = content.replace("script.src.auto-test.", prefix)
                                dst_file.write_text(content, encoding="utf-8")
                                deployed_files.append(str(dst_file))

                            # 同时部署 _war3_tester/assertions.lua 与 jass_mock.lua
                            wt_dst_dir.mkdir(parents=True, exist_ok=True)
                            server_dir = plugin_root / "server"
                            for helper_name in ["assertions.lua", "jass_mock.lua"]:
                                h_src = server_dir / helper_name
                                h_dst = wt_dst_dir / helper_name
                                if h_src.exists():
                                    shutil.copy2(h_src, h_dst)
                                    deployed_files.append(str(h_dst))

                            msg = f"已部署/修复 {len(deployed_files)} 个 Lua 文件到 {agent_dst_dir}"
                            if skipped_existing:
                                msg += f"（保留已存在文件 {skipped_existing} 个）"
                            results.append({"component": "agent_lua", "status": "success", "message": msg, "files": deployed_files[:8]})
            except Exception as e:
                results.append({"component": "agent_lua", "status": "failed", "message": f"处理失败：{e}"})

        # 6. entry_hook 组件（检查/修复 auto-test/init.lua 的 -test on 聊天钩子 & 清理 _test_off.lua）
        if "entry_hook" in components:
            try:
                if not project_root:
                    results.append({"component": "entry_hook", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                else:
                    test_dir = self._resolve_test_dir(project_root)
                    prefix = self._resolve_module_prefix(project_root, test_dir)
                    init_lua = test_dir / "init.lua"
                    test_off = test_dir / "_war3_tester" / "_test_off.lua"

                    if is_check:
                        issues = []
                        if not init_lua.exists():
                            issues.append(f"缺少入口文件 {init_lua}")
                        else:
                            init_text = init_lua.read_text(encoding="utf-8", errors="ignore")
                            if "agent.init" not in init_text:
                                issues.append("init.lua 未包含 agent.init 聊天启动钩子 (-test on)")
                        if test_off.exists():
                            issues.append(f"存在关闭标志 {test_off}（自动测试当前处于禁用状态）")
                        if not issues:
                            results.append({"component": "entry_hook", "status": "success", "message": f"检查通过：{init_lua} 已包含 -test on 钩子且无 _test_off 阻塞"})
                        else:
                            results.append({"component": "entry_hook", "status": "failed", "message": "；".join(issues)})
                    else:
                        actions_taken = []
                        if test_off.exists():
                            test_off.unlink()
                            actions_taken.append("已清除 _war3_tester/_test_off.lua 关闭标志")

                        agent_init_mod = f"{prefix}agent.init"
                        hook_code = CHAT_HOOK_SNIPPET.replace("@@AGENT_INIT_MODULE@@", agent_init_mod)
                        if not init_lua.exists():
                            init_lua.parent.mkdir(parents=True, exist_ok=True)
                            init_lua.write_text(
                                "local jass = require('jass.common')\n\n" + hook_code + "\n",
                                encoding="utf-8"
                            )
                            actions_taken.append(f"已创建默认入口 {init_lua} 并注入 -test on 钩子")
                        else:
                            init_text = init_lua.read_text(encoding="utf-8", errors="ignore")
                            if "agent.init" not in init_text:
                                init_lua.write_text(hook_code + "\n" + init_text, encoding="utf-8")
                                actions_taken.append(f"已在 {init_lua} 顶部注入 -test on / -agent on 启动钩子")
                            else:
                                actions_taken.append(f"{init_lua} 钩子已就绪")

                        results.append({"component": "entry_hook", "status": "success", "message": "；".join(actions_taken)})
            except Exception as e:
                results.append({"component": "entry_hook", "status": "failed", "message": f"处理失败：{e}"})

        # 7. plugin_sync 组件（同步插件源码到 Claude 插件缓存与全局 Skill 目录）
        if "plugin_sync" in components:
            try:
                home = Path.home()
                cache_root = home / ".claude" / "plugins" / "cache" / "kintsugi" / "war3-tester"
                synced_targets = []
                if cache_root.exists():
                    for ver_dir in cache_root.iterdir():
                        if ver_dir.is_dir():
                            if not is_check:
                                for sub in ["bin", "assets", "server", "skills", "commands", ".claude-plugin"]:
                                    src_sub = plugin_root / sub
                                    dst_sub = ver_dir / sub
                                    if src_sub.exists():
                                        shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)
                            synced_targets.append(str(ver_dir))
                msg = f"{'检查发现' if is_check else '已同步'} {len(synced_targets)} 个插件缓存目录"
                results.append({"component": "plugin_sync", "status": "success", "message": msg, "files": synced_targets})
            except Exception as e:
                results.append({"component": "plugin_sync", "status": "failed", "message": f"同步失败：{e}"})

        mode_label = {"repair": "安装/修复", "install": "增量安装", "check": "环境体检 (Check)"}[mode]
        messages = [f"## 环境{mode_label}结果\n\n时间：{timestamp}"]
        if project_root:
            messages.append(f"项目根目录：{project_root}")
        if war3_dir:
            messages.append(f"War3 安装目录：{war3_dir}")
        messages.append("")
        success_count = sum(1 for r in results if r.get("status") == "success")
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        skipped_count = sum(1 for r in results if r.get("status") == "skipped")
        messages.append(f"总计：{len(results)} 个组件（成功 {success_count} / 失败 {failed_count} / 跳过 {skipped_count}）\n")
        for r in results:
            status_icon = "✅" if r.get("status") == "success" else ("❌" if r.get("status") == "failed" else "⚠️")
            messages.append(f"{status_icon} {r.get('component')}: {r.get('status')}")
            messages.append(f"   {r.get('message')}")
            if r.get("files"):
                for f in r["files"]:
                    messages.append(f"   - {f}")
            messages.append("")
        is_error = failed_count > 0
        return {"content": [{"type": "text", "text": "\n".join(messages)}], "isError": is_error}
