#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志模块（通用版）

提供结构化日志输出，支持控制台和文件日志。
从基线 scripts/logger.py 直接迁移，无框架耦合。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "war3-mcp", level: str = "INFO") -> logging.Logger:
    """
    设置日志器

    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)

    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # 清除已有处理器
    logger.handlers.clear()

    # 控制台处理器（输出到 stderr，不干扰 stdout 的 JSON-RPC）
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（日志写入 server/logs/ 目录）
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"mcp-war3-{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger
