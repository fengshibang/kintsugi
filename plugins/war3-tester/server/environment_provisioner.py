#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnvironmentProvisioner - 测试环境组件部署模块

职责：
- 部署 socket.dll 到项目 map/ 目录
- 安装 Flask + werkzeug Python 依赖
- 部署 nopause.asi 到 War3 安装目录

零反向依赖：只依赖标准库 + 收 config/plugin_root 参数，不引用 mcp_server / test_batch_runner / http_receiver

v0.19.6(候选⑤): 从 mcp_server._handle_setup_environment 闭包外提。返回结构逐字保留
（{"content": [{"type":"text","text":...}], "isError": failed_count>0}）。
"""

import sys
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime


class EnvironmentProvisioner:
    """
    测试环境组件部署器。

    覆盖 mcp_server._handle_setup_environment 闭包的全部逻辑。

    构造参数：
        config: Config 实例
        plugin_root: 插件根目录 Path（= mcp_server.SERVER_DIR.parent）
        logger: 日志记录器（可选）
    """

    def __init__(self, config, plugin_root, logger=None):
        self.config = config
        self.plugin_root = plugin_root
        self.logger = logger or logging.getLogger(__name__)

    def setup(self, arguments: dict) -> dict:
        """
        部署测试环境组件。

        Args:
            arguments: 包含 source_dir / components / war3_dir 的字典

        Returns:
            {"content": [{"type":"text","text":...}], "isError": failed_count>0}
            返回结构逐字 = 原 mcp_server._handle_setup_environment 闭包
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_dir = arguments.get("source_dir")
        components = arguments.get("components", ["socket", "http", "nopause"])
        war3_dir = arguments.get("war3_dir")
        if source_dir:
            project_root = Path(source_dir)
        elif self.config.project_root:
            project_root = self.config.project_root
        else:
            project_root = None
        if not war3_dir and self.config.war3_log_dir:
            try:
                inferred_war3_dir = Path(self.config.war3_log_dir).parent
                if inferred_war3_dir.exists():
                    war3_dir = str(inferred_war3_dir)
            except Exception:
                pass
        plugin_root = self.plugin_root
        results = []
        if "socket" in components:
            try:
                if not project_root:
                    results.append({"component": "socket", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                else:
                    socket_src_dir = plugin_root / "bin" / "socket"
                    socket_dst_dir = project_root / "map"
                    if not socket_src_dir.exists():
                        results.append({"component": "socket", "status": "failed", "message": f"插件 bin/socket 目录不存在：{socket_src_dir}"})
                    else:
                        socket_dst_dir.mkdir(parents=True, exist_ok=True)
                        copied_files = []
                        for dll_name in ["socket.dll", "libwinpthread-1.dll"]:
                            src = socket_src_dir / dll_name
                            dst = socket_dst_dir / dll_name
                            if src.exists():
                                shutil.copy2(src, dst)
                                copied_files.append(str(dst))
                        if copied_files:
                            results.append({"component": "socket", "status": "success", "message": f"已拷贝 {len(copied_files)} 个文件到 {socket_dst_dir}", "files": copied_files})
                        else:
                            results.append({"component": "socket", "status": "failed", "message": "未找到 socket.dll 或 libwinpthread-1.dll"})
            except Exception as e:
                results.append({"component": "socket", "status": "failed", "message": f"部署失败：{e}"})
        if "http" in components:
            try:
                proc = subprocess.run([sys.executable, "-m", "pip", "install", "flask", "werkzeug"], capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    results.append({"component": "http", "status": "success", "message": "flask + werkzeug 已安装（或已是最新）"})
                else:
                    results.append({"component": "http", "status": "failed", "message": f"pip install 失败：{proc.stderr}"})
            except subprocess.TimeoutExpired:
                results.append({"component": "http", "status": "failed", "message": "pip install 超时（120秒）"})
            except Exception as e:
                results.append({"component": "http", "status": "failed", "message": f"pip install 异常：{e}"})
        if "nopause" in components:
            try:
                if not war3_dir:
                    results.append({"component": "nopause", "status": "skipped", "message": "未指定 war3_dir 且无法从 config.war3_log_dir 反推，请传参 war3_dir"})
                else:
                    nopause_src = plugin_root / "bin" / "nopause.asi"
                    nopause_dst = Path(war3_dir) / "nopause.asi"
                    if not nopause_src.exists():
                        results.append({"component": "nopause", "status": "failed", "message": f"插件 bin/nopause.asi 不存在：{nopause_src}"})
                    else:
                        shutil.copy2(nopause_src, nopause_dst)
                        results.append({"component": "nopause", "status": "success", "message": f"已拷贝 nopause.asi 到 {nopause_dst}"})
            except Exception as e:
                results.append({"component": "nopause", "status": "failed", "message": f"部署失败：{e}"})
        messages = [f"## 环境部署结果\n\n时间：{timestamp}"]
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
