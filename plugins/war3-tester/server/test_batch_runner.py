#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestBatchRunner - 批量测试编排（v2 新增，设计文档 4.1）

职责：
- discover_tests：扫描 auto-test/ 目录，返回测试列表 + 分类 + 估算耗时
- run_test_batch：顺序运行多个测试，每个独立游戏会话（隔离），返回汇总报告
- _run_single_test：单测执行核心（预清理→准备→编译→启动→轮询+进程监控→分类→截图→清理），
  被 run_test_batch 与 mcp_server.test_commit 共享，确保两者行为一致

特性：
- 进程存活监控 → 游戏崩溃检测（failure_type=crash）
- failure_type 分类决策树（设计文档 4.5）
- 失败按类型触发截图（仅 crash/timeout/unknown；assertion/runtime/compile 不截图，设计文档 4.7）
- 重试（max_retries）
- failed 列表会话内内存缓存（供 filter="failed" 复用，不持久化）

依赖（构造时注入）：config / executor / http_receiver / mcp_server（复用 _prepare_test_entry）
"""

import json
import time
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from logger import setup_logger


class TestBatchRunner:
    """批量测试编排器"""

    # 失败时触发截图的类型（设计文档 4.7：assertion/runtime_error/compile_error 不截图）
    SCREENSHOT_FAILURE_TYPES = {'crash', 'timeout', 'unknown'}

    def __init__(self, config, executor, http_receiver, mcp_server):
        """
        Args:
            config: Config 实例
            executor: 执行器（WinProxy / Local）
            http_receiver: HTTPReceiver 实例（取 progress/logs/game_errors）
            mcp_server: War3TesterMCP 实例（复用 _prepare_test_entry）
        """
        self.config = config
        self.executor = executor
        self.http_receiver = http_receiver
        self.mcp_server = mcp_server
        self.logger = setup_logger('test-batch')
        # 本次 batch 的 failed 列表（内存，不持久化），供 filter="failed" 复用
        self._failed_cache: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    # 测试发现
    # ------------------------------------------------------------------

    def discover_tests(self, source_dir: str = None, filter_pattern: str = None, layer: str = None) -> dict:
        """扫描测试目录，返回测试列表 + 分类 + 分层 + 估算耗时（设计文档 4.1 discover_tests）

        Args:
            source_dir: 源码目录
            filter_pattern: 过滤子串（匹配 test_name）
            layer: 按层过滤 'all' | 'unit' | 'integration' | 'e2e'（默认 None 不过滤）

        Returns:
            {'success': bool, 'test_dir': str, 'count': int, 'total_est_seconds': int,
             'tests': [{test_name, file, type(sync/async), layer(unit/integration/e2e), est_seconds}], ...}
        """
        resolved = self.config._resolve_path(source_dir) if source_dir else self.config.compile_source_dir
        test_dir = self.config.get_test_dir_path(resolved)
        if test_dir is None or not test_dir.exists():
            return {
                'success': False,
                'error': f'测试目录不存在: {test_dir}（请检查 config.test_dir / source_dir）',
                'test_dir': str(test_dir),
                'tests': [],
            }

        tests = []
        for f in sorted(test_dir.glob('test_*.lua')):
            test_name = f.stem  # 去 .lua
            ttype = self._infer_test_type(f)
            tlayer = self._infer_test_layer(f)
            est = self._estimate_test_time(ttype, tlayer)
            tests.append({
                'test_name': test_name,
                'file': f.name,
                'type': ttype,
                'layer': tlayer,
                'est_seconds': est,
            })

        # 过滤（substring 匹配，兼容 glob/regex 的简单情形）
        if filter_pattern and filter_pattern != 'all':
            tests = [t for t in tests if filter_pattern in t['test_name']]

        # 按 layer 过滤
        if layer and layer != 'all':
            tests = [t for t in tests if t['layer'] == layer]

        total_est = sum(t['est_seconds'] for t in tests)
        self.logger.info(f"[discover] 发现 {len(tests)} 个测试（目录 {test_dir}, layer={layer or 'all'}），估算 {total_est}s")
        return {
            'success': True,
            'test_dir': str(test_dir),
            'count': len(tests),
            'total_est_seconds': total_est,
            'tests': tests,
        }

    def _infer_test_type(self, filepath: Path) -> str:
        """推断测试类型：含 TestScenario → async，否则 sync"""
        try:
            text = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return 'sync'
        return 'async' if 'TestScenario' in text else 'sync'

    def _infer_test_layer(self, filepath: Path) -> str:
        """
        推断测试层（unit/integration/e2e）。

        优先级：
        1. 文件名前缀：test_unit_* → unit, test_int_* → integration, test_e2e_* → e2e
        2. 文件首行注释标记：-- @layer unit/integration/e2e
        3. 默认：integration（游戏内测试）
        """
        fname = filepath.name

        # 1. 文件名前缀
        if fname.startswith('test_unit_'):
            return 'unit'
        elif fname.startswith('test_int_'):
            return 'integration'
        elif fname.startswith('test_e2e_'):
            return 'e2e'

        # 2. 文件首行注释标记
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
            if first_line.startswith('--'):
                import re
                m = re.search(r'@layer\s+(unit|integration|e2e)', first_line, re.IGNORECASE)
                if m:
                    return m.group(1).lower()
        except Exception:
            pass

        # 3. 默认
        return 'integration'

    def _estimate_test_time(self, ttype: str, tlayer: str) -> int:
        """根据测试类型和层估算耗时（秒）"""
        if tlayer == 'unit':
            return 2  # 桌面秒级
        elif tlayer == 'e2e':
            return 60  # 全流程较长
        else:  # integration
            return 45 if ttype == 'async' else 30

    # ------------------------------------------------------------------
    # 批量执行
    # ------------------------------------------------------------------

    def run_test_batch(self, test_filter: Any = "all", stop_on_first_failure: bool = False,
                       max_retries: int = 1, timeout_per_test: int = 90,
                       auto_screenshot_on_failure: bool = True,
                       source_dir: str = None, platform: str = None,
                       layer: str = None) -> dict:
        """顺序运行多个测试，每个独立游戏会话，返回汇总报告（设计文档 4.1 run_test_batch）

        Args:
            test_filter: "all" | "failed" | 文件名/测试名列表 | glob 子串
            stop_on_first_failure: 首个失败即停止
            max_retries: 单测最大重试次数（默认 1，即失败后再跑 1 次）
            timeout_per_test: 单测超时秒数（默认 90）
            auto_screenshot_on_failure: 失败时是否自动截图（仅 crash/timeout/unknown 触发）
            source_dir: 源码目录
            platform: 游戏平台
            layer: 按层过滤 'all' | 'unit' | 'integration' | 'e2e'（默认 None 不过滤）
        """
        # ① 环境检查
        if not self.executor.check_connectivity():
            return {
                'success': False,
                'error': '执行器不可用（win_proxy 未连接或本地执行器异常）',
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0},
                'results': [],
            }

        # ② 测试发现 / 选择
        selected = self._select_tests(test_filter, source_dir, layer)
        if isinstance(selected, dict):  # 发现失败
            return selected
        if not selected:
            return {
                'success': True,
                'message': '未发现匹配的测试',
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0},
                'results': [],
            }

        self.logger.info(f"[batch] 开始批量测试：{len(selected)} 个，stop_on_first_failure={stop_on_first_failure}, "
                         f"max_retries={max_retries}, timeout={timeout_per_test}s")

        # ③ 逐个执行（每个独立会话，天然隔离）
        results = []
        passed = 0
        failed_list = []
        self._failed_cache = []  # 重置本次 batch 的 failed 缓存

        for i, t in enumerate(selected):
            test_name = t['test_name']
            test_file = t.get('file') or f'{test_name}.lua'
            self.logger.info(f"[batch] ({i + 1}/{len(selected)}) {test_name}")

            attempt = 0
            single = None
            while attempt <= max_retries:
                single = self._run_single_test(
                    test_name, test_file, timeout_per_test, platform, source_dir,
                    auto_screenshot_on_failure)
                if single.get('success'):
                    break
                attempt += 1
                if attempt <= max_retries:
                    self.logger.info(
                        f"[batch] {test_name} 失败({single.get('failure_type')}), 第 {attempt} 次重试...")

            results.append(single)
            if single.get('success'):
                passed += 1
            else:
                failed_list.append(test_name)
                self._failed_cache.append({'test_name': test_name, 'file': test_file})
                if stop_on_first_failure:
                    self.logger.info("[batch] stop_on_first_failure，停止后续测试")
                    break

        # ④ 汇总
        total = len(results)
        failed = total - passed
        pass_rate = round(passed / total, 4) if total else 0.0
        summary = {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate,
            'stop_on_first_failure': stop_on_first_failure,
            'failure_types': self._tally_failure_types(results),
        }

        # ⑤ 清理
        self.executor.stop_game()

        self.logger.info(f"[batch] 完成：{passed}/{total} 通过")
        return {
            'success': failed == 0,
            'message': f'批量测试完成：{passed}/{total} 通过，通过率 {pass_rate:.0%}',
            'summary': summary,
            'results': results,
            'failed': failed_list,
        }

    def _select_tests(self, test_filter: Any, source_dir: str = None, layer: str = None):
        """根据 filter 选择测试列表。返回 list；发现失败时返回 dict（错误响应）。"""
        if isinstance(test_filter, list):
            return [self._normalize_test(t) for t in test_filter]
        if test_filter == 'failed':
            if not self._failed_cache:
                self.logger.info("[batch] filter='failed' 但无失败缓存，返回空")
            return list(self._failed_cache)
        # 'all' 或 glob 子串
        pattern = None if (not test_filter or test_filter == 'all') else test_filter
        discovery = self.discover_tests(source_dir, filter_pattern=pattern, layer=layer)
        if not discovery.get('success'):
            return {
                'success': False,
                'error': discovery.get('error'),
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0},
                'results': [],
            }
        return [{'test_name': t['test_name'], 'file': t['file']} for t in discovery['tests']]

    def _normalize_test(self, t) -> Dict[str, str]:
        """把字符串/字典归一为 {test_name, file}"""
        if isinstance(t, dict):
            name = t.get('test_name') or t.get('name')
            file = t.get('file') or (f'{name}.lua' if name else None)
            return {'test_name': name, 'file': file}
        name = str(t)
        if name.endswith('.lua'):
            name = name[:-4]
        return {'test_name': name, 'file': f'{name}.lua'}

    def _tally_failure_types(self, results: List[dict]) -> Dict[str, int]:
        tally: Dict[str, int] = {}
        for r in results:
            if not r.get('success'):
                ft = r.get('failure_type') or 'unknown'
                tally[ft] = tally.get(ft, 0) + 1
        return tally

    # ------------------------------------------------------------------
    # 单测执行核心（run_test_batch 与 mcp_server.test_commit 共享）
    # ------------------------------------------------------------------

    def _run_single_test(self, test_name: str, test_file: str = None,
                         timeout: int = 90, platform: str = None, source_dir: str = None,
                         auto_screenshot_on_failure: bool = True) -> dict:
        """运行单个测试（独立会话）。返回标准化结果（含 failure_type / progress / logs）。

        流程：预清理 → 准备入口 → 编译 → 启动 → 轮询+进程监控 → 分类 → 截图 → 清理
        """
        # 清缓冲：避免上一个测试的 progress/logs/game_errors 污染本次
        self.http_receiver.clear_test_buffers(test_name)
        self.http_receiver.clear_game_errors()

        # source_dir 默认 config.compile_source_dir（与 test_commit handle 一致）；
        # 否则 _prepare_test_entry 会 fallback 到 project_root(cache)，
        # 把 _target_test.lua / run_auto_test.lua 写到插件目录而非项目目录 → 游戏加载不到
        if not source_dir:
            source_dir = str(self.config.compile_source_dir)

        # 0. 预清理
        self.logger.info(f"[{test_name}] 预清理...")
        self.executor.stop_game()
        time.sleep(3)

        try:
            # 0.5 准备测试入口（写 _target_test.lua + run_auto_test.lua）
            try:
                self.mcp_server._prepare_test_entry(test_name, test_file, source_dir)
            except Exception as e:
                return self._build_result(test_name, success=False, failure_type='env_error',
                                          error=f'准备测试入口失败：{e}', elapsed=0)

            # 1. 编译
            compile_result = self.executor.compile(source_dir)
            if not compile_result.get('success'):
                return self._build_result(test_name, success=False, failure_type='compile_error',
                                          error=f'编译失败：{compile_result.get("error", "unknown")}',
                                          elapsed=0)

            # 2. 启动游戏
            run_result = self.executor.run_game(platform=platform)
            if not run_result.get('success'):
                return self._build_result(test_name, success=False, failure_type='env_error',
                                          error=f'启动游戏失败：{run_result.get("error", "unknown")}',
                                          elapsed=0)

            # 3. 轮询结果 + 进程存活监控
            self.http_receiver.delete_old_result(test_name)
            result_file = self.http_receiver.get_result_file(test_name)

            self.logger.info(f"[{test_name}] 等待测试结果 (超时 {timeout}s)...")
            elapsed = 0
            poll_interval = 3
            game_seen_alive = False
            result_data = None
            outcome: Optional[str] = None  # 'result' | 'crash' | 'timeout' | 'env_error'

            while elapsed < timeout:
                time.sleep(poll_interval)
                elapsed += poll_interval

                if result_file.exists():
                    try:
                        with open(result_file, 'r', encoding='utf-8') as f:
                            result_data = json.load(f)
                        outcome = 'result'
                        break
                    except (json.JSONDecodeError, IOError) as e:
                        self.logger.warning(f"[{test_name}] 结果文件读取失败：{e}")
                        continue

                # 进程存活监控（设计文档 4.1/4.5：进程曾存活后消失 → crash）
                alive = self._is_game_alive()
                if alive:
                    game_seen_alive = True
                elif game_seen_alive:
                    outcome = 'crash'
                    self.logger.warning(f"[{test_name}] 游戏进程消失（曾存活），判定崩溃")
                    break
                # 未曾存活则继续等（游戏可能仍在启动）

                self.logger.info(f"[{test_name}] 等待中... ({elapsed}/{timeout}s)")

            # 超时
            if outcome is None:
                outcome = 'env_error' if not game_seen_alive else 'timeout'

            # 4. 停止游戏
            self.executor.stop_game()
            time.sleep(1)

            # 5. 分类 + 组装结果
            game_errors = self.http_receiver.get_game_errors()
            return self._finalize_result(
                test_name, outcome, result_data, game_errors, elapsed,
                auto_screenshot_on_failure, result_file)
        finally:
            # 需求1：测试完成后（成功/失败/超时/早返回——所有路径）自动写 _test_off.lua，
            # 让手动游戏时 auto-test 模块不加载（零干扰）；下次 _prepare_test_entry 自动删除它
            self._write_test_off(source_dir)

    def _write_test_off(self, source_dir: str) -> None:
        """测试完成后写 _test_off.lua，让手动游戏时 auto-test 模块不加载（零干扰）。"""
        try:
            test_dir = self.config.get_test_dir_path(self.config._resolve_path(source_dir))
            if test_dir is None:
                self.logger.warning('[toggle] source_dir 非有效项目根，跳过写 _test_off')
                return
            off_path = test_dir / '_test_off.lua'
            off_path.write_text(
                '-- _run_single_test 完成后自动生成：手动游戏时 auto-test 模块不加载（init.lua early-return）\nreturn true\n',
                encoding='utf-8')
            self.logger.info(f"[toggle] 测试完成，已写 _test_off.lua（手动游戏零干扰）")
        except Exception as e:
            self.logger.warning(f"[toggle] 写 _test_off 失败：{e}")

    def _finalize_result(self, test_name: str, outcome: str, result_data: Optional[dict],
                         game_errors: list, elapsed: int,
                         auto_screenshot_on_failure: bool, result_file: Optional[Path]) -> dict:
        """根据 outcome 与结果数据，分类 failure_type 并组装最终结果

        【M4 增强】失败时自动收集诊断信息（截图+VLM 判读+inspect_game+get_debug_output）。
        每个诊断步骤 try/except 包裹，失败不阻塞主结果。
        """
        screenshots: List[str] = []
        screenshot_analysis: Optional[str] = None
        inspect_snapshot: Optional[str] = None
        debug_output: Optional[str] = None

        # 判断是否失败（用于触发诊断）
        is_failure = False
        failure_type = None

        if outcome == 'result':
            test_success = result_data.get('success', False)
            failure_type = None if test_success else self._classify_failure(result_data, game_errors)
            is_failure = not test_success

            # result 到达时通常非 crash/timeout；保留兜底（failure_type 被显式标为这些时才截）
            if (is_failure and auto_screenshot_on_failure
                    and failure_type in self.SCREENSHOT_FAILURE_TYPES):
                screenshots = self._take_failure_screenshot(test_name)

            # 【M4 增强】失败时收集诊断信息
            if is_failure and auto_screenshot_on_failure:
                screenshot_analysis = self._collect_screenshot_analysis(screenshots)
                inspect_snapshot = self._collect_inspect_snapshot()
                debug_output = self._collect_debug_output()

            return self._build_result(
                test_name, success=test_success, failure_type=failure_type,
                result=result_data, result_file=str(result_file) if result_file else None,
                game_errors=game_errors, elapsed=elapsed, screenshots=screenshots,
                screenshot_analysis=screenshot_analysis,
                inspect_snapshot=inspect_snapshot,
                debug_output=debug_output,
                error=(result_data.get('error') if not test_success else None))

        if outcome == 'crash':
            is_failure = True
            failure_type = 'crash'
            if auto_screenshot_on_failure:
                screenshots = self._take_failure_screenshot(test_name)
            progress = self.http_receiver.get_progress(test_name)

            # 【M4 增强】收集诊断
            if auto_screenshot_on_failure:
                screenshot_analysis = self._collect_screenshot_analysis(screenshots)
                inspect_snapshot = self._collect_inspect_snapshot()
                debug_output = self._collect_debug_output()

            return self._build_result(
                test_name, success=False, failure_type='crash',
                game_errors=game_errors, elapsed=elapsed, screenshots=screenshots,
                screenshot_analysis=screenshot_analysis,
                inspect_snapshot=inspect_snapshot,
                debug_output=debug_output,
                crash_log=None,  # P1：crash_log_reader 读取 Errors\<时间戳> Crash.txt
                progress=progress,
                logs=self.http_receiver.get_logs(test_name),
                error=f'游戏进程崩溃（曾启动后消失），已收 {len(progress)} 条进度')

        if outcome == 'timeout':
            is_failure = True
            failure_type = 'timeout'
            if auto_screenshot_on_failure:
                screenshots = self._take_failure_screenshot(test_name)

            # 【M4 增强】收集诊断
            if auto_screenshot_on_failure:
                screenshot_analysis = self._collect_screenshot_analysis(screenshots)
                inspect_snapshot = self._collect_inspect_snapshot()
                debug_output = self._collect_debug_output()

            return self._build_result(
                test_name, success=False, failure_type='timeout',
                game_errors=game_errors, elapsed=elapsed, screenshots=screenshots,
                screenshot_analysis=screenshot_analysis,
                inspect_snapshot=inspect_snapshot,
                debug_output=debug_output,
                progress=self.http_receiver.get_progress(test_name),
                logs=self.http_receiver.get_logs(test_name),
                error=f'测试超时 ({elapsed}s)，最后进度：{self._last_progress_step(test_name)}')

        # outcome == 'env_error'（游戏从未启动）
        return self._build_result(
            test_name, success=False, failure_type='env_error',
            elapsed=elapsed, error='游戏进程从未启动（或执行器异常）')

    def _classify_failure(self, result_data: dict, game_errors: list) -> str:
        """failure_type 分类决策树（设计文档 4.5）

        result 已到达且 success=false 时调用。优先级：
        游戏侧推断 > assertion > runtime_error > unknown
        crash/timeout/compile_error/env_error 在 _finalize_result 由 outcome 直接判定。
        """
        ft = result_data.get('failure_type')
        if ft:
            return ft
        assertions = result_data.get('assertions') or []
        if any(not a.get('passed') for a in assertions):
            return 'assertion'
        if game_errors:
            return 'runtime_error'
        return 'unknown'

    def _is_game_alive(self) -> bool:
        """检查 War3 游戏进程是否存活（复用 tasklist，跨 WinProxy/Local 执行器）"""
        try:
            result = self.executor.execute('tasklist.exe', ['/FO', 'CSV'], kwargs={'timeout': 5})
            stdout = (result.get('stdout', '') or '').lower()
            for name in self.config.war3_process_names:
                if name.lower() in stdout:
                    return True
            return False
        except Exception as e:
            self.logger.debug(f"[alive] 探测异常（不误判崩溃）：{e}")
            return True  # 探测失败不误判为崩溃

    def _take_failure_screenshot(self, test_name: str) -> List[str]:
        """失败时截图，返回路径列表"""
        try:
            ss = self.executor.take_screenshot(test_name, window_title='魔兽')
            if ss.get('success'):
                return [ss.get('path') or ss.get('path_wsl')]
            self.logger.warning(f"[{test_name}] 截图失败：{ss.get('error')}")
        except Exception as e:
            self.logger.warning(f"[{test_name}] 截图异常：{e}")
        return []

    def _collect_screenshot_analysis(self, screenshots: List[str]) -> Optional[str]:
        """【M4 方向 G】收集截图的 VLM 判读结果（graceful）"""
        if not screenshots:
            return None
        try:
            # 取第一张截图
            screenshot_path = screenshots[0]
            if not screenshot_path or not os.path.exists(screenshot_path):
                return None

            # 调用 mcp_server 的 analyze_screenshot
            analysis = self.mcp_server.analyze_screenshot(screenshot_path)
            return analysis
        except Exception as e:
            self.logger.warning(f"[{test_name}] VLM 判读失败（graceful）：{e}")
            return f"VLM 判读失败: {e}"

    def _collect_inspect_snapshot(self) -> Optional[str]:
        """【M4 方向 G】收集运行时状态快照（graceful）

        查询表达式从 config.inspect_queries 读取（项目自定义，默认空=不查 inspect）。
        通用性：不硬编码任何项目特化 API，项目通过 config.json -> test.inspect_queries 配置。
        """
        try:
            # 从 config 读取查询表达式列表（项目自定义，默认空）
            queries = self.config.inspect_queries or []
            if not queries:
                # 未配置 inspect_queries，跳过（通用，不依赖项目特化 API）
                self.logger.info("[inspect] 未配置 inspect_queries，跳过 inspect 快照")
                return None

            snapshots = []
            for expr in queries:
                try:
                    # 使用 inspect_game 的机制（直接操作 _inspect_pending）
                    query_id = f"q_{int(time.time() * 1000)}_{os.getpid()}"
                    self.http_receiver._inspect_pending.append({
                        "id": query_id,
                        "expr": expr
                    })
                    # 等待结果（最多 2s）
                    for _ in range(10):
                        time.sleep(0.2)
                        result = self.http_receiver._inspect_results.pop(query_id, None)
                        if result:
                            if "error" in result:
                                snapshots.append(f"{expr}: ERROR - {result['error']}")
                            else:
                                snapshots.append(f"{expr}: {result.get('value', '')}")
                            break
                except Exception as e:
                    snapshots.append(f"{expr}: 查询失败 - {e}")

            return "\n".join(snapshots) if snapshots else None
        except Exception as e:
            self.logger.warning(f"inspect 快照收集失败（graceful）：{e}")
            return f"inspect 快照收集失败: {e}"

    def _collect_debug_output(self) -> Optional[str]:
        """【M4 方向 G】收集调试输出（graceful）"""
        try:
            # 调用 mcp_server 的 _get_debug_output
            debug_text = self.mcp_server._get_debug_output(limit=20, level='error')
            return debug_text
        except Exception as e:
            self.logger.warning(f"debug_output 收集失败（graceful）：{e}")
            return f"debug_output 收集失败: {e}"

    def _last_progress_step(self, test_name: str) -> str:
        """取最后一条进度的 step 名（timeout 诊断用）"""
        progress = self.http_receiver.get_progress(test_name)
        if progress:
            last = progress[-1]
            return f"{last.get('step', '?')}({last.get('phase', '?')})"
        return '无进度上报'

    def _build_result(self, test_name: str, success: bool, failure_type: str = None,
                      result: dict = None, result_file: str = None, elapsed: int = 0,
                      game_errors: list = None, screenshots: list = None,
                      crash_log: str = None, progress: list = None, logs: list = None,
                      error: str = None, **extra) -> dict:
        """构造标准化单测结果（对齐设计文档 4.4 v2 格式）

        result 已到达时，progress/logs 已由 http_receiver /result 合并逻辑回填进 result_data；
        crash/timeout（无 result）时由调用方手动带上缓冲，便于诊断。
        """
        data = {
            'test_name': test_name,
            'success': success,
            'failure_type': failure_type,
            'elapsed': elapsed,
            'duration_ms': (result.get('duration_ms') if result else None),
            'result': result,
            'result_file': result_file,
            'progress': progress if progress is not None else ((result.get('progress') if result else []) or []),
            'logs': logs if logs is not None else ((result.get('logs') if result else []) or []),
            'game_errors': game_errors or [],
            'crash_log': crash_log,  # P1 实现（crash_log_reader 读 Errors\）
            'screenshots': screenshots or [],
            'error': error,
        }
        data.update(extra)
        return data
