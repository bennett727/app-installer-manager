# -*- coding: utf-8 -*-
"""
配置管理模块
管理默认安装路径等配置信息
"""

import json
from pathlib import Path
import ctypes
import sys


class Config:
    """配置管理器"""
    
    DEFAULT_CONFIG = {
        'default_base_path': '',
        'default_timeout': 600,  # 默认安装超时时间（秒）
        'network_query_timeout': 3,  # 网络查询超时时间（秒）
    }
    
    def __init__(self, config_file: str = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径（可选）
        """
        self.config_file = Path(config_file) if config_file else None
        self.config = self.DEFAULT_CONFIG.copy()
        
        # 如果配置文件存在，加载配置
        if self.config_file and self.config_file.exists():
            self.load_config()
    
    def load_config(self):
        """从文件加载配置"""
        try:
            if self.config_file and self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
        except Exception as e:
            import logging
            logging.warning('配置加载失败: %s', e)
    
    def save_config(self):
        """保存配置到文件"""
        try:
            if self.config_file:
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            import logging
            logging.warning('配置保存失败: %s', e)
    
    def get(self, key: str, default=None):
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
        
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """
        设置配置项
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.config[key] = value
        self.save_config()
    
    def get_default_base_path(self) -> str:
        """获取默认基础安装路径"""
        return self.config.get('default_base_path', '')
    
    def set_default_base_path(self, path: str):
        """
        设置默认基础安装路径
        
        Args:
            path: 新的默认路径
        """
        self.set('default_base_path', path)
    
    @staticmethod
    def is_admin() -> bool:
        """
        检查是否以管理员权限运行
        
        Returns:
            是否是管理员
        """
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    
    @staticmethod
    def check_write_permission(directory: Path) -> bool:
        """
        检查目录写权限
        
        Args:
            directory: 要检查的目录
        
        Returns:
            是否有写权限
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
            test_file = directory / '.write_test'
            test_file.touch()
            test_file.unlink()
            return True
        except Exception:
            return False
    
    @staticmethod
    def request_admin_privileges():
        """
        请求管理员权限（重启程序）
        """
        try:
            if sys.platform == 'win32':
                # 以管理员权限重新运行程序
                ctypes.windll.shell32.ShellExecuteW(
                    None, 
                    "runas", 
                    sys.executable, 
                    " ".join(sys.argv), 
                    None, 
                    1
                )
                sys.exit(0)
        except Exception:
            pass


import hashlib
from datetime import datetime

# ============================================================
# 有效期管理系统
# ============================================================

# 默认有效期截止日期（格式：年-月-日）
EXPIRATION_DATE = '2026-06-16'

# 激活码哈希表（SHA256 前16位）
_ACTIVATION_CODES = {
    '月卡': {'hash': '64309852a897cc62', 'months': 1, 'desc': '延长 1 个月'},
    '半年卡': {'hash': '131cc4d4de5ec615', 'months': 6, 'desc': '延长 6 个月'},
    '永久': {'hash': '5b9ec49a32d95ab4', 'value': 'forever', 'desc': '永久激活'},
}


def _hash_code(code: str) -> str:
    """对输入码做 SHA256 哈希"""
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def activate(code: str, config_path: Path) -> tuple:
    """
    尝试激活
    
    Args:
        code: 用户输入的激活码
        config_path: 配置文件路径
    
    Returns:
        (success: bool, message: str)
    """
    code_hash = _hash_code(code)

    for name, info in _ACTIVATION_CODES.items():
        if code_hash == info['hash']:
            config = _read_config(config_path)

            if 'value' in info and info['value'] == 'forever':
                config['expiration'] = 'forever'
                _save_config(config_path, config)
                return True, '激活成功！\n\n已升级为永久版本，无限期使用。'

            months = info.get('months', 0)
            if months > 0:
                now = datetime.now()
                old_exp = datetime.strptime(EXPIRATION_DATE, '%Y-%m-%d')
                base_date = now if now > old_exp else old_exp
                # add months
                y, m = base_date.year, base_date.month
                m += months
                while m > 12:
                    y += 1
                    m -= 12
                # 处理日期溢出（如1月31日+1个月=2月28/29日）
                import calendar
                max_day = calendar.monthrange(y, m)[1]
                day = min(base_date.day, max_day)
                new_date = base_date.replace(year=y, month=m, day=day)
                new_date_str = new_date.strftime('%Y-%m-%d')

                config['expiration'] = new_date_str
                _save_config(config_path, config)
                return True, f'激活成功！\n\n有效期已延长到：{new_date_str}\n（{info["desc"]}）'

    return False, '激活码无效，请检查后重试。\n\n如有疑问请联系：只是向着'


def _read_config(config_path: Path) -> dict:
    """读取配置文件"""
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_config(config_path: Path, config: dict):
    """保存配置文件"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_effective_expiration(config_path: Path = None) -> str:
    """
    获取实际生效的截止日期

    Returns:
        'forever' 或 日期字符串 'YYYY-MM-DD'
    """
    if config_path:
        try:
            config = _read_config(config_path)
            ext = config.get('expiration', '')
            if ext == 'forever':
                return 'forever'
            if ext:
                return ext
        except Exception:
            # 配置文件损坏，返回极早日期触发过期
            return '2000-01-01'
    return EXPIRATION_DATE


def check_expiration(config_path: Path = None):
    """
    检查软件有效期
    
    Returns:
        (status, message, days_remaining) 元组
        status: 'valid' 正常 / 'warning' 临期 / 'expired' 已过期
    """
    effective = get_effective_expiration(config_path)
    if effective == 'forever':
        return 'valid', '永久授权', 9999

    try:
        expiration = datetime.strptime(effective, '%Y-%m-%d')
        now = datetime.now()
        days_left = (expiration - now).days

        if days_left <= 0:
            return 'expired', (
                f'软件使用期限已到期！\n\n'
                f'有效期至：{effective}\n'
                f'已过期：{abs(days_left)} 天\n\n'
                f'如需续期，请联系开发者：\n'
                f'只是向着'
            ), days_left

        if days_left <= 7:
            return 'warning', (
                f'许可证即将到期！\n\n'
                f'有效期至：{effective}\n'
                f'仅剩 {days_left} 天\n\n'
                f'如需续期，请联系开发者：\n'
                f'只是向着'
            ), days_left

        return 'valid', '', days_left

    except Exception:
        # 异常时采用 fail-closed 策略，避免被篡改的配置绕过检查
        return 'expired', '配置异常，请重新激活', 0


def get_expiration_info(config_path: Path = None):
    """获取有效期信息，供关于页面展示"""
    effective = get_effective_expiration(config_path)
    if effective == 'forever':
        return '永久有效', '无需续期'

    try:
        expiration = datetime.strptime(effective, '%Y-%m-%d')
        now = datetime.now()
        days_left = (expiration - now).days
        if days_left < 0:
            days_left = 0
        return effective, f'剩余 {days_left} 天'
    except Exception:
        return effective, ''


class WorkspaceManager:
    """工作目录管理器"""
    
    def __init__(self, base_dir: Path):
        """
        初始化工作目录管理器
        
        Args:
            base_dir: 程序根目录
        """
        self.base_dir = base_dir
        self.data_dir = base_dir / 'data'
        self.packages_dir = self.data_dir / 'packages'
        self.logs_dir = self.data_dir / 'logs'
        self.db_path = self.data_dir / 'app_manager.db'
    
    def initialize(self) -> bool:
        """
        初始化工作目录
        
        Returns:
            是否成功初始化
        """
        try:
            # 创建目录结构
            self.data_dir.mkdir(exist_ok=True)
            self.packages_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)
            
            # 测试写权限
            if not Config.check_write_permission(self.data_dir):
                return False
            
            return True
        
        except Exception:
            return False
    
    def get_package_copy_path(self, original_filename: str) -> Path:
        """
        获取安装包复制后的路径
        
        Args:
            original_filename: 原始文件名
        
        Returns:
            复制目标路径
        """
        return self.packages_dir / original_filename
    
    def copy_package(self, source_path: str) -> str:
        """
        复制安装包到packages目录
        
        Args:
            source_path: 源文件路径
        
        Returns:
            复制后的相对路径（相对于程序根目录）
        """
        import shutil
        
        source = Path(source_path)
        target = self.get_package_copy_path(source.name)
        
        # 如果目标已存在且相同，不重复复制
        if target.exists() and target.stat().st_size == source.stat().st_size:
            return self.to_relative_path(target)
        
        shutil.copy2(source, target)
        return self.to_relative_path(target)
    
    def to_relative_path(self, abs_path: Path) -> str:
        """
        将绝对路径转换为相对于程序根目录的相对路径
        
        Args:
            abs_path: 绝对路径
        
        Returns:
            相对路径字符串
        """
        try:
            # 尝试计算相对路径
            rel_path = abs_path.relative_to(self.base_dir)
            return str(rel_path)
        except ValueError:
            # 如果不在程序目录下，返回绝对路径
            return str(abs_path)
    
    def to_absolute_path(self, rel_path: str) -> str:
        """
        将相对路径转换为绝对路径
        
        Args:
            rel_path: 相对路径（相对于程序根目录）
        
        Returns:
            绝对路径字符串
        """
        path = Path(rel_path)
        
        # 如果已经是绝对路径，直接返回
        if path.is_absolute():
            return str(path)
        
        # 否则，基于程序根目录计算绝对路径
        return str(self.base_dir / path)


if __name__ == '__main__':
    # 测试代码
    print('配置管理测试：')
    
    # 测试配置
    config = Config('./test_data/config.json')
    print(f'默认安装路径: {config.get_default_base_path()}')
    
    config.set_default_base_path('D:\\Program Files')
    print(f'新的默认路径: {config.get_default_base_path()}')
    
    # 测试权限
    print(f'是否管理员: {Config.is_admin()}')
    
    # 测试工作目录
    workspace = WorkspaceManager(Path('./test_workspace'))
    success = workspace.initialize()
    print(f'工作目录初始化: {"成功" if success else "失败"}')
    
    print('配置管理模块测试完成')

