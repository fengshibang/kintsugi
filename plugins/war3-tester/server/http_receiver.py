#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP 接收端模块

从基线 _create_http_app 提取，提供 HTTP 接收端：
- /health: 健康检查
- /result: 接收测试结果
- /screenshot: 接收截图
- /error: 接收游戏内错误上报
- /poll/<test_name>: 轮询测试结果

端口：8766（可配置）
"""

import json
import base64
import threading
import time
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
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 8766,
                 logs_dir: Path = None):
        """
        初始化 HTTP 接收端

        Args:
            host: 监听地址
            port: 监听端口
            logs_dir: 日志目录（默认 server/logs/）
        """
        self.host = host
        self.port = port
        self.logger = setup_logger('http-receiver')

        # 目录结构（使用 Path(__file__) 自解析）
        base_dir = Path(__file__).parent / 'logs'
        self.logs_dir = logs_dir or base_dir
        self.test_results_dir = self.logs_dir / 'test_results'
        self.screenshots_dir = self.logs_dir / 'screenshots'

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.test_results_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.http_server = None
        self.http_thread = None
        self._game_errors = []  # 存储游戏内错误上报（/error 端点写入）
        # 【v2】按 test_name 缓冲的进度时间线与结构化日志（/progress、/log 端点写入）
        # /result 到达时合并进 result.json（游戏侧只管 POST，MCP 汇总，见设计文档 4.2/4.3）
        self._progress = {}  # test_name -> list[progress_entry]
        self._logs = {}      # test_name -> list[log_entry]
        self._max_logs_per_test = 2000  # 单测试日志缓冲上限（防爆内存）

        # inspect_game 运行时查询队列与结果缓存（v0.9.0 新增）
        # _inspect_pending: list[dict]，每项 {id, expr}，游戏端 GET /inspect/pending 取走执行
        # _inspect_results: dict[id -> dict]，游戏端 POST /inspect/result 回传，MCP 轮询取出
        self._inspect_pending = []   # FIFO 队列（append 入，pop(0) 出）
        self._inspect_results = {}   # id → {"id","value"} 或 {"id","error"}

    def start(self) -> bool:
        """启动 HTTP 服务器（后台线程）

        使用 werkzeug.serving.make_server 替代 app.run()，
        避免 werkzeug 启动 banner 污染 stdout（MCP stdio 协议要求 stdout 纯净）。
        端口占用时 make_server 会抛 OSError，直接报告失败，不误报成功。
        """
        try:
            from flask import Flask
            from werkzeug.serving import make_server

            if self.http_server is not None:
                self.logger.info("HTTP 服务器已在运行")
                return True

            app = self._create_app()

            # make_server 不打印 banner，端口占用时直接抛 OSError
            try:
                server = make_server(self.host, self.port, app, threaded=True)
            except OSError as e:
                self.logger.error(f"HTTP 服务器启动失败（端口 {self.port} 可能被占用）：{e}")
                return False

            self.http_server = server

            def run_http():
                server.serve_forever()

            # 守护线程，主进程退出时自动停止
            self.http_thread = threading.Thread(target=run_http, daemon=True)
            self.http_thread.start()

            self.logger.info(f"HTTP 服务器已启动（端口 {self.port}）")
            return True

        except ImportError:
            self.logger.error("Flask 未安装，HTTP 服务器无法启动")
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

    def _create_app(self):
        """创建 Flask 应用"""
        from flask import Flask, request, jsonify

        app = Flask(__name__)
        app.game_errors = self._game_errors  # 共享错误列表

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
                # 容错解析（通用 JSON 接收）：
                # force+silent 优先，失败则 get_data + json.loads 兜底。
                # 修复：部分 War3 Lua HTTP 客户端的 JSON POST 在 Flask strict request.json 下被判 400
                # （Content-Type/mimetype 识别差异），改用容错链路保证兼容。
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

                # 保存截图
                screenshots = data.get('screenshots', [])
                saved_screenshots = save_screenshots(test_name, screenshots)
                if saved_screenshots:
                    data['screenshots'] = saved_screenshots

                # 【v2】合并 MCP 侧缓冲的 progress / logs / game_errors
                # 游戏侧只管 POST，MCP 按 test_name 汇总回填（设计文档 4.2/4.3）
                buffered_progress = self._progress.get(test_name)
                if buffered_progress:
                    existing = data.get('progress') or []
                    data['progress'] = (existing + buffered_progress) if existing else list(buffered_progress)
                buffered_logs = self._logs.get(test_name)
                if buffered_logs:
                    existing = data.get('logs') or []
                    data['logs'] = (existing + buffered_logs) if existing else list(buffered_logs)
                # game_errors：本次测试相关的错误上报（按 test_name 过滤；未带 test_name 的归 unknown）
                related_errors = [e for e in self._game_errors
                                  if e.get('test_name', 'unknown') == test_name]
                if related_errors and not data.get('game_errors'):
                    data['game_errors'] = related_errors

                # 写入结果文件
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 写入日志
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

                test_name = data.get('test_name', 'unknown')
                error_message = data.get('error', '')
                traceback = data.get('traceback', '')
                timestamp = data.get('timestamp', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))

                self.logger.error(f"[游戏错误] {test_name}: {error_message}")
                if traceback:
                    self.logger.error(f"[堆栈] {traceback[:500]}...")

                app.game_errors.append({
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
            """接收测试逐步骤进度（v2 新增）

            游戏侧 TestScenario:step() 与 assert 失败时 POST。
            MCP 按 test_name 缓冲为时间线，/result 到达时并入 result.json。
            """
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
                    'phase': data.get('phase', 'done'),  # start | done | failed
                    'detail': data.get('detail', {}),
                    'timestamp': data.get('timestamp') or datetime.now().isoformat(),
                }
                if 'elapsed_ms' in data:
                    entry['elapsed_ms'] = data['elapsed_ms']

                self._progress.setdefault(test_name, []).append(entry)
                self.logger.info(f"[进度] {test_name}: {entry['step']} ({entry['phase']})")
                return jsonify({'success': True, 'message': '进度已接收'})
            except Exception as e:
                self.logger.error(f"处理进度上报失败：{e}", exc_info=True)
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/inspect/pending', methods=['GET'])
        def get_inspect_pending():
            """游戏端轮询拉取待执行的查询（v0.9.0 新增）

            返回 FIFO 队列中最旧的一条 {id, expr}，取出即移除。
            队列为空时返回 {}（200），绝不阻塞——游戏每 200ms 轮询一次。
            """
            try:
                self.logger.info(f"[get_pending] len={len(self._inspect_pending)} self_id={id(self)} list_id={id(self._inspect_pending)}")
                if not self._inspect_pending:
                    return jsonify({})
                # 取出最旧的一条（FIFO），同时从队列移除
                entry = self._inspect_pending.pop(0)
                return jsonify(entry)
            except Exception as e:
                self.logger.error(f"处理 /inspect/pending 失败：{e}", exc_info=True)
                # graceful：出错时返回空，不阻塞游戏轮询
                return jsonify({})

        @app.route('/inspect/result', methods=['POST'])
        def receive_inspect_result():
            """接收游戏端回传的查询结果（v0.9.0 新增）

            body: {"id":"<id>","value":"<结果文本>"} 或 {"id":"<id>","error":"<错误文本>"}
            存入 _inspect_results 缓存，MCP 侧 inspect_game 轮询取出。
            """
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    raw_data = request.get_data(as_text=True)
                    try:
                        data = json.loads(raw_data)
                    except (json.JSONDecodeError, ValueError):
                        return jsonify({'success': False, 'error': '请求体为空或不是有效的 JSON'}), 400

                req_id = data.get('id')
                if not req_id:
                    return jsonify({'success': False, 'error': '缺少 id 字段'}), 400

                # 存入结果缓存（整个 body，含 id+value 或 id+error）
                self._inspect_results[req_id] = data
                self.logger.info(f"[inspect] 收到结果：{req_id}")
                return jsonify({'success': True, 'message': '结果已接收'})
            except Exception as e:
                self.logger.error(f"处理 /inspect/result 失败：{e}", exc_info=True)
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/log', methods=['POST'])
        def receive_log():
            """接收结构化分级日志（v2 新增）

            游戏侧 init.lua 拦截 log.info / log.error 后 POST。
            MCP 按 test_name 缓冲（设上限防爆），/result 到达时并入 result.json。
            高频上报由游戏侧节流（同类 message 0.2s 合并，见 init.lua）。
            """
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
                    'level': data.get('level', 'info'),  # info | warn | error
                    'category': data.get('category', ''),
                    'message': data.get('message', ''),
                    'context': data.get('context', {}),
                    'timestamp': data.get('timestamp') or datetime.now().isoformat(),
                }

                bucket = self._logs.setdefault(test_name, [])
                bucket.append(entry)
                # 上限防爆：超出则丢弃最旧的一半
                if len(bucket) > self._max_logs_per_test:
                    del bucket[:len(bucket) // 2]

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

    def get_game_errors(self) -> list:
        """获取游戏内错误上报列表"""
        return self._game_errors

    def get_progress(self, test_name: str) -> list:
        """获取指定测试的进度时间线（v2）"""
        return self._progress.get(test_name, [])

    def get_logs(self, test_name: str) -> list:
        """获取指定测试的结构化日志（v2）"""
        return self._logs.get(test_name, [])

    def clear_test_buffers(self, test_name: str = None) -> None:
        """清除测试缓冲（progress / logs）

        每个 test_commit / batch 单测开始前调用，避免上一个测试的缓冲污染。

        Args:
            test_name: 指定测试名则只清该测试的 progress/logs；None 则清空全部。
        """
        if test_name is None:
            self._progress.clear()
            self._logs.clear()
            return
        self._progress.pop(test_name, None)
        self._logs.pop(test_name, None)

    def clear_game_errors(self) -> None:
        """清空游戏内错误上报列表（batch 开始前重置）"""
        self._game_errors.clear()
