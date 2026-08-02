"""video-idea-extractor plugin 环境脚手架。

一键配好:vie 依赖 + .env 模板 + ffmpeg 检查 + vie 验证。
跑法(在 plugin 目录,含 pyproject.toml):python install.py
可重复跑(幂等)。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
NEED_PY = (3, 13)


def step(msg):
    print(f'\n==> {msg}')


def ok(msg):
    print(f'  ✓ {msg}')


def warn(msg):
    print(f'  ⚠ {msg}')


def main():
    print(f'video-idea-extractor 环境脚手架(plugin 目录:{PLUGIN_DIR})')

    # 1. Python 版本
    step(f'检查 Python(需 >={".".join(map(str, NEED_PY))})')
    print(f'  当前:Python {sys.version.split()[0]} @ {sys.executable}')
    if sys.version_info < NEED_PY:
        warn(f'Python 版本过低,需 >={".".join(map(str, NEED_PY))}。请升级后重跑。')
        return 1
    ok('版本满足')

    # 2. pip install -e .
    step('安装依赖(pip install -e .)')
    rc = subprocess.call([sys.executable, '-m', 'pip', 'install', '-e', str(PLUGIN_DIR)])
    if rc != 0:
        warn('pip install 失败(检查 pip/网络/权限)后重跑。')
        return 1
    ok('vie 命令 + openai SDK 已装')

    # 3. ffmpeg
    step('检查 ffmpeg')
    ffmpeg = shutil.which('ffmpeg')
    env_bin = os.environ.get('VIE_FFMPEG_BIN', '')
    cand = ffmpeg
    if not cand and env_bin:
        for name in ('ffmpeg.exe', 'ffmpeg'):
            p = Path(env_bin) / name
            if p.is_file():
                cand = str(p)
                break
    if cand:
        ok(f'ffmpeg 可用:{cand}')
    else:
        warn('未找到 ffmpeg。请装 ffmpeg 加 PATH,或设 VIE_FFMPEG_BIN 指 ffmpeg 所在目录。')
        print('    例(Windows):set VIE_FFMPEG_BIN=D:/path/to/ffmpeg_dir')

    # 4. .env 模板
    step('配置 .env')
    env_path = PLUGIN_DIR / '.env'
    template = (
        'DASHSCOPE_API_KEY=\n'
        'DASHSCOPE_BASE_URL=http://your-proxy:3000\n'
        'MODEL=qwen3.7-plus\n'
        'VIE_SUPPORTS_VIDEO=1\n'
    )
    if env_path.exists():
        print(f'  .env 已存在:{env_path}(确认 DASHSCOPE_API_KEY 已填)')
    else:
        env_path.write_text(template, encoding='utf-8')
        print(f'  已生成 .env 模板:{env_path}')
        print('  请编辑填 DASHSCOPE_API_KEY(必需)和代理地址。')

    # 5. 验证 vie
    step('验证 vie 命令')
    scripts_dir = Path(sysconfig.get_path('scripts'))
    exe = 'vie.exe' if os.name == 'nt' else 'vie'
    vie = shutil.which(exe) or str(scripts_dir / exe)
    if Path(vie).is_file():
        r = subprocess.call([vie, 'analyze', '--help'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r == 0:
            ok(f'vie 可用:{vie}')
        else:
            warn(f'vie 调用退出码 {r}(可能 .env/key 未配,但命令本身已装)')
    else:
        warn(f'vie 未找到(预期 {vie})。重开终端刷新 PATH 后重试,或手动 pip install -e .')

    print('\n=== 下一步 ===')
    print('1. 编辑 .env 填 DASHSCOPE_API_KEY(若未填)')
    print('2. 确保 ffmpeg 可用(PATH 或 VIE_FFMPEG_BIN)')
    print('3. 在 Claude Code 会话说 "分析视频 <路径>" 或 /video-idea-extractor')
    print('   或命令行:vie analyze <视频> --format md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
