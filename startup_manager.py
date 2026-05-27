# -*- coding: utf-8 -*-
"""
开机自启管理模块
检测、记录和管理应用的开机自启项
"""

import winreg
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import os


class StartupManager:
    """开机自启管理器"""
    
    # 注册表启动项位置
    REGISTRY_PATHS = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', '系统启动项'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run', '系统启动项(32位)'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', '用户启动项'),
    ]
    
    # 启动文件夹位置
    STARTUP_FOLDERS = [
        (Path(os.environ.get('APPDATA', '')) / r'Microsoft\Windows\Start Menu\Programs\Startup', '用户启动文件夹'),
        (Path(os.environ.get('PROGRAMDATA', '')) / r'Microsoft\Windows\Start Menu\Programs\Startup', '公共启动文件夹'),
    ]
    
    def __init__(self, logger=None, database=None):
        """
        初始化启动管理器
        
        Args:
            logger: 日志记录器
            database: 数据库实例
        """
        self.logger = logger
        self.db = database
    
    def get_all_startup_items(self) -> List[Dict]:
        """
        获取所有开机自启项
        
        Returns:
            启动项列表，每项包含：
            {
                'name': '启动项名称',
                'path': '程序路径',
                'location': '位置（注册表或启动文件夹）',
                'type': 'registry' 或 'folder'
            }
        """
        startup_items = []
        
        # 1. 从注册表读取
        for hkey, subkey_path, location_name in self.REGISTRY_PATHS:
            items = self._read_registry_startup(hkey, subkey_path, location_name)
            startup_items.extend(items)
        
        # 2. 从启动文件夹读取
        for folder_path, location_name in self.STARTUP_FOLDERS:
            items = self._read_folder_startup(folder_path, location_name)
            startup_items.extend(items)
        
        return startup_items
    
    def _read_registry_startup(self, hkey, subkey_path: str, location_name: str) -> List[Dict]:
        """
        从注册表读取启动项
        
        Args:
            hkey: 注册表根键
            subkey_path: 子键路径
            location_name: 位置名称
        
        Returns:
            启动项列表
        """
        items = []
        
        try:
            with winreg.OpenKey(hkey, subkey_path) as key:
                index = 0
                while True:
                    try:
                        # 枚举所有值
                        name, data, data_type = winreg.EnumValue(key, index)
                        index += 1
                        
                        items.append({
                            'name': name,
                            'path': data,
                            'location': location_name,
                            'type': 'registry',
                            'reg_path': f'{self._hkey_to_string(hkey)}\\{subkey_path}'
                        })
                    
                    except OSError:
                        # 枚举完成
                        break
        
        except FileNotFoundError:
            # 注册表路径不存在
            pass
        except Exception as e:
            if self.logger:
                self.logger.warning(f'读取注册表启动项失败 {subkey_path}: {e}')
        
        return items
    
    def _read_folder_startup(self, folder_path: Path, location_name: str) -> List[Dict]:
        """
        从启动文件夹读取启动项
        
        Args:
            folder_path: 启动文件夹路径
            location_name: 位置名称
        
        Returns:
            启动项列表
        """
        items = []
        
        try:
            if folder_path.exists() and folder_path.is_dir():
                for file in folder_path.iterdir():
                    if file.is_file():
                        # 读取快捷方式目标（如果是.lnk文件）
                        if file.suffix.lower() == '.lnk':
                            target = self._resolve_shortcut(file)
                        else:
                            target = str(file)
                        
                        items.append({
                            'name': file.stem,
                            'path': target or str(file),
                            'location': location_name,
                            'type': 'folder',
                            'shortcut_path': str(file)
                        })
        
        except Exception as e:
            if self.logger:
                self.logger.warning(f'读取启动文件夹失败 {folder_path}: {e}')
        
        return items
    
    def _resolve_shortcut(self, lnk_path: Path) -> Optional[str]:
        """
        解析快捷方式的目标路径
        
        Args:
            lnk_path: .lnk文件路径
        
        Returns:
            目标路径，失败返回None
        """
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(lnk_path))
            return shortcut.Targetpath
        except Exception:
            # 如果没有 win32com，返回None
            return None
    
    def _hkey_to_string(self, hkey) -> str:
        """将注册表根键转换为字符串"""
        if hkey == winreg.HKEY_LOCAL_MACHINE:
            return 'HKLM'
        elif hkey == winreg.HKEY_CURRENT_USER:
            return 'HKCU'
        else:
            return 'HKEY'
    
    def find_startup_by_software(self, software_name: str) -> List[Dict]:
        """
        查找特定软件的开机自启项
        
        Args:
            software_name: 软件名称
        
        Returns:
            匹配的启动项列表
        """
        all_items = self.get_all_startup_items()
        software_name_lower = software_name.lower()
        
        matched = []
        for item in all_items:
            # 模糊匹配名称或路径
            if (software_name_lower in item['name'].lower() or 
                software_name_lower in item['path'].lower()):
                matched.append(item)
        
        return matched
    
    def remove_startup_item(self, item: Dict) -> Tuple[bool, str]:
        """
        删除开机自启项
        
        Args:
            item: 启动项信息字典
        
        Returns:
            (success, message) 元组
        """
        try:
            if item['type'] == 'registry':
                # 从注册表删除
                return self._remove_registry_startup(item)
            elif item['type'] == 'folder':
                # 从启动文件夹删除
                return self._remove_folder_startup(item)
            else:
                return False, '未知的启动项类型'
        
        except Exception as e:
            msg = f'删除失败: {e}'
            if self.logger:
                self.logger.error(msg)
            return False, msg
    
    def _remove_registry_startup(self, item: Dict) -> Tuple[bool, str]:
        """从注册表删除启动项"""
        try:
            # 解析注册表路径
            reg_path = item.get('reg_path', '')
            if 'HKLM' in reg_path:
                hkey = winreg.HKEY_LOCAL_MACHINE
            elif 'HKCU' in reg_path:
                hkey = winreg.HKEY_CURRENT_USER
            else:
                return False, '无法解析注册表路径'
            
            # 提取子键路径
            if '\\' in reg_path:
                subkey = reg_path.split('\\', 1)[1]
            else:
                return False, '无效的注册表路径'
            
            # 删除值
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, item['name'])
            
            msg = f'已从注册表删除: {item["name"]}'
            if self.logger:
                self.logger.info(msg)
            return True, msg
        
        except Exception as e:
            msg = f'删除注册表项失败: {e}'
            if self.logger:
                self.logger.error(msg)
            return False, msg
    
    def _remove_folder_startup(self, item: Dict) -> Tuple[bool, str]:
        """从启动文件夹删除启动项"""
        try:
            shortcut_path = Path(item.get('shortcut_path', ''))
            if shortcut_path.exists():
                shortcut_path.unlink()
                msg = f'已从启动文件夹删除: {item["name"]}'
                if self.logger:
                    self.logger.info(msg)
                return True, msg
            else:
                return False, '文件不存在'
        
        except Exception as e:
            msg = f'删除启动文件失败: {e}'
            if self.logger:
                self.logger.error(msg)
            return False, msg
    
    def detect_new_startup_items(self, before_items: List[Dict], after_items: List[Dict]) -> List[Dict]:
        """
        检测新增的启动项（用于安装前后对比）
        
        Args:
            before_items: 安装前的启动项列表
            after_items: 安装后的启动项列表
        
        Returns:
            新增的启动项列表
        """
        # 创建before的唯一标识集合
        before_ids = set()
        for item in before_items:
            item_id = f"{item['name']}|{item['path']}|{item['location']}"
            before_ids.add(item_id)
        
        # 找出新增项
        new_items = []
        for item in after_items:
            item_id = f"{item['name']}|{item['path']}|{item['location']}"
            if item_id not in before_ids:
                new_items.append(item)
        
        return new_items
    
    def track_installation_startup(self, app_id: int, app_name: str, 
                                   before_items: List[Dict]) -> List[Dict]:
        """
        跟踪安装过程中添加的开机自启项
        
        Args:
            app_id: 应用ID
            app_name: 应用名称
            before_items: 安装前的启动项列表
        
        Returns:
            该应用添加的启动项列表
        """
        # 获取当前启动项
        after_items = self.get_all_startup_items()
        
        # 检测新增项
        new_items = self.detect_new_startup_items(before_items, after_items)
        
        # 过滤出与该软件相关的启动项
        related_items = []
        app_name_lower = app_name.lower()
        
        for item in new_items:
            # 通过名称或路径匹配
            if (app_name_lower in item['name'].lower() or 
                app_name_lower in item['path'].lower()):
                related_items.append(item)
        
        # 记录到数据库（扩展功能，需要新表）
        if self.logger and related_items:
            self.logger.info(f'{app_name} 添加了 {len(related_items)} 个开机自启项')
            for item in related_items:
                self.logger.info(f"  → {item['name']}: {item['location']}")
        
        return related_items


