# -*- coding: utf-8 -*-
"""
日志系统模块
支持UTF-8编码，同时输出到控制台和文件
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class Logger:
    """日志管理类"""
    
    def __init__(self, name='AppInstaller', log_dir=None):
        """
        初始化日志系统
        
        Args:
            name: 日志记录器名称
            log_dir: 日志文件目录路径
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器
        if self.logger.handlers:
            return
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        # 确保控制台使用UTF-8编码
        if hasattr(console_handler.stream, 'reconfigure'):
            console_handler.stream.reconfigure(encoding='utf-8')
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 日志文件名包含日期
            log_filename = f"installer_{datetime.now().strftime('%Y%m%d')}.log"
            log_file = log_dir / log_filename
            
            file_handler = logging.FileHandler(
                log_file, 
                mode='a', 
                encoding='utf-8'
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message):
        """记录INFO级别日志"""
        self.logger.info(message)
    
    def warning(self, message):
        """记录WARNING级别日志"""
        self.logger.warning(message)
    
    def error(self, message):
        """记录ERROR级别日志"""
        self.logger.error(message)
    
    def debug(self, message):
        """记录DEBUG级别日志"""
        self.logger.debug(message)


# 全局日志实例（延迟初始化）
_global_logger = None


def get_logger(log_dir=None):
    """
    获取全局日志实例
    
    Args:
        log_dir: 日志目录路径（仅首次初始化时有效）
    
    Returns:
        Logger实例
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger(log_dir=log_dir)
    return _global_logger

