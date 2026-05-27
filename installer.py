# -*- coding: utf-8 -*-
"""
安装器模块
执行静默安装操作
"""

import subprocess
import time
from pathlib import Path
from typing import Tuple


class Installer:
    """应用安装器"""
    
    def __init__(self, logger=None, database=None, workspace=None, startup_manager=None, param_detector=None):
        """
        初始化安装器
        
        Args:
            logger: 日志记录器实例
            database: 数据库实例
            workspace: WorkspaceManager实例（用于路径转换）
            startup_manager: StartupManager实例（用于检测开机自启）
            param_detector: ParamDetector实例（用于检测 Office 安装包）
        """
        self.logger = logger
        self.db = database
        self.workspace = workspace
        self.startup_manager = startup_manager
        self.param_detector = param_detector
    
    def install(self, app_id: int, package_path: str, install_args: str, 
                target_dir: str, timeout: int = 600, allow_fallback: bool = True) -> Tuple[bool, str]:
        """
        执行安装（智能回退：静默失败则自动尝试正常安装）
        
        Args:
            app_id: 应用ID（用于日志记录）
            package_path: 安装包路径（可能是相对路径）
            install_args: 静默参数
            target_dir: 目标安装目录
            timeout: 超时时间（秒），默认10分钟
            allow_fallback: 是否允许回退到正常安装（默认True）
        
        Returns:
            (success, message) 元组
        """
        # 如果有workspace，将相对路径转换为绝对路径
        if self.workspace:
            package_path = self.workspace.to_absolute_path(package_path)
        
        package_path = Path(package_path)
        
        # 验证安装包存在
        if not package_path.exists():
            msg = f'安装包不存在: {package_path}\n可能原因：原始文件已被移动或删除，请重新添加应用并选择正确的安装包路径'
            if self.logger:
                self.logger.error(msg)
            if self.db:
                self.db.add_log(app_id, 'install', 'failed', msg)
            return False, msg
        
        # 只在用户明确指定了自定义路径时才创建目标目录和检查空间
        if self._is_custom_target_dir(target_dir):
            # 磁盘空间预检（需要至少 500MB）
            try:
                import shutil as _shutil
                disk_usage = _shutil.disk_usage(Path(target_dir).anchor)
                free_mb = disk_usage.free / (1024 * 1024)
                if free_mb < 500:
                    msg = f'目标磁盘空间不足（剩余 {free_mb:.0f}MB，需要至少 500MB）'
                    if self.logger:
                        self.logger.error(msg)
                    if self.db:
                        self.db.add_log(app_id, 'install', 'failed', msg)
                    return False, msg
                if self.logger:
                    self.logger.info(f'磁盘空间检查通过：剩余 {free_mb:.0f}MB')
            except Exception as e:
                if self.logger:
                    self.logger.warning(f'无法检查磁盘空间，继续安装: {e}')
            
            # 创建目标目录
            try:
                Path(target_dir).mkdir(parents=True, exist_ok=True)
                if self.logger:
                    self.logger.info(f'创建安装目录: {target_dir}')
            except OSError as e:
                msg = f'无法创建安装目录: {e}'
                if self.logger:
                    self.logger.error(msg)
                if self.db:
                    self.db.add_log(app_id, 'install', 'failed', msg)
                return False, msg
        
        # 构建安装命令
        cmd = self._build_install_command(package_path, install_args, target_dir)
        
        # 确定工作目录（Office 和 .bat 需要在安装包目录下运行）
        work_dir = None
        suffix = package_path.suffix.lower()
        if self.param_detector and self.param_detector.is_office_install(str(package_path), package_path.stem):
            work_dir = str(package_path.resolve().parent)
        elif suffix == '.bat':
            work_dir = str(package_path.resolve().parent)
        
        if self.logger:
            self.logger.info(f'执行安装命令: {cmd}')
            if work_dir:
                self.logger.info(f'工作目录: {work_dir}')
        
        # 安装前记录开机自启项
        before_startup = []
        if self.startup_manager:
            before_startup = self.startup_manager.get_all_startup_items()
        
        # 第一次尝试：静默安装
        success, message, return_code = self._execute_install(cmd, timeout, is_silent=True, cwd=work_dir)
        
        # 如果静默安装失败且允许回退，尝试正常安装
        if not success and allow_fallback and return_code not in [0, 3010]:
            if self.logger:
                self.logger.info('静默安装失败，尝试正常安装模式...')
            
            # 构建正常安装命令（移除静默参数）
            fallback_cmd = self._build_normal_install_command(package_path, target_dir)
            
            if self.logger:
                self.logger.info(f'执行正常安装: {fallback_cmd}')
            
            # 第二次尝试：正常安装（带界面）
            success, message, return_code = self._execute_install(fallback_cmd, timeout, is_silent=False, cwd=work_dir)
            
            if success:
                message = '安装成功（使用正常安装模式）'
                if self.logger:
                    self.logger.info('正常安装模式成功')
        
        # 安装成功后检测新增的开机自启项
        if success and self.startup_manager and self.db:
            # 获取应用名称
            app = self.db.get_application(app_id)
            if app:
                new_startup_items = self.startup_manager.track_installation_startup(
                    app_id, app['name'], before_startup
                )
                
                # 记录到数据库
                if new_startup_items:
                    self.db.record_startup_items(app_id, new_startup_items)
        
        # 记录最终结果
        if success:
            if self.db:
                self.db.add_log(app_id, 'install', 'success', message)
                self.db.update_install_status(app_id, '已安装')
        else:
            if self.db:
                self.db.add_log(app_id, 'install', 'failed', message)
                self.db.update_install_status(app_id, '失败')
        
        return success, message
    
    def _execute_install(self, cmd: str, timeout: int, is_silent: bool, cwd: str = None) -> Tuple[bool, str, int]:
        """
        执行安装命令（细化异常处理）
        
        Args:
            cmd: 安装命令
            timeout: 超时时间
            is_silent: 是否静默安装
            cwd: 工作目录（可选）
        
        Returns:
            (success, message, return_code) 元组
        """
        try:
            # 使用subprocess执行安装命令
            creation_flags = 0
            if is_silent and hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
                cwd=cwd
            )
            
            # 等待安装完成
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                # 超时后强制终止进程
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    pass  # 进程可能已结束
                msg = f'安装超时（超过{timeout}秒）'
                if self.logger:
                    self.logger.error(msg)
                return False, msg, -1
            
            # 检查返回码
            if return_code == 0:
                msg = '安装成功'
                if self.logger:
                    self.logger.info(msg)
                return True, msg, return_code
            elif return_code == 3010:
                msg = '安装成功（需要重启）'
                if self.logger:
                    self.logger.warning(msg)
                return True, msg, return_code
            elif return_code == 1603 or return_code == 5:
                msg = f'安装失败（权限不足，请以管理员身份运行，返回码: {return_code}）'
                stderr_msg = stderr.decode('gbk', errors='ignore').strip() if stderr else ''
                if stderr_msg:
                    msg += f' - {stderr_msg}'
                if self.logger:
                    self.logger.error(msg)
                return False, msg, return_code
            elif return_code == 1618 or return_code == 1638:
                msg = f'安装失败（软件已安装或正在运行，返回码: {return_code}）'
                if self.logger:
                    self.logger.warning(msg)
                return False, msg, return_code
            else:
                stderr_msg = stderr.decode('gbk', errors='ignore').strip() if stderr else ''
                msg = f'安装失败（返回码: {return_code}）'
                if stderr_msg:
                    msg += f' - {stderr_msg}'
                if self.logger:
                    self.logger.error(msg)
                return False, msg, return_code
        
        except FileNotFoundError as e:
            msg = f'找不到命令或程序: {str(e)}'
            if self.logger:
                self.logger.error(msg)
            return False, msg, -2
        except PermissionError as e:
            msg = f'权限不足: {str(e)}'
            if self.logger:
                self.logger.error(msg)
            return False, msg, -3
        except OSError as e:
            msg = f'系统错误: {str(e)}'
            if self.logger:
                self.logger.error(msg)
            return False, msg, -4
        except Exception as e:
            error_type = type(e).__name__
            msg = f'安装过程出错 ({error_type}): {str(e)}'
            if self.logger:
                self.logger.exception(msg)  # 记录完整堆栈
            return False, msg, -99
    
    def _is_custom_target_dir(self, target_dir: str) -> bool:
        """
        判断是否明确指定了自定义安装路径

        Args:
            target_dir: 目标目录

        Returns:
            True 表示用户明确指定了自定义路径，False 表示使用默认路径
        """
        return bool(target_dir and target_dir.strip())
    
    def _build_cmd(self, package_path: Path, install_args: str = '', 
                    target_dir: str = '', is_silent: bool = True) -> str:
        """
        统一的安装命令构建入口（消除 _build_install_command 和 _build_normal_install_command 的重复）

        Args:
            package_path: 安装包路径
            install_args: 静默参数（空字符串表示正常模式）
            target_dir: 目标目录（空表示使用默认路径）
            is_silent: True=静默安装（带install_args）, False=正常安装（不带静默参数）

        Returns:
            安装命令字符串
        """
        suffix = package_path.suffix.lower()
        app_name = package_path.stem

        # Office 特殊处理（根据 is_silent 区分静默/正常模式）
        if self.param_detector and self.param_detector.is_office_install(str(package_path), app_name):
            return self.param_detector.build_office_install_command(str(package_path), target_dir, is_silent)

        if suffix == '.msi':
            cmd = self._build_msi_cmd(package_path, install_args, target_dir, is_silent)
        elif suffix == '.bat':
            cmd = self._build_bat_cmd(package_path, install_args)
        else:
            cmd = self._build_exe_cmd(package_path, install_args, target_dir, is_silent)
        
        return cmd
    
    def _build_msi_cmd(self, package_path: Path, install_args: str, 
                        target_dir: str, is_silent: bool) -> str:
        """构建 MSI 安装命令"""
        if is_silent and install_args:
            cmd = f'msiexec /i "{package_path}" {install_args}'
        else:
            cmd = f'msiexec /i "{package_path}" /qn'
        
        if '/norestart' not in (install_args if is_silent else '').lower():
            cmd += ' /norestart'
        
        if self._is_custom_target_dir(target_dir):
            cmd += f' INSTALLDIR="{target_dir}"'
        
        return cmd
    
    def _build_bat_cmd(self, package_path: Path, install_args: str) -> str:
        """构建 BAT 安装命令"""
        cmd = f'"{package_path}"'
        if install_args:
            cmd += f' {install_args}'
        return cmd
    
    def _build_exe_cmd(self, package_path: Path, install_args: str, 
                        target_dir: str, is_silent: bool) -> str:
        """构建 EXE 安装命令"""
        if is_silent and install_args:
            cmd = f'"{package_path}" {install_args}'
        else:
            cmd = f'"{package_path}" /norestart'
        
        if self._is_custom_target_dir(target_dir):
            dir_param = self._detect_dir_param_format(install_args if is_silent else '')
            
            if dir_param == 'WINRAR':
                cmd += f' /d"{target_dir}"'
            elif dir_param == '/D=':
                cmd += f' /D="{target_dir}"'
            elif dir_param == '/DIR=':
                cmd += f' /DIR="{target_dir}"'
            elif 'INSTALLDIR=' in (install_args if is_silent else '').upper():
                cmd += f' INSTALLDIR="{target_dir}"'
            else:
                cmd += f' /D="{target_dir}"'
        
        return cmd
    
    # 兼容性接口（保持向后兼容，内部统一调用 _build_cmd）
    def _build_normal_install_command(self, package_path: Path, target_dir: str = '') -> str:
        """构建正常安装命令（不带静默参数）"""
        return self._build_cmd(package_path, '', target_dir, is_silent=False)
    
    def _build_install_command(self, package_path: Path, install_args: str, 
                            target_dir: str) -> str:
        """构建安装命令（智能自动模式，带静默参数）"""
        return self._build_cmd(package_path, install_args, target_dir, is_silent=True)
    
    def _detect_dir_param_format(self, install_args: str) -> str:
        """
        检测目录参数格式
        
        Args:
            install_args: 安装参数
        
        Returns:
            目录参数格式
        """
        install_args_upper = install_args.upper()
        install_args_lower = install_args.lower()
        
        if install_args_lower == '/s' or install_args_lower.strip() == '/s':
            # WinRAR 格式：/s /d<path>（无空格无等号）
            return 'WINRAR'
        elif '/VERYSILENT' in install_args_upper:
            # Inno Setup
            return '/DIR='
        elif '/S' in install_args and '/V' in install_args:
            # InstallShield
            return 'INSTALLDIR='
        else:
            # NSIS或默认
            return '/D='
    
    def batch_install(self, app_ids: list, progress_callback=None, cancel_event=None) -> dict:
        """
        批量安装应用（支持取消和错误跳过）
        
        Args:
            app_ids: 应用ID列表
            progress_callback: 进度回调函数 callback(current, total, app_name, success)
            cancel_event: threading.Event 对象，用于取消批量安装
        
        Returns:
            统计字典 {
                'success': 3, 
                'failed': 1, 
                'total': 4,
                'cancelled': False/True,
                'reboot_required': [{'id': 1, 'name': 'App1'}, ...]
            }
        """
        import threading as _threading
        
        total = len(app_ids)
        success_count = 0
        failed_count = 0
        cancelled = False
        reboot_required_apps = []  # 需要重启的应用列表
        
        for i, app_id in enumerate(app_ids, 1):
            # 检查是否被用户取消
            if cancel_event and (isinstance(cancel_event, _threading.Event) and cancel_event.is_set()):
                if self.logger:
                    self.logger.info('用户取消了批量安装')
                cancelled = True
                break
            
            # 获取应用信息
            if not self.db:
                continue
            
            app = self.db.get_application(app_id)
            if not app:
                continue
            
            app_name = app['name']
            
            if self.logger:
                self.logger.info(f'[{i}/{total}] 正在安装 {app_name}...')
            
            # 执行安装（单个失败不阻塞后续安装）
            try:
                success, message = self.install(
                    app_id,
                    app['package_path'],
                    app['install_args'],
                    app['final_install_path']
                )
                
                if success:
                    success_count += 1
                    if self.logger:
                        self.logger.info(f'✓ {app_name} 安装成功')
                    
                    # 检查是否需要重启
                    if '需要重启' in message or 'reboot' in message.lower():
                        reboot_required_apps.append({
                            'id': app_id,
                            'name': app_name
                        })
                        if self.logger:
                            self.logger.info(f'  → {app_name} 需要重启才能完成安装')
                else:
                    failed_count += 1
                    if self.logger:
                        self.logger.warning(f'✗ {app_name} 安装失败（已跳过，继续下一个）: {message}')
                    
                    # 失败后记录日志并继续下一个
                    if self.db:
                        self.db.add_log(app_id, 'install', 'skipped', f'安装失败已跳过: {message}')
                        
            except Exception as e:
                failed_count += 1
                if self.logger:
                    self.logger.error(f'✗ {app_name} 安装异常（已跳过）: {type(e).__name__}: {e}')
                if self.db:
                    self.db.add_log(app_id, 'install', 'error', f'安装异常: {type(e).__name__}: {e}')
            
            # 调用进度回调
            if progress_callback:
                try:
                    progress_callback(i, total, app_name, success)
                except Exception:
                    pass  # 回调异常不影响主流程
            
            # 智能延迟：成功后短延迟，失败后长延迟
            if i < total:
                delay = 0.5 if success else 2.0
                time.sleep(delay)
        
        return {
            'success': success_count,
            'failed': failed_count,
            'total': total,
            'cancelled': cancelled,
            'reboot_required': reboot_required_apps
        }


def reboot_system(delay_seconds: int = 10):
    """
    重启系统
    
    Args:
        delay_seconds: 延迟秒数
    """
    import os
    # Windows重启命令
    os.system(f'shutdown /r /t {delay_seconds}')

