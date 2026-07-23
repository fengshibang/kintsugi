#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块（通用版）

从基线 scripts/config.py 剥离框架耦合：
- compile_output_name 默认值改为 map.w3x
- w2l_path 去除框架专属 fallback
- 新增 test_dir / test_module_prefix 可配置项
- 保留 is_wsl() / 路径转换 / ${workspaceRoot} 等通用能力

配置加载优先级：配置文件 > 环境变量 > 默认路径
"""

import os
import sys
import platform
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple


def to_windows_path(path: str) -> str:
    """
    将 WSL 路径转换为 Windows 路径

    Args:
        path: WSL 路径或 Windows 路径

    Returns:
        Windows 格式的路径（统一使用反斜杠）
    """
    # 如果已经是 Windows 路径，直接返回
    if len(path) >= 2 and path[1] == ':':
        return path.replace('/', '\\')

    # 检查 WSL 路径格式（/mnt/d/...）
    path_str = str(path)
    if path_str.startswith('/mnt/'):
        drive = path_str[5].upper()
        rest = path_str[7:]
        return f"{drive}:\\{rest.replace('/', '\\')}"

    # 非 WSL 路径，使用 Path.resolve() 解析
    path = Path(path).resolve()
    path_str = str(path)
    if path_str.startswith('/mnt/'):
        drive = path_str[5].upper()
        rest = path_str[7:]
        return f"{drive}:\\{rest.replace('/', '\\')}"
    return path_str.replace('/', '\\')


def is_windows() -> bool:
    """检测是否在 Windows 环境下运行"""
    return os.name == 'nt' or platform.system() == 'Windows'


def is_wsl() -> bool:
    """检测是否在 WSL 环境下运行"""
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
            return 'microsoft' in version or 'wsl' in version
    except (IOError, OSError):
        return False


class Config:
    """War3 Tester 通用配置管理"""

    def __init__(self, project_root: Path = None):
        """
        初始化配置

        Args:
            project_root: 项目根目录。若为 None，使用 Path(__file__).parent.parent
                          （即 server/ 的父目录 = 插件根目录）
        """
        self.is_windows = is_windows()
        self.is_wsl = is_wsl()
        # 自解析路径：server/ 的父目录 = 插件根目录
        self.project_root = project_root or Path(__file__).parent.parent

        # 初始化 logger
        self.logger = logging.getLogger('war3-config')

        # 平台路径配置
        self.ydwe_path: Optional[Path] = None
        self.kkwe_path: Optional[Path] = None

        # 工具路径
        self.w2l_path: Optional[Path] = None

        # 其他配置
        self.log_level: str = "INFO"
        self.run_mode: str = "ydwe"  # ydwe 或 kkwe

        # 编译配置
        self.compile_source_dir: Path = self.project_root
        self.compile_output_path: Path = self.project_root
        # 默认值必须是 map.w3x
        self.compile_output_name: str = "map.w3x"

        # 测试目录与模块前缀可配置
        # test_dir: 测试文件所在目录名（相对于 source_dir/）
        self.test_dir: str = "auto-test"
        # test_module_prefix: require 时的模块前缀
        # 空串 = 同目录加载（引导脚本与测试文件同目录）
        # 非空 = prefix..name 走 require（如 'some.prefix.'）
        self.test_module_prefix: str = ""
        # test_bootstrap_template: 自定义引导模板路径
        # 空串 = 使用通用 server/lua_bootstrap.lua（默认行为）
        # 非空 = 用 resolve_path 解析后读取该文件作为 run_auto_test.lua 内容
        # 文件不存在时 fallback 到通用模板，不 crash
        self.test_bootstrap_template: str = ""
        # extra_package_path: 桌面测试专属 package.path（分号分隔多 path，相对 source_dir）
        # 由项目在 config.json -> test.extra_package_path 声明，插件读取后通过环境变量
        # LUA_EXTRA_PATH 传给 desktop_bootstrap 子进程，追加到 package.path。
        # 用于让点分 require（如 'script.src.xxx'）能相对 source_dir 解析。
        # 空串 = 不追加（兼容现有项目 + examples/minimal）
        self.extra_package_path: str = ""

        # M4: 失败诊断时 inspect_game 查询表达式列表（项目自定义，默认空=不查 inspect）
        # 项目通过 config.json -> test.inspect_queries 配置，如 ["Player(0):getGold()", "UnitObj.all_count()"]
        self.inspect_queries: List[str] = []

        # HTTP 服务器配置
        self.http_host: str = "0.0.0.0"
        self.http_port: int = 8766
        self.wsl_to_windows_ip: str = "172.30.48.1"  # WSL 访问 Windows 主机的 IP
        self.windows_to_wsl_ip: str = ""  # Windows 访问 WSL 的 IP

        # War3 进程名配置
        self.war3_process_names: List[str] = ['War3.exe', 'war3.exe', 'KKWE.exe', 'YDWE.exe', 'Warcraft III.exe']

        # War3 游戏日志目录
        self.war3_log_dir: Optional[Path] = None

        # take_screenshot 成功后默认自动调 VLM 判读(画面状态/UI/卡对话框/数值)
        # config.json 设 take_screenshot_auto_analyze=false 可关闭(个别项目关闭自动判读)
        self.take_screenshot_auto_analyze: bool = True

        # 多实例配置
        self.multi_instance: bool = False
        self.service_port_min: int = 8765
        self.service_port_max: int = 8775
        self.http_port_min: int = 8766
        self.http_port_max: int = 8776

        # 归档配置
        self.archive_dir: Path = self.project_root / 'logs' / 'archive'
        self.archive_result_retention_days: int = 30
        self.archive_screenshot_retention_days: int = 7
        self.archive_log_retention_days: int = 30

        # 加载配置
        self._load_config()

    def _load_config(self) -> None:
        """加载配置（优先级：配置文件 > 环境变量 > 默认路径）"""
        config_file = self.project_root / 'config.json'
        file_config = {}

        # 1. 读取配置文件
        if config_file.exists():
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # 1.5 提前解析编译目录（供 .env 加载与 w2l 项目内查找使用）
        compile_config = file_config.get('compile', {})
        if compile_config:
            self.compile_source_dir = self.resolve_path(compile_config.get('source_dir', '.'))
            self.compile_output_path = self.resolve_path(compile_config.get('output_path', '.'))
            # 【红线 3】默认 map.w3x
            self.compile_output_name = compile_config.get('output_name', 'map.w3x')

        # 1.6 加载 .env（项目根目录优先、插件目录兜底），注入 os.environ（不覆盖系统变量）
        #     必须在读取 YDWE_PATH/KKWE_PATH/W2L_PATH 等环境变量之前完成
        self._load_dotenv()

        # 2. 加载 KKWE/YDWE 路径
        if file_config.get('ydwe_path'):
            self.ydwe_path = Path(file_config['ydwe_path'])
        elif os.getenv('YDWE_PATH'):
            self.ydwe_path = Path(os.getenv('YDWE_PATH'))

        if file_config.get('kkwe_path'):
            self.kkwe_path = Path(file_config['kkwe_path'])
        elif os.getenv('KKWE_PATH'):
            self.kkwe_path = Path(os.getenv('KKWE_PATH'))

        if not self.ydwe_path and not self.kkwe_path:
            self._load_default_paths()

        # 3. w2l.exe 查找推迟到第 6 步之后（依赖 compile_source_dir 做项目内搜索）

        # 4. 日志级别
        self.log_level = file_config.get('log_level') or os.getenv('LOG_LEVEL', 'INFO')

        # 5. 运行模式
        self.run_mode = file_config.get('run_mode') or os.getenv('WAR3_RUN_MODE', 'ydwe')

        # 6. 编译配置已在第 1.5 步提前解析（供 .env 加载使用）

        # 6.1 查找 w2l.exe（环境变量 > 项目目录相对位置 > 项目内递归搜索）
        #     这里用 compile_source_dir 算出初始默认值；编译时会按实际 source_dir 再查一次
        self.w2l_path = self.find_w2l_exe()

        # 6.5 测试配置（【红线 4】）
        test_config = file_config.get('test', {})
        if test_config:
            self.test_dir = test_config.get('test_dir', self.test_dir)
            self.test_module_prefix = test_config.get('test_module_prefix', self.test_module_prefix)
            self.test_bootstrap_template = test_config.get('test_bootstrap_template', self.test_bootstrap_template)
            # M4: inspect 查询表达式（项目自定义，默认空=不查 inspect）
            self.inspect_queries = test_config.get('inspect_queries', self.inspect_queries)
            # 桌面测试专属 package.path（项目声明，插件读取后通过 LUA_EXTRA_PATH 传给子进程）
            self.extra_package_path = test_config.get('extra_package_path', self.extra_package_path)

        # 7. HTTP 服务器配置
        http_config = file_config.get('http_server', {})
        if http_config:
            self.http_host = http_config.get('host', '0.0.0.0')
            self.http_port = http_config.get('port', 8766)

        # 8. 网络配置
        network_config = file_config.get('network', {})
        explicit_windows_ip = network_config.get('wsl_to_windows_ip')
        explicit_wsl_ip = network_config.get('windows_to_wsl_ip')

        if explicit_windows_ip:
            self.wsl_to_windows_ip = explicit_windows_ip
        elif self.is_wsl:
            detected_ip = self._auto_detect_windows_ip()
            if detected_ip:
                self.wsl_to_windows_ip = detected_ip

        if explicit_wsl_ip:
            self.windows_to_wsl_ip = explicit_wsl_ip
        else:
            self.windows_to_wsl_ip = self._get_wsl_ip()

        # 8. War3 进程名配置
        if file_config.get('war3_process_names'):
            self.war3_process_names = file_config['war3_process_names']
        elif os.getenv('WAR3_PROCESS_NAMES'):
            self.war3_process_names = [name.strip() for name in os.getenv('WAR3_PROCESS_NAMES').split(',')]

        # 8.5 War3 游戏日志目录
        if file_config.get('war3_log_dir'):
            self.war3_log_dir = self.resolve_path(file_config['war3_log_dir'])
        else:
            ydwe_path = self.ydwe_path or self._get_ydwe_candidates()[0]
            if ydwe_path:
                self.war3_log_dir = ydwe_path / 'logs'

        # 9. 多实例配置
        if file_config.get('multi_instance') is not None:
            self.multi_instance = bool(file_config['multi_instance'])
        if file_config.get('take_screenshot_auto_analyze') is not None:
            self.take_screenshot_auto_analyze = bool(file_config['take_screenshot_auto_analyze'])
        self.service_port_min = file_config.get('service_port_min', self.service_port_min)
        self.service_port_max = file_config.get('service_port_max', self.service_port_max)
        self.http_port_min = file_config.get('http_port_min', self.http_port_min)
        self.http_port_max = file_config.get('http_port_max', self.http_port_max)

        # 归档配置
        archive_config = file_config.get('archive', {})
        if archive_config:
            self.archive_result_retention_days = archive_config.get('result_retention_days', 30)
            self.archive_screenshot_retention_days = archive_config.get('screenshot_retention_days', 7)
            self.archive_log_retention_days = archive_config.get('log_retention_days', 30)

    def _auto_detect_windows_ip(self) -> str:
        """WSL 环境下自动检测 Windows IP"""
        try:
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('nameserver'):
                        ip = line.split()[-1]
                        parts = ip.split('.')
                        if len(parts) == 4 and all(p.isdigit() for p in parts):
                            return ip
        except (IOError, OSError):
            pass
        return ''

    def _get_wsl_ip(self) -> str:
        """自动获取 WSL 的 IP 地址"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ''

    def resolve_source_dir(self, source_dir) -> str:
        """把用户传入的 source_dir 归一为绝对路径字符串。

        None/空时回退 compile_source_dir。等价于：
          if source_dir: str(self.resolve_path(source_dir)) else str(self.compile_source_dir)

        v0.19.3: 收敛 mcp_server.py 中散落的「source_dir 归一化」重复模式。
        只收敛 fallback=compile_source_dir 的点；fallback=project_root 或无 fallback 的点不在此方法覆盖范围。
        """
        if source_dir:
            return str(self.resolve_path(source_dir))
        return str(self.compile_source_dir)

    def resolve_path(self, path: str) -> Path:
        """
        解析路径：支持绝对路径或相对路径（相对于项目根目录）
        支持 Windows 风格和 WSL 风格路径
        支持变量：${workspaceRoot}
        """
        if not path or path == '.':
            return self.project_root

        # 替换 ${workspaceRoot} 变量
        if '${workspaceRoot}' in path:
            workspace_root = self._detect_workspace_root()
            path = path.replace('${workspaceRoot}', str(workspace_root))

        p = Path(path)

        # Windows 绝对路径
        if len(path) >= 2 and path[1] == ':':
            if self.is_wsl:
                drive = path[0].lower()
                rest = path[2:].replace('\\', '/')
                return Path(f'/mnt/{drive}/{rest}').resolve()
            else:
                return Path(path).resolve()

        if p.is_absolute():
            return p.resolve()

        return (self.project_root / p).resolve()

    def _detect_workspace_root(self) -> Path:
        """检测工作区根目录：支持 git worktree"""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if result.returncode != 0:
                return self.project_root

            git_dir = result.stdout.strip()
            git_file = Path(git_dir)
            if git_file.exists() and git_file.is_file():
                with open(git_file, 'r') as f:
                    content = f.read().strip()
                    if content.startswith('gitdir:'):
                        worktree_path = content.split(':')[1].strip()
                        return Path(worktree_path).parent.parent.parent.resolve()

            return self.project_root.resolve()
        except Exception:
            return self.project_root

    def _load_default_paths(self) -> None:
        """加载默认搜索路径"""
        if self.is_wsl:
            self.default_ydwe_paths = [
                Path('/mnt/d/war3/YDWE'),
            ]
            self.default_kkwe_paths = [
                Path('/mnt/d/KKWE'),
            ]
        else:
            self.default_ydwe_paths = [
                Path('D:/war3/YDWE'),
            ]
            self.default_kkwe_paths = [
                Path('D:/KKWE'),
            ]

    def _load_dotenv(self) -> None:
        """
        从 .env 文件加载环境变量（纯标准库，零依赖）

        查找位置（都读，项目级优先；已存在的系统环境变量不被覆盖）：
          1. compile_source_dir / .env   （项目根目录，per-project）
          2. project_root / .env         （插件目录，全局兜底）

        .env 格式：每行 KEY=VALUE，支持 # 注释、空行、值两侧单/双引号、export 前缀。
        必须在读取 YDWE_PATH/KKWE_PATH/W2L_PATH 等环境变量之前调用。
        """
        candidates = [Path(self.project_root) / '.env']
        if self.compile_source_dir and Path(self.compile_source_dir) != Path(self.project_root):
            candidates.insert(0, Path(self.compile_source_dir) / '.env')

        for env_file in candidates:
            if env_file.exists() and env_file.is_file():
                self._parse_and_inject_env(env_file)

    def _parse_and_inject_env(self, env_file: Path) -> None:
        """解析单个 .env 文件并注入 os.environ（已存在的 key 不覆盖）"""
        try:
            text = env_file.read_text(encoding='utf-8')
        except OSError:
            return
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            # 去 export 前缀
            if line.startswith('export '):
                line = line[7:].lstrip()
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            # 剥离两侧匹配的引号
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)

    def find_w2l_exe(self, project_dir: Optional[Path] = None) -> Optional[Path]:
        """
        查找 w2l.exe（按项目目录的相对位置）

        每个地图项目通常自带 w3x2lni/w2l.exe，故以「项目目录的相对位置」为最高优先级，
        而不是只在插件目录下找。

        Args:
            project_dir: 项目目录（地图源码目录）。默认 compile_source_dir。
                         支持 Windows（D:\\...）与 WSL（/mnt/d/...）两种路径格式，
                         内部经 resolve_path 归一化到本机可访问路径。

        查找顺序（命中即返回）：
          1. 环境变量 W2L_PATH（最高优先级）
          2. 项目目录的相对位置：<project_dir>/w3x2lni/w2l.exe、<project_dir>/tools/w3x2lni/w2l.exe
          3. project_root / 插件目录下的同位置（兜底）
          4. 项目目录内递归搜索 w2l.exe（限深度 6，跳 node_modules/.git/logs 等噪声目录）

        全部未命中返回 None。
        """
        # 归一化项目目录到本机可访问路径（Windows/WSL 自适应）
        proj = self.resolve_path(str(project_dir)) if project_dir else self.compile_source_dir

        plugin_root = Path(__file__).parent.parent
        candidates: List[Path] = []

        # 1. 环境变量最高优先级
        env_w2l = os.getenv('W2L_PATH')
        if env_w2l:
            candidates.append(Path(env_w2l))

        # 2. 项目目录的相对位置（用户约定：每个项目自带 w3x2lni/）
        for rel in ('w3x2lni', 'tools/w3x2lni'):
            candidates.append(proj / rel / 'w2l.exe')

        # 3. project_root / 插件目录的同位置兜底
        for base in (self.project_root, plugin_root):
            for rel in ('w3x2lni', 'tools/w3x2lni'):
                candidates.append(Path(base) / rel / 'w2l.exe')

        for path in candidates:
            if path.exists():
                return path.resolve()

        # 4. 项目内递归搜索兜底
        return self._search_w2l_in_project(proj)

    def _search_w2l_in_project(self, root: Optional[Path], max_depth: int = 6) -> Optional[Path]:
        """
        在项目目录内递归搜索 w2l.exe

        - 限制最大深度（默认 6 层），跳过 node_modules/.git/logs 等噪声目录，避免慢
        - 同时匹配 w2l.exe（Windows）与 w2l（无扩展名，*nix 原生版）

        Args:
            root: 搜索根目录（通常为 compile_source_dir）
            max_depth: 最大递归深度

        Returns:
            命中的 w2l 可执行文件路径（已 resolve），未命中返回 None
        """
        if not root:
            return None
        root = Path(root)
        if not root.exists() or not root.is_dir():
            return None

        skip_dirs = {
            '.git', 'node_modules', '__pycache__', '.codegraph',
            'logs', 'archive', '.idea', '.vs', 'dist', 'build',
        }
        targets = {'w2l.exe', 'w2l'}

        stack: List[tuple] = [(root, 0)]
        while stack:
            current, depth = stack.pop()
            try:
                for entry in current.iterdir():
                    name_lower = entry.name.lower()
                    if entry.is_dir():
                        if name_lower in skip_dirs:
                            continue
                        if depth < max_depth:
                            stack.append((entry, depth + 1))
                    elif entry.is_file() and name_lower in targets:
                        return entry.resolve()
            except (PermissionError, OSError):
                continue
        return None

    def find_kkwe_path(self) -> Optional[Path]:
        """查找有效的 KKWE 安装路径"""
        if self.kkwe_path and self._is_valid_kkwe_path(self.kkwe_path):
            return self.kkwe_path
        for path in self._get_kkwe_candidates():
            if self._is_valid_kkwe_path(path):
                self.kkwe_path = path
                return path
        return self.find_ydwe_path()

    def find_ydwe_path(self) -> Optional[Path]:
        """查找有效的 YDWE 安装路径"""
        if self.ydwe_path and self._is_valid_ydwe_path(self.ydwe_path):
            return self.ydwe_path
        for path in self._get_ydwe_candidates():
            if self._is_valid_ydwe_path(path):
                self.ydwe_path = path
                return path
        return None

    def find_war3_platform(self, platform: str = None, fallback: bool = True) -> Optional[Tuple[Path, str]]:
        """
        查找指定的 War3 平台路径

        Args:
            platform: 指定平台 'ydwe', 'kkwe' 或 None（自动选择）
            fallback: 是否允许自动 fallback 到另一平台

        Returns:
            (平台路径，平台名称) 或 None
        """
        if platform == 'ydwe':
            path = self.find_ydwe_path()
            return (path, 'YDWE') if path else None
        elif platform == 'kkwe':
            path = self._find_kkwe_only()
            return (path, 'KKWE') if path else None
        else:
            run_mode = self.run_mode
            if run_mode == 'kkwe':
                path = self._find_kkwe_only()
                if path:
                    return (path, 'KKWE')
                if not fallback:
                    return None
                path = self.find_ydwe_path()
                if path:
                    self.logger.warning("KKWE 不存在，自动回退到 YDWE")
                    return (path, 'YDWE')
            else:
                path = self.find_ydwe_path()
                if path:
                    return (path, 'YDWE')
                if not fallback:
                    return None
                path = self._find_kkwe_only()
                if path:
                    self.logger.warning("YDWE 不存在，自动回退到 KKWE")
                    return (path, 'KKWE')
            return None

    def _find_kkwe_only(self) -> Optional[Path]:
        """只查找 KKWE"""
        if self.kkwe_path and self._is_valid_kkwe_path(self.kkwe_path):
            return self.kkwe_path
        for path in self._get_kkwe_candidates():
            if self._is_valid_kkwe_path(path):
                self.kkwe_path = path
                return path
        return None

    def _is_valid_kkwe_path(self, path: Path) -> bool:
        """检查路径是否是有效的 KKWE 安装"""
        if not path:
            return False
        actual_path = self.resolve_path(str(path))
        config_exe = actual_path / 'bin' / 'YDWEConfig.exe'
        game_exe1 = actual_path / 'KKWE.exe'
        game_exe2 = actual_path / 'Warcraft III.exe'
        return config_exe.exists() or game_exe1.exists() or game_exe2.exists()

    def _is_valid_ydwe_path(self, path: Path) -> bool:
        """检查路径是否是有效的 YDWE 安装"""
        if not path:
            return False
        actual_path = self.resolve_path(str(path))
        config_exe = actual_path / 'bin' / 'ydweconfig.exe'
        game_exe = actual_path / 'YDWE.exe'
        return config_exe.exists() or game_exe.exists()

    def _get_ydwe_candidates(self) -> List[Path]:
        """获取 YDWE 候选路径列表"""
        return getattr(self, 'default_ydwe_paths', [
            Path('/mnt/d/war3/YDWE') if self.is_wsl else Path('D:/war3/YDWE'),
        ])

    def _get_kkwe_candidates(self) -> List[Path]:
        """获取 KKWE 候选路径列表"""
        return getattr(self, 'default_kkwe_paths', [
            Path('/mnt/d/war3/KKWE') if self.is_wsl else Path('D:/kkwe'),
        ])

    def get_run_mode_with_source(self) -> Tuple[str, str]:
        """获取 run_mode 配置值及其来源"""
        config_file = self.project_root / 'config.json'
        if config_file.exists():
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                if file_config.get('run_mode'):
                    return (file_config['run_mode'], 'config_file')
            except (json.JSONDecodeError, IOError):
                pass
        env_run_mode = os.getenv('WAR3_RUN_MODE')
        if env_run_mode:
            return (env_run_mode, 'env')
        return (self.run_mode, 'default')

    def get_test_dir_path(self, source_dir: Path = None) -> Optional[Path]:
        """
        获取测试目录的完整路径

        Args:
            source_dir: 源码根目录，默认为 compile_source_dir

        Returns:
            测试目录的 Path 对象；source_dir 非有效 w2l 项目根时返回 None（拒绝生成，
            避免 source_dir 传错如多了 /map 导致 test_dir 错位成 map/map/... 污染项目目录）
        """
        base = source_dir or self.compile_source_dir
        # 项目根校验：source_dir 必须是有效 w2l 项目根（含 w3x2lni/ 或 tools/w3x2lni/）。
        # 防止 source_dir 传成 D:/x/proj/map（多了 /map）等错位路径，导致
        # test_dir = base/<test_dir> 拼出 base/map/map/script/... 的错误目录。
        if not self._is_w2l_project_root(base):
            self.logger.error(
                f'get_test_dir_path: source_dir 非有效 w2l 项目根（缺 w3x2lni/ 及 tools/w3x2lni/）: {base}，'
                f'可能 source_dir 传错（如多了子目录），拒绝生成 test_dir'
            )
            return None
        # 通用约定：测试目录在 <source_dir>/<test_dir>/
        return base / self.test_dir

    def _is_w2l_project_root(self, base: Path) -> bool:
        """判断 base 是否为有效 w2l 项目根（含 w3x2lni/ 或 tools/w3x2lni/ 编译工具目录）。"""
        return (base / 'w3x2lni').is_dir() or (base / 'tools' / 'w3x2lni').is_dir()

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """验证配置有效性"""
        errors: List[str] = []
        warnings: List[str] = []

        platform_info = self.find_war3_platform()
        if not platform_info:
            errors.append(
                "未找到 KKWE 或 YDWE 安装路径\n"
                f"  已检查路径：{', '.join(str(p) for p in self._get_kkwe_candidates() + self._get_ydwe_candidates())}\n"
                "  建议：设置环境变量 KKWE_PATH 或 YDWE_PATH，或在 config.json 中配置"
            )
        else:
            warnings.append(f"使用平台：{platform_info[1]} @ {platform_info[0]}")

        if not self.w2l_path:
            warnings.append(
                "默认位置未找到 w2l.exe（不影响编译：编译时会按实际项目目录的相对位置重新查找）\n"
                "  已搜索：环境变量 W2L_PATH；compile_source_dir、插件目录下的\n"
                "         tools/w3x2lni/、w3x2lni/；并在 compile_source_dir 内递归搜索\n"
                "  建议：在地图项目目录下放置 w3x2lni/w2l.exe，或设置环境变量 W2L_PATH 指向 w2l.exe"
            )

        return len(errors) == 0, errors, warnings

    def get_war3_log_file_path(self, player_id: int = 1, date: str = None) -> Optional[Path]:
        """获取指定玩家的 War3 日志文件路径"""
        if not self.war3_log_dir:
            return None
        if not self.war3_log_dir.exists():
            return None
        if date is None:
            date = datetime.now().strftime('%Y%m%d')

        old_format = self.war3_log_dir / f"玩家{player_id}_{date}.log"
        if old_format.exists():
            return old_format

        date_dashed = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        pattern = f"玩家{player_id}_玩家{player_id}_log-{date_dashed}-*.log"
        matches = sorted(self.war3_log_dir.glob(pattern))
        if matches:
            return matches[-1]

        return None


def is_port_available(port: int, host: str = '0.0.0.0') -> bool:
    """检测端口是否可用"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        return False


def find_available_port(start_port: int, end_port: int, host: str = '0.0.0.0') -> Optional[int]:
    """在指定范围内查找第一个可用的端口"""
    for port in range(start_port, end_port + 1):
        if is_port_available(port, host):
            return port
    return None
