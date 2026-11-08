#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
HTTP 接收端模块

从基线 _create_http_app 提取，提供 HTTP 接收端：
- /health: 健康检查
- /result: 接收测试结果
- /screenshot: 接收截图
- /error: 接收游戏内错误上报
- /poll/<test_name>: 轮询测试结果
- /progress: 接收测试逐步骤进度
- /log: 接收结构化分级日志

注：运行时查询（inspect_game / exec_game）已完全迁移至 Windows 命名管道 (\\.\pipe\war3_agent)，
不再通过 HTTP 轮询 /inspect/pending 与 /inspect/result。

端口：8766（可配置）
"""

import json
import base64
import sys
import threading
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from logger import setup_logger


class HTTPReceiver:
    """
    HTTP 接收端：接收游戏内回传的测试结果、截图、错误

    路由：
    - GET  /health: 健康检查
    - POST /result: 接收测试结果
    - POST /screenshot: 接收截图
    - POST /error: 接收游戏内错误上报
    - GET  /poll/<test_name>: 轮询测试结果
    - POST /progress: 接收测试步骤进度
    - POST /log: 接收结构化日志
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 8766,
                 logs_dir: Path = None, store=None):
        self.host = host
        self.port = port
        self.logger = setup_logger('http-receiver')

        base_dir = Path(__file__).parent / 'logs'
        self.logs_dir = logs_dir or base_dir
        self.test_results_dir = self.logs_dir / 'test_results'
        self.screenshots_dir = self.logs_dir / 'screenshots'

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.test_results_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.http_server = None
        self.http_thread = None
        self.store = store

    def start(self) -> bool:
        """启动 HTTP 服务器（后台线程）"""
        try:
            from flask import Flask
            from werkzeug.serving import make_server

            if self.http_server is not None:
                self.logger.info("HTTP 服务器已在运行")
                return True

            app = self._create_app()

            cleaned = self._cleanup_port_occupiers()
            if cleaned:
                self.logger.info(f"启动前清理占用端口 {self.port} 的残留进程：{cleaned}")
                time.sleep(1)

            try:
                server = make_server(self.host, self.port, app, threaded=True)
            except OSError as e:
                self.logger.warning(f"HTTP 服务器启动失败（端口 {self.port} 可能被占用）：{e}，尝试清理残留进程...")
                cleaned_pids = self._cleanup_port_occupiers()
                if cleaned_pids:
                    self.logger.info(f"已清理占用端口 {self.port} 的进程：{cleaned_pids}，重试启动...")
                    time.sleep(1)
                    try:
                        server = make_server(self.host, self.port, app, threaded=True)
                    except OSError as retry_e:
                        self.logger.error(f"HTTP 服务器启动失败（端口 {self.port} 被占用且清理后重试失败）：{retry_e}")
                        return False
                else:
                    self.logger.error(f"HTTP 服务器启动失败（端口 {self.port} 被占用且未找到可清理的残留进程）：{e}")
                    return False

            self.http_server = server

            def run_http():
                server.serve_forever()

            self.http_thread = threading.Thread(target=run_http, daemon=True)
            self.http_thread.start()

            self.logger.info(f"HTTP 服务器已启动（端口 {self.port}）")
            return True

        except ImportError:
            self.logger.error("Flask 未安装，HTTP 服务器无法启动")
            print("[war3-tester] ============================================================", file=sys.stderr)
            print("[war3-tester] 错误：缺少依赖 Flask/werkzeug，HTTP 结果回传服务无法启动", file=sys.stderr)
            print("[war3-tester] 影响：所有 test_commit 将因无进度上报而超时失败", file=sys.stderr)
            print("[war3-tester] 解决：请执行 pip install flask werkzeug（或调用 setup_environment 工具）", file=sys.stderr)
            print("[war3-tester] ============================================================", file=sys.stderr)
            return False
        except Exception as e:
            self.logger.error(f"HTTP 服务器启动失败：{e}")
            return False

    def stop(self) -> None:
        """停止 HTTP 服务器"""
        if self.http_server is not None:
            try:
                self.http_server.shutdown()
                self.logger.info("HTTP 服务器已停止")
            except Exception as e:
                self.logger.error(f"HTTP 服务器停止失败：{e}")
            finally:
                self.http_server = None
        else:
            self.logger.info("HTTP 服务器未在运行")

    def _cleanup_port_occupiers(self) -> list:
        """清理占用 self.port 的残留进程，返回清理的 PID 列表"""
        cleaned = []
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.logger.warning(f"netstat 执行失败：returncode={result.returncode}")
                return cleaned

            for line in (result.stdout or '').splitlines():
                if f':{self.port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if not parts:
                        continue
                    pid_str = parts[-1]
                    if not pid_str.isdigit():
                        continue
                    pid = int(pid_str)
                    try:
                        kill_result = subprocess.run(
                            ['taskkill', '/PID', str(pid), '/F'],
                            capture_output=True,
                            timeout=5
                        )
                        if kill_result.returncode == 0:
                            cleaned.append(pid)
                            self.logger.info(f"已清理占用端口 {self.port} 的进程 PID={pid}")
                        else:
                            self.logger.warning(f"清理 PID={pid} 失败：{kill_result.stderr.decode('utf-8', errors='ignore') if isinstance(kill_result.stderr, bytes) else kill_result.stderr}")
                    except Exception as kill_e:
                        self.logger.warning(f"清理 PID={pid} 异常：{kill_e}")
        except Exception as e:
            self.logger.warning(f"_cleanup_port_occupiers 异常：{e}")
        return cleaned

    def _create_app(self):
        """创建 Flask 应用"""
        from flask import Flask, request, jsonify

        app = Flask(__name__)

        def save_screenshots(test_name: str, screenshots: list) -> list:
            """保存截图并返回文件路径列表"""
            saved = []
            for i, screenshot in enumerate(screenshots):
                filename = screenshot.get('filename', f'screenshot_{i}.png')
                base64_data = screenshot.get('data', '')
                if not base64_data:
                    continue
                try:
                    image_data = base64.b64decode(base64_data)
                    screenshot_path = self.screenshots_dir / test_name / filename
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(screenshot_path, 'wb') as img_file:
                        img_file.write(image_data)
                    saved.append(str(screenshot_path))
                    self.logger.info(f"截图已保存：{screenshot_path}")
                except Exception as e:
                    self.logger.error(f"截图保存失败 {filename}: {e}")
            return saved

        @app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'logs_dir': str(self.logs_dir),
                'results_dir': str(self.test_results_dir)
            })

        @app.route('/result', methods=['POST'])
        def receive_test_result():
            """接收测试结果"""
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    raw_data = request.get_data(as_text=True)
                    self.logger.debug(f"[测试结果] get_json 未命中，原始请求体前200字符：{raw_data[:200]!r}")
                    try:
                        data = json.loads(raw_data)
                    except (json.JSONDecodeError, ValueError):
                        return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400
                if not data:
                    return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400

                test_name = data.get('test_name', 'unknown_test')
                timestamp = data.get('timestamp', datetime.now().strftime('%Y%m%d_%H%M%S'))
                result_file = self.test_results_dir / f'{test_name}.json'

                screenshots = data.get('screenshots', [])
                saved_screenshots = save_screenshots(test_name, screenshots)
                if saved_screenshots:
                    data['screenshots'] = saved_screenshots

                data = self.store.merge_into(test_name, data)

                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                log_file = self.logs_dir / f'test_{test_name}.log'
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] 测试结果：{'通过' if data.get('success') else '失败'}\n")
                    for log_entry in data.get('logs', []):
                        f.write(f"  {log_entry}\n")
                    f.write("\n")

                self.logger.info(f"测试结果已接收：{test_name} - {'通过' if data.get('success') else '失败'}")
                self.logger.info(f"结果文件：{result_file}")

                return jsonify({
                    'success': True,
                    'message': '测试结果已接收',
                    'result_file': str(result_file),
                    'screenshots_saved': len(saved_screenshots)
                })

            except Exception as e:
                self.logger.error(f"处理测试结果失败：{e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/screenshot', methods=['POST'])
        def receive_screenshot():
            """接收截图"""
            try:
                data = request.form
                test_name = data.get('test_name', 'unknown')
                filename = data.get('filename', f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
                base64_data = data.get('data', '')

                if not base64_data:
                    return jsonify({'success': False, 'error': '缺少图片数据'}), 400

                image_data = base64.b64decode(base64_data)
                screenshot_path = self.screenshots_dir / test_name / filename
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)

                with open(screenshot_path, 'wb') as f:
                    f.write(image_data)

                return jsonify({'success': True, 'path': str(screenshot_path)})

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/error', methods=['POST'])
        def receive_game_error():
            """接收游戏内错误上报"""
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    raw_data = request.get_data(as_text=True)
                    try:
                        data = json.loads(raw_data)
                    except (json.JSONDecodeError, ValueError):
                        return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400
                if not data:
                    return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400

                test_name = data.get('test_name', 'unknown')
                error_message = data.get('error', '')
                traceback = data.get('traceback', '')
                timestamp = data.get('timestamp', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))

                self.logger.error(f"[游戏错误] {test_name}: {error_message}")
                if traceback:
                    self.logger.error(f"[堆栈] {traceback[:500]}...")

                self.store.record_error(test_name, {
                    'test_name': test_name,
                    'error': error_message,
                    'traceback': traceback,
                    'timestamp': timestamp
                })

                self.logger.info(f"[错误上报] 已接收错误：{test_name}")
                return jsonify({'success': True, 'message': '错误已接收'})

            except Exception as e:
                self.logger.error(f"处理错误上报失败：{e}", exc_info=True)
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/poll/<test_name>', methods=['GET'])
        def poll_test_result(test_name):
            """轮询测试结果"""
            result_file = self.test_results_dir / f'{test_name}.json'

            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify({'status': 'completed', 'data': data})
            else:
                return jsonify({'status': 'not_found', 'message': f'测试结果 {test_name} 尚未生成'}), 404

        @app.route('/progress', methods=['POST'])
        def receive_progress():
            """接收测试逐步骤进度（v2 新增）"""
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    raw_data = request.get_data(as_text=True)
                    try:
                        data = json.loads(raw_data)
                    except (json.JSONDecodeError, ValueError):
                        return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400
                if not data:
                    return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400

                test_name = data.get('test_name', 'unknown')
                entry = {
                    'test_name': test_name,
                    'step': data.get('step', ''),
                    'phase': data.get('phase', 'done'),
                    'detail': data.get('detail', {}),
                    'timestamp': data.get('timestamp') or datetime.now().isoformat(),
                }
                if 'elapsed_ms' in data:
                    entry['elapsed_ms'] = data['elapsed_ms']

                self.store.record_progress(test_name, entry)
                self.logger.info(f"[进度] {test_name}: {entry['step']} ({entry['phase']})")
                return jsonify({'success': True, 'message': '进度已接收'})
            except Exception as e:
                self.logger.error(f"处理进度上报失败：{e}", exc_info=True)
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/log', methods=['POST'])
        def receive_log():
            """接收结构化分级日志（v2 新增）"""
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    raw_data = request.get_data(as_text=True)
                    try:
                        data = json.loads(raw_data)
                    except (json.JSONDecodeError, ValueError):
                        return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400
                if not data:
                    return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400

                test_name = data.get('test_name', 'unknown')
                entry = {
                    'test_name': test_name,
                    'level': data.get('level', 'info'),
                    'category': data.get('category', ''),
                    'message': data.get('message', ''),
                    'context': data.get('context', {}),
                    'timestamp': data.get('timestamp') or datetime.now().isoformat(),
                }

                self.store.record_log(test_name, entry)

                return jsonify({'success': True, 'message': '日志已接收'})
            except Exception as e:
                self.logger.error(f"处理日志上报失败：{e}", exc_info=True)
                return jsonify({'success': False, 'error': str(e)}), 500

        return app

    def get_result_file(self, test_name: str) -> Optional[Path]:
        """获取测试结果文件路径"""
        return self.test_results_dir / f'{test_name}.json'

    def delete_old_result(self, test_name: str) -> None:
        """删除旧的测试结果文件"""
        result_file = self.test_results_dir / f'{test_name}.json'
        if result_file.exists():
            result_file.unlink()
            self.logger.info(f"已删除旧结果文件: {result_file}")
