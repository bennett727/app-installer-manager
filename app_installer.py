# -*- coding: utf-8 -*-
"""
批量应用安装管理器 - 主程序
支持批量安装、应用管理、智能参数检测、智能卸载
"""

import sys
import argparse
from pathlib import Path

from database import Database
from logger import get_logger
from installer import Installer
from uninstaller import Uninstaller
from param_detector import ParamDetector
from config import Config, WorkspaceManager, check_expiration, get_expiration_info
from startup_manager import StartupManager


class AppInstallerCLI:
    """主程序CLI类"""
    
    def __init__(self):
        """初始化主程序"""
        # 获取程序根目录
        if getattr(sys, 'frozen', False):
            # 打包后的exe
            self.base_dir = Path(sys.executable).parent
        else:
            # 开发环境
            self.base_dir = Path(__file__).parent.absolute()
        
        # 初始化工作目录
        self.workspace = WorkspaceManager(self.base_dir)
        if not self.workspace.initialize():
            print('错误：无法初始化工作目录')
            print(f'请确保程序有权限在以下位置创建文件：{self.workspace.data_dir}')
            print('建议：')
            print('1. 将程序移动到非系统保护目录（如 D:\\AppInstaller\\）')
            print('2. 或以管理员身份运行')
            sys.exit(1)
        
        # 检查有效期
        config_path = self.workspace.data_dir / 'config.json'
        status, expire_msg, days_left = check_expiration(config_path)
        if status == 'expired':
            print(f'\n错误：{expire_msg}\n')
            input('\n按回车键退出...')
            sys.exit(1)
        elif status == 'warning':
            print(f'\n提示：{expire_msg}\n')
        
        # 初始化组件
        self.logger = get_logger(log_dir=self.workspace.logs_dir)
        self.config = Config(self.workspace.data_dir / 'config.json')
        self.db = Database(self.workspace.db_path)
        self.param_detector = ParamDetector(database=self.db)
        self.startup_manager = StartupManager(logger=self.logger, database=self.db)
        self.installer = Installer(logger=self.logger, database=self.db, workspace=self.workspace, startup_manager=self.startup_manager, param_detector=self.param_detector)
        self.uninstaller = Uninstaller(logger=self.logger, database=self.db)
        
        self.logger.info('=' * 60)
        self.logger.info('批量应用安装管理器已启动')
        self.logger.info(f'工作目录: {self.workspace.data_dir}')
        self.logger.info('=' * 60)
    
    # ==================== 应用管理 ====================
    
    def cmd_add(self, args):
        """添加应用"""
        package_path = Path(args.package_path)
        
        # 验证文件存在
        if not package_path.exists():
            print(f'错误：文件不存在 {package_path}')
            return
        
        # 验证文件类型
        if package_path.suffix.lower() not in ['.exe', '.msi']:
            print(f'错误：不支持的文件类型 {package_path.suffix}')
            print('仅支持 .exe 和 .msi 文件')
            return
        
        # 交互式输入
        print(f'\n添加应用: {package_path.name}')
        print('-' * 60)
        
        name = input('请输入软件名称: ').strip()
        if not name:
            print('错误：软件名称不能为空')
            return
        
        folder_name = input('请输入安装文件夹名: ').strip()
        if not folder_name:
            print('错误：文件夹名不能为空')
            return
        
        version = input('请输入版本号（可选，回车跳过）: ').strip()
        
        # 显示正在分析软件信息
        print('\n正在分析软件信息...')
        
        # 自动检测参数
        install_args, source = self.param_detector.detect_params(str(package_path), name)
        
        print(f'✓ 检测到静默参数: {install_args}')
        print(f'  来源: {source}')
        
        # 允许用户修改参数
        custom_args = input(f'是否修改参数？(直接回车使用检测到的参数，或输入新参数): ').strip()
        if custom_args:
            install_args = custom_args
            # 缓存用户自定义的参数
            self.db.cache_params(name, install_args, '用户输入')
        
        # 获取基础安装路径
        default_base_path = self.config.get_default_base_path()
        final_path = str(Path(default_base_path) / folder_name)
        
        print(f'✓ 最终安装路径: {final_path}')
        
        # 确认
        confirm = input('\n是否确认添加？(Y/n): ').strip().lower()
        if confirm and confirm != 'y':
            print('已取消')
            return
        
        # 是否复制安装包
        copy_package = input('是否复制安装包到本地？(y/N): ').strip().lower()
        if copy_package == 'y':
            try:
                print('正在复制安装包...')
                package_path_str = self.workspace.copy_package(str(package_path))
                print(f'✓ 已复制到: {package_path_str}')
            except Exception as e:
                print(f'警告：复制失败，将使用原始路径: {e}')
                package_path_str = str(package_path)
        else:
            package_path_str = str(package_path)
        
        # 添加到数据库
        app_id = self.db.add_application(
            name=name,
            package_path=package_path_str,
            folder_name=folder_name,
            base_install_path=default_base_path,
            version=version,
            install_args=install_args
        )
        
        print(f'\n✓ 应用已添加，ID: {app_id}')
        self.logger.info(f'添加应用: {name} (ID: {app_id})')
    
    def cmd_list(self, args):
        """列出所有应用"""
        apps = self.db.get_all_applications()
        
        if not apps:
            print('暂无应用')
            return
        
        print(f'\n应用列表 (共 {len(apps)} 个):')
        print('=' * 100)
        print(f'{"ID":<5} {"名称":<20} {"状态":<10} {"版本":<10} {"安装路径":<40}')
        print('-' * 100)
        
        for app in apps:
            status_icon = '✓' if app['status'] == '已安装' else '○' if app['status'] == '待安装' else '✗'
            print(f'{app["id"]:<5} {app["name"]:<20} {status_icon} {app["status"]:<8} {app["version"]:<10} {app["final_install_path"]:<40}')
        
        print('=' * 100)
    
    def cmd_remove(self, args):
        """删除应用记录"""
        app_id = args.id
        app = self.db.get_application(app_id)
        
        if not app:
            print(f'错误：未找到ID为 {app_id} 的应用')
            return
        
        print(f'确认删除应用: {app["name"]} (ID: {app_id})?')
        confirm = input('输入 yes 确认: ').strip().lower()
        
        if confirm == 'yes':
            self.db.delete_application(app_id)
            print(f'✓ 已删除应用: {app["name"]}')
            self.logger.info(f'删除应用: {app["name"]} (ID: {app_id})')
        else:
            print('已取消')
    
    def cmd_edit(self, args):
        """编辑应用信息"""
        app_id = args.id
        app = self.db.get_application(app_id)
        
        if not app:
            print(f'错误：未找到ID为 {app_id} 的应用')
            return
        
        print(f'\n编辑应用: {app["name"]} (ID: {app_id})')
        print('-' * 60)
        print(f'当前安装参数: {app["install_args"]}')
        
        new_args = input('输入新参数（回车保持不变）: ').strip()
        if new_args:
            self.db.update_application(app_id, install_args=new_args)
            print('✓ 参数已更新')
            self.logger.info(f'更新应用参数: {app["name"]} -> {new_args}')
    
    # ==================== 安装操作 ====================
    
    def cmd_install(self, args):
        """安装单个应用"""
        app_id = args.id
        app = self.db.get_application(app_id)
        
        if not app:
            print(f'错误：未找到ID为 {app_id} 的应用')
            return
        
        print(f'\n开始安装: {app["name"]}')
        print(f'安装路径: {app["final_install_path"]}')
        print(f'安装参数: {app["install_args"]}')
        print('-' * 60)
        
        success, message = self.installer.install(
            app_id,
            app['package_path'],
            app['install_args'],
            app['final_install_path']
        )
        
        if success:
            print(f'✓ {message}')
        else:
            print(f'✗ {message}')
    
    def cmd_install_all(self, args):
        """批量安装所有待安装应用"""
        apps = self.db.get_all_applications(status='待安装')
        
        if not apps:
            print('没有待安装的应用')
            return
        
        print(f'\n开始批量安装，共 {len(apps)} 个应用')
        print('=' * 60)
        
        app_ids = [app['id'] for app in apps]
        
        def progress_callback(current, total, app_name, success):
            status = '✓' if success else '✗'
            print(f'[{current}/{total}] {status} {app_name}')
        
        stats = self.installer.batch_install(app_ids, progress_callback)
        
        print('=' * 60)
        print(f'完成：{stats["success"]} 成功，{stats["failed"]} 失败')
        
        # 处理需要重启的应用
        reboot_required = stats.get('reboot_required', [])
        if reboot_required:
            print()
            print('⚠️  以下应用需要重启电脑才能完成安装：')
            print('-' * 60)
            for app in reboot_required:
                print(f'  • {app["name"]}')
            print('-' * 60)
            print()
            
            choice = input('是否现在重启电脑？(y/N): ').strip().lower()
            if choice == 'y':
                print('系统将在 10 秒后重启...')
                print('（可以按 Ctrl+C 取消）')
                import time
                try:
                    time.sleep(2)
                    from installer import reboot_system
                    reboot_system(10)
                    print('重启命令已发送')
                except KeyboardInterrupt:
                    print('\n已取消重启')
            else:
                print('请稍后手动重启电脑以完成安装')
        
        self.logger.info(f'批量安装完成：{stats["success"]} 成功，{stats["failed"]} 失败')
    
    # ==================== 卸载操作 ====================
    
    def cmd_uninstall_list(self, args):
        """显示已安装应用及卸载状态"""
        apps = self.db.get_all_applications(status='已安装')
        
        if not apps:
            print('没有已安装的应用')
            return
        
        print(f'\n已安装应用列表 (共 {len(apps)} 个):')
        print('=' * 90)
        print(f'{"ID":<5} {"名称":<30} {"版本":<15} {"卸载状态":<20}')
        print('-' * 90)
        
        for app in apps:
            if app['uninstall_available']:
                status = '✓ 可卸载'
            else:
                status = '✗ 需手动卸载'
            
            print(f'{app["id"]:<5} {app["name"]:<30} {app["version"]:<15} {status:<20}')
        
        print('=' * 90)
    
    def cmd_uninstall(self, args):
        """卸载应用"""
        app_id = args.id
        app = self.db.get_application(app_id)
        
        if not app:
            print(f'错误：未找到ID为 {app_id} 的应用')
            return
        
        if app['status'] != '已安装':
            print(f'错误：应用未安装，无法卸载')
            return
        
        # 检查是否可卸载
        if not app['uninstall_available']:
            print(f'警告：未找到 {app["name"]} 的卸载信息')
            print('正在尝试重新检测...')
            available = self.uninstaller.check_uninstall_available(app_id, app['name'])
            if not available:
                print('✗ 无法自动卸载此应用，请手动卸载')
                return
        
        print(f'\n开始卸载: {app["name"]}')
        print('-' * 60)
        
        success, message = self.uninstaller.uninstall(app_id, app['name'])
        
        if success:
            print(f'✓ {message}')
        else:
            print(f'✗ {message}')
    
    def cmd_refresh_uninstall(self, args):
        """刷新卸载状态"""
        print('正在刷新所有已安装应用的卸载状态...')
        count = self.uninstaller.refresh_all_uninstall_status()
        print(f'✓ 已刷新 {count} 个应用的卸载状态')
    
    # ==================== 路径管理 ====================
    
    def cmd_set_base_path(self, args):
        """设置默认基础路径"""
        new_path = args.path
        
        # 验证路径
        path_obj = Path(new_path)
        if not path_obj.is_absolute():
            print('错误：请提供绝对路径')
            return
        
        self.config.set_default_base_path(new_path)
        print(f'✓ 默认基础安装路径已设置为: {new_path}')
        
        # 询问是否批量更新
        update_all = input('是否批量更新所有应用的基础路径？(y/N): ').strip().lower()
        if update_all == 'y':
            self.db.batch_update_base_path(new_path)
            print('✓ 已批量更新所有应用的安装路径')
            self.logger.info(f'批量更新基础路径: {new_path}')
    
    def cmd_set_path(self, args):
        """设置单个应用路径"""
        app_id = args.id
        new_base_path = args.path
        
        app = self.db.get_application(app_id)
        if not app:
            print(f'错误：未找到ID为 {app_id} 的应用')
            return
        
        self.db.update_application(app_id, base_install_path=new_base_path)
        
        # 重新获取更新后的应用信息
        app = self.db.get_application(app_id)
        print(f'✓ {app["name"]} 的安装路径已更新为: {app["final_install_path"]}')
        self.logger.info(f'更新应用路径: {app["name"]} -> {app["final_install_path"]}')
    
    # ==================== 日志查询 ====================
    
    def cmd_logs(self, args):
        """查看日志"""
        limit = args.limit or 50
        
        if args.app_name:
            # 查找应用ID
            apps = self.db.get_all_applications()
            app_id = None
            for app in apps:
                if args.app_name.lower() in app['name'].lower():
                    app_id = app['id']
                    break
            
            if not app_id:
                print(f'未找到应用: {args.app_name}')
                return
            
            logs = self.db.get_logs(app_id=app_id, limit=limit)
            print(f'\n{args.app_name} 的操作日志:')
        else:
            logs = self.db.get_logs(limit=limit)
            print(f'\n所有操作日志 (最近{limit}条):')
        
        if not logs:
            print('暂无日志')
            return
        
        print('=' * 100)
        print(f'{"时间":<20} {"应用名称":<20} {"操作":<10} {"状态":<10} {"消息":<30}')
        print('-' * 100)
        
        for log in logs:
            timestamp = log['timestamp'][:19] if log['timestamp'] else ''
            app_name = log.get('app_name', 'N/A')
            action = log['action']
            status = '✓' if log['status'] == 'success' else '✗'
            message = log['message'][:30] if log['message'] else ''
            
            print(f'{timestamp:<20} {app_name:<20} {action:<10} {status:<10} {message:<30}')
        
        print('=' * 100)
    
    def cmd_status(self, args):
        """查看状态统计"""
        stats = self.db.get_status_statistics()
        total = sum(stats.values())
        
        print('\n应用状态统计:')
        print('=' * 40)
        print(f'{"状态":<15} {"数量":<10} {"百分比":<10}')
        print('-' * 40)
        
        for status, count in stats.items():
            percentage = f'{count/total*100:.1f}%' if total > 0 else '0%'
            print(f'{status:<15} {count:<10} {percentage:<10}')
        
        print('-' * 40)
        print(f'{"总计":<15} {total:<10} {"100%":<10}')
        print('=' * 40)
    
    # ==================== 主函数 ====================
    
    def _extract_name_from_filename(self, stem: str) -> str:
        """
        从文件名中提取干净的软件名称
        
        Args:
            stem: 文件名（不含扩展名）
        
        Returns:
            提取的软件名称
        """
        import re

        name = stem.strip()
        # 替换常见分隔符为空格
        name = re.sub(r'[_\-]+', ' ', name)
        # 去掉常见冗余标记（版本号、架构等）
        # 匹配结尾的版本号模式：空格 + 数字 + 点号 + 数字
        name = re.sub(r'\s*\d+[\d\.]+\s*$', '', name)
        # 匹配结尾的架构标记 (x64, x86, win64, etc.)
        name = re.sub(r'\s*(x64|x86|win64|win32|windows|setup|installer)\s*$', '', name, flags=re.IGNORECASE)
        # 匹配开头引导词 (setup, install, etc.)
        name = re.sub(r'^(setup|install|installer)\s+', '', name, flags=re.IGNORECASE)
        # 清理多余空格
        name = re.sub(r'\s+', ' ', name).strip()
        # 首字母大写
        name = name.title() if name else stem

        return name if name else stem

    def cmd_scan_packages(self, args):
        """
        扫描 packages 目录并自动添加安装包到应用列表
        """
        packages_dir = self.workspace.packages_dir

        if not packages_dir.exists():
            print(f'错误：安装包目录不存在 {packages_dir}')
            print('请先创建该目录并将安装包放入其中')
            return

        supported = {'.exe', '.msi', '.bat'}
        installer_files = sorted([
            f for f in packages_dir.iterdir()
            if f.is_file() and f.suffix.lower() in supported
        ])

        if not installer_files:
            print(f'在 {packages_dir} 中未找到 .exe、.msi 或 .bat 安装包')
            return

        print(f'\n📂 扫描到 {len(installer_files)} 个安装包:\n')

        imported = 0
        skipped = 0
        failed = 0
        name_seen = {}

        for file_path in installer_files:
            try:
                # 1. 检查是否已存在（基于 package_path 去重）
                package_rel = self.workspace.to_relative_path(file_path)
                existing = self.db.get_application_by_path(package_rel)
                if existing:
                    print(f'  ⏭️ [{file_path.name}] 已在列表中 (ID={existing["id"]})')
                    skipped += 1
                    continue

                # 2. 提取软件名称
                name = self._extract_name_from_filename(file_path.stem)

                # 3. 检测静默参数
                install_args = None
                source = ''
                try:
                    detect_result = self.param_detector.detect_params(
                        str(file_path), name
                    )
                    if detect_result:
                        if isinstance(detect_result, tuple):
                            install_args, source = detect_result
                        else:
                            install_args = detect_result
                            source = '自动检测'
                except Exception:
                    pass

                params_info = f'参数={install_args}' if install_args else '参数=默认'

                # 4. 设置安装信息
                base_path = self.config.get_default_base_path()
                folder_name = name.replace(' ', '')
                version = ''

                # 5. 添加到数据库
                app_id = self.db.add_application(
                    name=name,
                    package_path=package_rel,
                    folder_name=folder_name,
                    base_install_path=base_path,
                    version=version,
                    install_args=install_args
                )

                # 检测名称重复（不同路径但同名）
                if name in name_seen and name_seen[name] != package_rel:
                    print(f'  ⚠️ [{file_path.name}] → {name} (ID={app_id}, {params_info}) 与已有软件同名')
                else:
                    print(f'  ✅ [{file_path.name}] → {name} (ID={app_id}, {params_info})')
                name_seen[name] = package_rel

                self.logger.info(f'扫描添加应用: {name} (ID={app_id}, 路径={package_rel})')
                imported += 1

            except Exception as e:
                print(f'  ❌ [{file_path.name}] 添加失败: {e}')
                self.logger.error(f'扫描添加失败: {file_path.name} - {e}')
                failed += 1

        # 汇总
        print(f'\n📊 扫描完成: 新增 {imported} 个, 已存在 {skipped} 个, 失败 {failed} 个\n')

        if imported > 0 or failed > 0:
            print('提示：可在「应用列表」中编辑修正名称、版本和安装参数')
    
    def run(self):
        """运行主程序"""
        parser = argparse.ArgumentParser(
            description='批量应用安装管理器',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        subparsers = parser.add_subparsers(dest='command', help='命令')
        
        # 添加应用
        parser_add = subparsers.add_parser('add', help='添加应用')
        parser_add.add_argument('package_path', help='安装包路径')
        
        # 列出应用
        subparsers.add_parser('list', help='列出所有应用')
        
        # 删除应用
        parser_remove = subparsers.add_parser('remove', help='删除应用')
        parser_remove.add_argument('id', type=int, help='应用ID')
        
        # 编辑应用
        parser_edit = subparsers.add_parser('edit', help='编辑应用信息')
        parser_edit.add_argument('id', type=int, help='应用ID')
        
        # 安装
        parser_install = subparsers.add_parser('install', help='安装单个应用')
        parser_install.add_argument('id', type=int, help='应用ID')
        
        subparsers.add_parser('install-all', help='批量安装所有待安装应用')
        
        # 卸载
        subparsers.add_parser('uninstall-list', help='显示已安装应用及卸载状态')
        
        parser_uninstall = subparsers.add_parser('uninstall', help='卸载应用')
        parser_uninstall.add_argument('id', type=int, help='应用ID')
        
        subparsers.add_parser('refresh-uninstall', help='刷新卸载状态')
        
        # 路径管理
        parser_set_base = subparsers.add_parser('set-base-path', help='设置默认基础路径')
        parser_set_base.add_argument('path', help='新的基础路径')
        
        parser_set_path = subparsers.add_parser('set-path', help='设置单个应用路径')
        parser_set_path.add_argument('id', type=int, help='应用ID')
        parser_set_path.add_argument('path', help='新的基础路径')
        
        # 日志查询
        parser_logs = subparsers.add_parser('logs', help='查看日志')
        parser_logs.add_argument('app_name', nargs='?', help='应用名称（可选）')
        parser_logs.add_argument('--limit', type=int, help='显示条数')
        
        subparsers.add_parser('status', help='查看状态统计')
        
        # 扫描安装包
        subparsers.add_parser('scan-packages', help='扫描 packages 目录并自动添加安装包')
        
        # 解析参数
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return
        
        # 执行命令
        command_map = {
            'add': self.cmd_add,
            'list': self.cmd_list,
            'remove': self.cmd_remove,
            'edit': self.cmd_edit,
            'install': self.cmd_install,
            'install-all': self.cmd_install_all,
            'uninstall-list': self.cmd_uninstall_list,
            'uninstall': self.cmd_uninstall,
            'refresh-uninstall': self.cmd_refresh_uninstall,
            'set-base-path': self.cmd_set_base_path,
            'set-path': self.cmd_set_path,
            'logs': self.cmd_logs,
            'status': self.cmd_status,
            'scan-packages': self.cmd_scan_packages,
        }
        
        command_func = command_map.get(args.command)
        if command_func:
            try:
                command_func(args)
            except KeyboardInterrupt:
                print('\n\n操作已取消')
            except Exception as e:
                print(f'\n错误: {e}')
                self.logger.error(f'命令执行错误: {e}', exc_info=True)
        else:
            parser.print_help()


def main():
    """程序入口"""
    cli = None
    try:
        cli = AppInstallerCLI()
        cli.run()
    except Exception as e:
        print(f'程序错误: {e}')
        sys.exit(1)
    finally:
        if cli and cli.db:
            cli.db.close()


if __name__ == '__main__':
    main()

