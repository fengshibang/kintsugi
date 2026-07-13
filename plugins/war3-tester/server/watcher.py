#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FileWatcher - 文件监控 + 自动重跑测试（M4 方向 F）

职责：
- 监控测试文件和相关源文件的修改时间
- 文件改动时自动触发测试
- 结果累积到内存 + 日志文件
- 后台线程运行，不阻塞 MCP

设计：
- 使用 threading 实现后台监控
- 轮询文件修改时间（间隔可配置，默认 1s）
- 文件改动后 debounce（默认 0.5s）再触发测试
- 结果累积到 _results 列表，同时写入日志文件
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from logger import setup_logger


class FileWatcher:
    """文件监控器 + 自动测试触发器"""

    def __init__(self, desktop_runner, config):
        """
        Args:
            desktop_runner: DesktopRunner 实例（用于 run_unit_test）
            config: Config 实例
        """
        self.desktop_runner = desktop_runner
        self.config = config
        self.logger = setup_logger('watcher')

        # 监控状态
        self._watching = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 监控配置
        self._test_name: Optional[str] = None
        self._source_dir: Optional[str] = None
        self._watch_paths: List[Path] = []  # 监控的文件/目录列表
        self._poll_interval = 1.0  # 轮询间隔（秒）
        self._debounce_delay = 0.5  # 防抖延迟（秒）

        # 文件修改时间缓存
        self._file_mtimes: Dict[str, float] = {}

        # 结果累积
        self._results: List[Dict[str, Any]] = []
        self._results_lock = threading.Lock()

        # 日志文件路径
        self._log_dir = Path(__file__).parent / 'logs'
        self._log_dir.mkdir(exist_ok=True)
        self._log_file: Optional[Path] = None

    def start_watch(self, test_name: str, source_dir: str = None,
                    poll_interval: float = 1.0, debounce_delay: float = 0.5) -> Dict[str, Any]:
        """
        启动文件监控

        Args:
            test_name: 测试名称
            source_dir: 源码目录（默认 config.compile_source_dir）
            poll_interval: 轮询间隔（秒）
            debounce_delay: 防抖延迟（秒）

        Returns:
            {'success': bool, 'message': str, 'watch_id': str}
        """
        if self._watching:
            return {
                'success': False,
                'message': '已有监控在运行，请先调用 stop_watch 停止',
                'watch_id': None,
            }

        # 解析 source_dir
        resolved_source = self.config._resolve_path(source_dir) if source_dir else self.config.compile_source_dir
        test_dir = self.config.get_test_dir_path(resolved_source)
        if test_dir is None:
            return {
                'success': False,
                'message': f'source_dir 非有效 w2l 项目根: {resolved_source}',
                'watch_id': None,
            }

        # 推断测试文件
        if not test_name.startswith('test_'):
            test_file = f'test_{test_name}.lua'
        else:
            test_file = f'{test_name}.lua'

        test_file_path = test_dir / test_file
        if not test_file_path.exists():
            return {
                'success': False,
                'message': f'测试文件不存在: {test_file_path}',
                'watch_id': None,
            }

        # 配置监控
        self._test_name = test_name
        self._source_dir = str(resolved_source)
        self._poll_interval = poll_interval
        self._debounce_delay = debounce_delay

        # 监控路径：测试文件 + 整个 source_dir（简化版，可后续优化为只监控相关文件）
        self._watch_paths = [test_file_path, resolved_source]

        # 初始化文件修改时间缓存
        self._file_mtimes = {}
        self._scan_files()

        # 创建日志文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._log_file = self._log_dir / f'watch_{test_name}_{timestamp}.jsonl'

        # 清空结果
        with self._results_lock:
            self._results = []

        # 启动后台线程
        self._stop_event.clear()
        self._watching = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

        watch_id = f"watch_{int(time.time() * 1000)}"
        self.logger.info(f"[watch] 启动监控: test={test_name}, source={resolved_source}, watch_id={watch_id}")

        return {
            'success': True,
            'message': f'已启动文件监控\n'
                       f'测试：{test_name}\n'
                       f'监控路径：{test_file_path}\n'
                       f'轮询间隔：{poll_interval}s\n'
                       f'防抖延迟：{debounce_delay}s\n'
                       f'日志文件：{self._log_file}\n'
                       f'watch_id: {watch_id}\n\n'
                       f'文件改动时会自动重跑测试，结果累积到日志文件。\n'
                       f'使用 stop_watch() 停止监控，get_watch_results() 查看结果。',
            'watch_id': watch_id,
            'log_file': str(self._log_file),
        }

    def stop_watch(self) -> Dict[str, Any]:
        """
        停止文件监控

        Returns:
            {'success': bool, 'message': str, 'total_runs': int}
        """
        if not self._watching:
            return {
                'success': False,
                'message': '没有监控在运行',
                'total_runs': 0,
            }

        # 发送停止信号
        self._stop_event.set()

        # 等待线程结束
        if self._thread:
            self._thread.join(timeout=5.0)

        self._watching = False
        self._thread = None

        with self._results_lock:
            total_runs = len(self._results)

        self.logger.info(f"[watch] 停止监控: test={self._test_name}, total_runs={total_runs}")

        return {
            'success': True,
            'message': f'已停止文件监控\n'
                       f'总运行次数：{total_runs}\n'
                       f'日志文件：{self._log_file}',
            'total_runs': total_runs,
            'log_file': str(self._log_file) if self._log_file else None,
        }

    def get_results(self) -> Dict[str, Any]:
        """
        获取累积的测试结果

        Returns:
            {'success': bool, 'results': list, 'count': int}
        """
        with self._results_lock:
            results_copy = list(self._results)

        return {
            'success': True,
            'results': results_copy,
            'count': len(results_copy),
            'watching': self._watching,
            'test_name': self._test_name,
            'log_file': str(self._log_file) if self._log_file else None,
        }

    def _watch_loop(self):
        """后台监控循环"""
        self.logger.info(f"[watch] 监控线程启动: test={self._test_name}")

        # 首次运行一次测试（基线）
        self._run_test_and_record("initial_run")

        while not self._stop_event.is_set():
            try:
                # 扫描文件，检测改动
                changed_files = self._detect_changes()

                if changed_files:
                    self.logger.info(f"[watch] 检测到文件改动: {changed_files}")

                    # 防抖延迟
                    time.sleep(self._debounce_delay)

                    # 再次检测（避免 debounce 期间的改动被忽略）
                    changed_files2 = self._detect_changes()
                    if changed_files2:
                        changed_files.extend(changed_files2)
                        changed_files = list(set(changed_files))

                    # 运行测试
                    trigger = f"file_change: {', '.join(changed_files[:3])}"
                    self._run_test_and_record(trigger)

                    # 更新文件修改时间缓存
                    self._scan_files()

                # 等待下一次轮询
                self._stop_event.wait(self._poll_interval)

            except Exception as e:
                self.logger.error(f"[watch] 监控循环异常: {e}")
                time.sleep(1.0)

        self.logger.info(f"[watch] 监控线程结束: test={self._test_name}")

    def _scan_files(self):
        """扫描监控路径，更新文件修改时间缓存"""
        for path in self._watch_paths:
            if path.is_file():
                try:
                    mtime = path.stat().st_mtime
                    self._file_mtimes[str(path)] = mtime
                except (OSError, IOError):
                    pass
            elif path.is_dir():
                # 递归扫描 .lua 文件
                for lua_file in path.rglob('*.lua'):
                    try:
                        mtime = lua_file.stat().st_mtime
                        self._file_mtimes[str(lua_file)] = mtime
                    except (OSError, IOError):
                        pass

    def _detect_changes(self) -> List[str]:
        """检测文件改动，返回改动的文件列表"""
        changed = []
        for path_str, old_mtime in self._file_mtimes.items():
            path = Path(path_str)
            if not path.exists():
                continue
            try:
                new_mtime = path.stat().st_mtime
                if new_mtime > old_mtime:
                    changed.append(path_str)
            except (OSError, IOError):
                pass
        return changed

    def _run_test_and_record(self, trigger: str):
        """运行测试并记录结果"""
        self.logger.info(f"[watch] 触发测试: trigger={trigger}")

        start_time = time.time()
        try:
            result = self.desktop_runner.run_unit_test(self._test_name, self._source_dir, timeout=10)
            elapsed = time.time() - start_time

            # 构造记录
            record = {
                'timestamp': datetime.now().isoformat(),
                'trigger': trigger,
                'test_name': self._test_name,
                'success': result.get('success', False),
                'failure_type': result.get('failure_type'),
                'error': result.get('error'),
                'elapsed': elapsed,
                'details': result.get('details', ''),
            }

            # 累积结果
            with self._results_lock:
                self._results.append(record)

            # 写入日志文件
            if self._log_file:
                try:
                    with open(self._log_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(record, ensure_ascii=False) + '\n')
                except (IOError, OSError) as e:
                    self.logger.warning(f"[watch] 写入日志失败: {e}")

            status = "通过" if record['success'] else f"失败({record['failure_type']})"
            self.logger.info(f"[watch] 测试完成: {status}, elapsed={elapsed:.2f}s")

        except Exception as e:
            self.logger.error(f"[watch] 测试运行异常: {e}")
            record = {
                'timestamp': datetime.now().isoformat(),
                'trigger': trigger,
                'test_name': self._test_name,
                'success': False,
                'failure_type': 'runtime_error',
                'error': str(e),
                'elapsed': time.time() - start_time,
            }
            with self._results_lock:
                self._results.append(record)
