# -*- coding: utf-8 -*-
"""
卸载器模块
通过读取注册表获取卸载命令并执行
"""

import winreg
import subprocess
from typing import Optional, Tuple, List, Dict


class Uninstaller:
    """应用卸载器"""
    
    # 注册表卸载信息位置
    UNINSTALL_PATHS = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    ]
    
    def __init__(self, logger=None, database=None):
        """
        初始化卸载器
        
        Args:
            logger: 日志记录器实例
            database: 数据库实例
        """
        self.logger = logger
        self.db = database
    
    def find_uninstall_info(self, software_name: str) -> Optional[Dict]:
        """
        从注册表查找软件的卸载信息
        
        Args:
            software_name: 软件名称
        
        Returns:
            卸载信息字典，包含：
            {
                'display_name': '显示名称',
                'uninstall_string': '标准卸载命令',
                'quiet_uninstall_string': '静默卸载命令',
                'publisher': '发布者',
                'version': '版本'
            }
            未找到返回None
        """
        software_name_lower = software_name.lower()
        
        for hkey, path in self.UNINSTALL_PATHS:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    # 遍历所有子键
                    index = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, index)
                            index += 1
                            
                            # 打开子键
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                # 获取显示名称
                                try:
                                    display_name = winreg.QueryValueEx(subkey, 'DisplayName')[0]
                                except FileNotFoundError:
                                    continue
                                
                                # 模糊匹配软件名
                                if software_name_lower in display_name.lower():
                                    # 找到匹配的软件，提取卸载信息
                                    uninstall_info = {'display_name': display_name}
                                    
                                    # 获取卸载命令
                                    try:
                                        uninstall_info['uninstall_string'] = winreg.QueryValueEx(subkey, 'UninstallString')[0]
                                    except FileNotFoundError:
                                        uninstall_info['uninstall_string'] = ''
                                    
                                    # 获取静默卸载命令（部分软件有）
                                    try:
                                        uninstall_info['quiet_uninstall_string'] = winreg.QueryValueEx(subkey, 'QuietUninstallString')[0]
                                    except FileNotFoundError:
                                        uninstall_info['quiet_uninstall_string'] = ''
                                    
                                    # 获取发布者
                                    try:
                                        uninstall_info['publisher'] = winreg.QueryValueEx(subkey, 'Publisher')[0]
                                    except FileNotFoundError:
                                        uninstall_info['publisher'] = ''
                                    
                                    # 获取版本
                                    try:
                                        uninstall_info['version'] = winreg.QueryValueEx(subkey, 'DisplayVersion')[0]
                                    except FileNotFoundError:
                                        uninstall_info['version'] = ''
                                    
                                    # 如果有卸载命令，返回信息
                                    if uninstall_info['uninstall_string'] or uninstall_info['quiet_uninstall_string']:
                                        return uninstall_info
                        
                        except OSError:
                            # 遍历完成
                            break
            
            except FileNotFoundError:
                # 注册表路径不存在，继续下一个
                continue
            except Exception as e:
                if self.logger:
                    self.logger.warning(f'读取注册表出错: {e}')
                continue
        
        return None
    
    def check_uninstall_available(self, app_id: int, software_name: str) -> bool:
        """
        检查软件是否可以通过工具卸载
        
        Args:
            app_id: 应用ID
            software_name: 软件名称
        
        Returns:
            是否可卸载
        """
        uninstall_info = self.find_uninstall_info(software_name)
        available = uninstall_info is not None
        
        # 更新数据库
        if self.db:
            self.db.update_application(app_id, uninstall_available=1 if available else 0)
        
        return available
    
    def uninstall(self, app_id: int, software_name: str, timeout: int = 600) -> Tuple[bool, str]:
        """
        卸载软件
        
        Args:
            app_id: 应用ID
            software_name: 软件名称
            timeout: 超时时间（秒）
        
        Returns:
            (success, message) 元组
        """
        # 查找卸载信息
        uninstall_info = self.find_uninstall_info(software_name)
        
        if not uninstall_info:
            msg = f'未找到 {software_name} 的卸载信息'
            if self.logger:
                self.logger.error(msg)
            if self.db:
                self.db.add_log(app_id, 'uninstall', 'failed', msg)
            return False, msg
        
        # 优先使用静默卸载命令
        uninstall_cmd = uninstall_info.get('quiet_uninstall_string') or uninstall_info.get('uninstall_string')
        
        if not uninstall_cmd:
            msg = f'{software_name} 没有可用的卸载命令'
            if self.logger:
                self.logger.error(msg)
            if self.db:
                self.db.add_log(app_id, 'uninstall', 'failed', msg)
            return False, msg
        
        if self.logger:
            self.logger.info(f'执行卸载命令: {uninstall_cmd}')
        
        # 执行卸载
        try:
            # 对于MSI卸载，添加静默参数
            if 'msiexec' in uninstall_cmd.lower():
                # 如果是MSI卸载但没有静默参数，添加/qn
                if '/qn' not in uninstall_cmd and '/quiet' not in uninstall_cmd:
                    uninstall_cmd += ' /qn /norestart'
            
            process = subprocess.Popen(
                uninstall_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                msg = f'卸载超时（超过{timeout}秒）'
                if self.logger:
                    self.logger.error(msg)
                if self.db:
                    self.db.add_log(app_id, 'uninstall', 'failed', msg)
                return False, msg
            
            # 检查返回码
            if return_code == 0 or return_code == 3010:
                msg = '卸载成功' if return_code == 0 else '卸载成功（需要重启）'
                if self.logger:
                    self.logger.info(msg)
                if self.db:
                    self.db.add_log(app_id, 'uninstall', 'success', msg)
                    self.db.update_install_status(app_id, '待安装')
                    self.db.update_application(app_id, uninstall_available=0)
                return True, msg
            else:
                stderr_msg = stderr.decode('gbk', errors='ignore').strip() if stderr else ''
                msg = f'卸载失败（返回码: {return_code}）{stderr_msg}'
                if self.logger:
                    self.logger.error(msg)
                if self.db:
                    self.db.add_log(app_id, 'uninstall', 'failed', msg)
                return False, msg
        
        except Exception as e:
            msg = f'卸载过程出错: {str(e)}'
            if self.logger:
                self.logger.error(msg)
            if self.db:
                self.db.add_log(app_id, 'uninstall', 'failed', msg)
            return False, msg
    
    def refresh_all_uninstall_status(self) -> int:
        """
        刷新所有已安装应用的卸载状态
        
        Returns:
            更新的应用数量
        """
        if not self.db:
            return 0
        
        # 获取所有已安装的应用
        installed_apps = self.db.get_all_applications(status='已安装')
        
        updated_count = 0
        for app in installed_apps:
            available = self.check_uninstall_available(app['id'], app['name'])
            if available:
                updated_count += 1
        
        if self.logger:
            self.logger.info(f'已刷新 {updated_count}/{len(installed_apps)} 个应用的卸载状态')
        
        return updated_count
    
    def get_uninstallable_apps(self) -> List[Dict]:
        """
        获取所有可卸载的应用列表
        
        Returns:
            可卸载应用列表
        """
        if not self.db:
            return []
        
        installed_apps = self.db.get_all_applications(status='已安装')
        uninstallable = []
        
        for app in installed_apps:
            if app['uninstall_available']:
                uninstallable.append(app)
        
        return uninstallable

