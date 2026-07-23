#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProjectScaffolder - 项目结构分析 + TDD 测试骨架生成模块

职责：
- 扫描项目地图脚本目录，返回结构化分析（纯静态，只读）
- 生成 TDD 测试骨架（unit/integration/e2e 三层）
- 创建测试文件并写入骨架内容

零反向依赖：只依赖标准库 + 收 config 参数，不引用 mcp_server / test_batch_runner / http_receiver

v0.19.6(候选③): 从 mcp_server.py 外提。方法体逐字搬迁，module_dirs 改从 config 读（通用化，
默认值逐字 = 原 18 项，行为不变）。
"""

import logging
from pathlib import Path
from datetime import datetime


class ProjectScaffolder:
    """
    项目结构分析 + TDD 测试骨架生成器。

    覆盖 mcp_server._get_project_info / _scaffold_test / _generate_test_skeleton 的全部逻辑。

    构造参数：
        config: Config 实例
        logger: 日志记录器（可选）
    """

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def get_project_info(self, source_dir: str, max_depth: int = 3) -> str:
        """
        扫描项目地图脚本目录，返回结构化分析（纯静态，只读）。

        分析内容：
        1. 目录树概要（限 max_depth 层）
        2. 各模块子目录文件计数（按约定子目录名识别）
        3. 代码行数统计（按文件扩展名分组）
        4. 关键入口文件列表（init.lua 等）

        Args:
            source_dir: 源码根目录（通常为 config.compile_source_dir）
            max_depth: 目录树扫描最大深度

        Returns:
            格式化的分析文本
        """
        root = Path(source_dir)
        if not root.exists() or not root.is_dir():
            return f"[WARN] 源码目录不存在或不是目录：{source_dir}"

        # 跳过的噪声目录
        skip_dirs = {
            '.git', 'node_modules', '__pycache__', '.codegraph',
            'logs', 'archive', '.idea', '.vs', 'dist', 'build',
            '.claude', 'w3x2lni',
        }

        # 关注的模块子目录（War3 ECS 项目约定）
        # v0.19.6: 从 config 读（通用化，默认值逐字 = 原 18 项，行为不变）
        module_dirs = set(self.config.project_info_module_dirs)

        # 关键入口文件名
        entry_files = {'init.lua', 'main.lua', 'app.lua', 'config.lua', 'bootstrap.lua'}

        # === 1. 目录树 + 2. 模块计数 + 3. 行数统计 + 4. 入口文件 ===
        dir_tree_lines = []
        module_counts = {}  # module_name -> file_count
        ext_line_counts = {}  # ext -> total_lines
        ext_file_counts = {}  # ext -> file_count
        entry_file_list = []  # list of relative paths
        total_files = 0
        total_lines = 0

        def scan_dir(current: Path, depth: int, prefix: str):
            """递归扫描目录"""
            nonlocal total_files, total_lines
            if depth > max_depth:
                return

            try:
                entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except (PermissionError, OSError):
                return

            for entry in entries:
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    if entry.name in skip_dirs:
                        continue
                    if depth < max_depth:
                        dir_tree_lines.append(f"{prefix}📁 {entry.name}/")
                        scan_dir(entry, depth + 1, prefix + "  ")
                    else:
                        # 最深层只列目录名，不递归
                        dir_tree_lines.append(f"{prefix}📁 {entry.name}/")
                elif entry.is_file():
                    total_files += 1
                    rel = str(entry.relative_to(root))
                    ext = entry.suffix.lower()
                    if ext:
                        ext_file_counts[ext] = ext_file_counts.get(ext, 0) + 1
                        try:
                            line_count = sum(1 for _ in entry.open('r', encoding='utf-8', errors='ignore'))
                        except (OSError, PermissionError):
                            line_count = 0
                        ext_line_counts[ext] = ext_line_counts.get(ext, 0) + line_count
                        total_lines += line_count

                    # 模块目录归属统计（只看直接子目录）
                    parts = entry.relative_to(root).parts
                    if len(parts) >= 2 and parts[0] in module_dirs:
                        mod = parts[0]
                        module_counts[mod] = module_counts.get(mod, 0) + 1

                    # 入口文件
                    if entry.name in entry_files:
                        entry_file_list.append(rel)

        dir_tree_lines.append(f"📁 {root.name}/")
        scan_dir(root, 1, "  ")

        # === 组装输出 ===
        out = []
        out.append(f"## 项目结构分析")
        out.append(f"扫描目录：{root}")
        out.append(f"扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append(f"总文件数：{total_files}  总代码行数：{total_lines}")
        out.append("")

        # 模块计数
        out.append("### 模块文件计数")
        if module_counts:
            for mod in sorted(module_counts.keys()):
                out.append(f"  {mod}: {module_counts[mod]} 个文件")
        else:
            out.append("  （未发现约定的模块子目录）")
        out.append("")

        # 行数按扩展名
        out.append("### 代码行数统计（按扩展名）")
        if ext_line_counts:
            for ext in sorted(ext_line_counts.keys(), key=lambda e: -ext_line_counts.get(e, 0)):
                out.append(f"  {ext}: {ext_file_counts.get(ext, 0)} 个文件, {ext_line_counts[ext]} 行")
        else:
            out.append("  （无代码文件）")
        out.append("")

        # 入口文件
        out.append("### 关键入口文件")
        if entry_file_list:
            for ef in sorted(entry_file_list):
                out.append(f"  {ef}")
        else:
            out.append("  （未发现 init.lua / main.lua 等入口文件）")
        out.append("")

        # 目录树（截断防爆）
        out.append(f"### 目录树（max_depth={max_depth}）")
        max_tree_lines = 200
        if len(dir_tree_lines) > max_tree_lines:
            out.extend(dir_tree_lines[:max_tree_lines])
            out.append(f"  ... 已截断（共 {len(dir_tree_lines)} 行，显示前 {max_tree_lines} 行）")
        else:
            out.extend(dir_tree_lines)

        return "\n".join(out)

    def scaffold_test(self, module: str, layer: str, name: str = None, source_dir: str = None) -> dict:
        """
        生成 TDD 测试骨架（M3 方向 D）

        Args:
            module: 模块名（如 'talent'、'skill_a00d'）
            layer: 测试层 'unit' | 'integration' | 'e2e'
            name: 测试名（可选，默认 test_<layer>_<module>）
            source_dir: 源码目录

        Returns:
            {'success': bool, 'file': str, 'message': str, 'error': str | None}
        """
        # v0.19.3: 收敛 source_dir 归一化
        resolved = self.config.resolve_source_dir(source_dir)
        test_dir = self.config.get_test_dir_path(resolved)
        if test_dir is None:
            return {
                'success': False,
                'file': None,
                'message': '',
                'error': f'source_dir 非有效 w2l 项目根: {resolved}',
            }

        test_dir.mkdir(parents=True, exist_ok=True)

        # 生成测试文件名
        if name:
            test_name = name if name.startswith('test_') else f'test_{name}'
        else:
            test_name = f'test_{layer}_{module}'

        test_file = f'{test_name}.lua'
        test_file_path = test_dir / test_file

        # 检查文件是否已存在
        if test_file_path.exists():
            return {
                'success': False,
                'file': str(test_file_path),
                'message': '',
                'error': f'测试文件已存在: {test_file_path}',
            }

        # 生成骨架内容
        content = self.generate_test_skeleton(module, layer, test_name)

        try:
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {
                'success': True,
                'file': str(test_file_path),
                'message': f'已生成测试骨架: {test_file}\n\n'
                           f'下一步:\n'
                           f'1. 编辑 {test_file} 填充测试逻辑\n'
                           f'2. 运行 tdd_red(test_name="{test_name}", layer="{layer}") 确认 Red\n'
                           f'3. 实现功能代码\n'
                           f'4. 运行 tdd_green(test_name="{test_name}", layer="{layer}") 确认 Green',
                'error': None,
            }
        except Exception as e:
            return {
                'success': False,
                'file': str(test_file_path),
                'message': '',
                'error': f'写入文件失败: {e}',
            }

    def generate_test_skeleton(self, module: str, layer: str, test_name: str) -> str:
        """生成测试骨架内容（通用，不硬编码项目路径）"""

        # 根据 layer 选择不同的引导方式
        if layer == 'unit':
            # 桌面单测：使用 jass_mock + assertions
            header = f'-- @layer unit\n'
            header += f'-- TDD 测试骨架: {test_name}\n'
            header += f'-- 桌面纯逻辑单测（秒级反馈）\n\n'
            header += f'-- 加载插件内置断言库（由 desktop_bootstrap 注入到 _G.__war3_tester_assertions）\n'
            header += f'local assert = _G.__war3_tester_assertions or {{}}\n'
            header += f'local assertEquals = assert.assertEquals or function(a, b, msg) error(msg or "assertion failed") end\n'
            header += f'local assertTrue = assert.assertTrue or function(cond, msg) if not cond then error(msg or "assertTrue failed") end end\n\n'
            header += f'-- 加载 jass mock（由 desktop_bootstrap 注入到 _G.__war3_tester_jass_mock）\n'
            header += f'-- local jass_mock = _G.__war3_tester_jass_mock\n\n'
            # unit 层使用 _G.__test_result（desktop_bootstrap 解析它）
            result_reporting = f'''
-- ============================================================================
-- 测试入口（最小契约: RunAutoTest）
-- ============================================================================

function RunAutoTest()
    print("=== 开始测试: {test_name} ===")

    local success, err = pcall(test_case_1)
    if not success then
        print("[FAIL] test_case_1: " .. tostring(err))
        -- 桌面层：设 _G.__test_result 让 desktop_bootstrap 解析为失败
        _G.__test_result = {{success=false, test_name='{test_name}', details=tostring(err), cases={{}}}}
        return
    end

    print("=== 测试完成: {test_name} ===")
    -- 桌面层：设 _G.__test_result 让 desktop_bootstrap 解析为成功
    _G.__test_result = {{success=true, test_name='{test_name}', details='all passed', cases={{}}}}
end
'''
        else:
            # integration/e2e: 游戏内测试，必须 HTTP POST /result
            header = f'-- @layer {layer}\n'
            header += f'-- TDD 测试骨架: {test_name}\n'
            header += f'-- 游戏内测试（需编译+启动游戏）\n\n'
            header += f'-- 加载插件内置断言库（由 lua_bootstrap 注入到 _G.__war3_tester_assertions）\n'
            header += f'local assert = _G.__war3_tester_assertions or {{}}\n'
            header += f'local assertEquals = assert.assertEquals or function(a, b, msg) error(msg or "assertion failed") end\n'
            header += f'local assertTrue = assert.assertTrue or function(cond, msg) if not cond then error(msg or "assertTrue failed") end end\n\n'
            # integration/e2e 层必须 HTTP POST（test_commit 不读 _G.__test_result）
            # 【通用性】不硬编码任何项目专有 require 路径，由项目自身提供 HTTP 客户端
            result_reporting = f'''
-- ============================================================================
-- HTTP POST 结果上报（通用骨架 - 需项目适配）
-- ============================================================================
-- 【重要】integration/e2e 层必须 HTTP POST 结果到 8766，test_commit 才能接收。
-- _G.__test_result 仅桌面层（desktop_bootstrap）使用，游戏内无效。
-- data 必须含 assertions 字段，_classify_failure 才能判定 assertion 失败。
--
-- 【适配说明】
-- War3 定制 Lua 通常无 luasocket（socket.http 不可用），需用项目/平台自身 HTTP 客户端。
-- 下方 http_post_result 是占位实现，需项目根据自身框架适配 HTTP POST 逻辑。
-- 参考范例：examples/wzns/run_auto_test.framework.lua（wzns 框架的 HTTP 适配器）
-- ============================================================================

local function http_post_result(test_name, success, details, assertions)
    local data = {{
        test_name = test_name,
        success = success,
        details = details or '',
        -- assertions 字段：_classify_failure 读取它判定 failure_type=assertion
        -- 格式: {{name='...', passed=true|false, message='...'}}, ...}}
        assertions = assertions or {{}},
    }}

    -- TODO: 项目适配 - 使用项目自身的 HTTP 客户端 POST 结果到 8766
    -- 常见模式（需项目实现）：
    --   local http_client = require('<your_project>.http_client')
    --   http_client.post('http://127.0.0.1:8766/result', data)
    --
    -- 参考范例：examples/wzns/run_auto_test.framework.lua 的 exportResults 函数
    --
    -- 占位实现：仅打印日志，实际游戏内不会上报（test_commit 会超时）
    print(string.format('[HTTP] TODO: 需项目适配 HTTP POST 到 http://127.0.0.1:8766/result'))
    print(string.format('[HTTP] test_name=%s, success=%s', test_name, tostring(success)))

    -- fallback 到 _G.__test_result（仅桌面层有效，游戏内 test_commit 不读）
    _G.__test_result = data
end

-- ============================================================================
-- 测试入口（最小契约: RunAutoTest）
-- ============================================================================

function RunAutoTest()
    print("=== 开始测试: {test_name} ===")

    local success, err = pcall(test_case_1)
    if not success then
        print("[FAIL] test_case_1: " .. tostring(err))
        -- 游戏内：HTTP POST 结果到 8766（test_commit 依赖此机制）
        -- assertions 含 passed=false 让 _classify_failure 判定 assertion（tdd_red -> red_valid）
        http_post_result('{test_name}', false, tostring(err),
            {{name='test_case_1', passed=false, message=tostring(err)}})
        return
    end

    print("=== 测试完成: {test_name} ===")
    -- 游戏内：HTTP POST 结果到 8766（test_commit 依赖此机制）
    http_post_result('{test_name}', true, 'all passed',
        {{name='test_case_1', passed=true}})
end
'''

        # TDD 三段式骨架（通用部分）
        skeleton = f'''
-- ============================================================================
-- 测试模块: {module}
-- 测试层: {layer}
-- ============================================================================

-- Arrange: 准备测试数据和环境
local function setup()
    -- TODO: 初始化测试数据
    -- 例如: local data = {{id = 1, name = "test"}}
    return {{}}
end

-- Act: 执行被测功能
local function execute(data)
    -- TODO: 调用被测函数
    -- 例如: local result = MyModule.process(data)
    -- return result
    return nil
end

-- Assert: 验证结果
local function verify(result)
    -- TODO: 断言检查结果
    -- 例如: assertEquals(result.id, 1, "ID 应该为 1")
    -- 例如: assertTrue(result.success, "应该成功")
end

-- ============================================================================
-- 测试用例
-- ============================================================================

local function test_case_1()
    print("[TEST] test_case_1: 基本功能测试")

    -- Arrange
    local data = setup()

    -- Act
    local result = execute(data)

    -- Assert
    verify(result)

    print("[PASS] test_case_1")
end

'''

        return header + skeleton + result_reporting
