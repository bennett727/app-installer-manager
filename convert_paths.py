# -*- coding: utf-8 -*-
"""
Path Conversion Tool
Convert absolute paths to relative paths in the database
"""

import sys
from pathlib import Path

from database import Database
from config import WorkspaceManager


def convert_paths():
    """Convert absolute paths to relative paths in database"""
    
    # Get program root directory
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.absolute()
    
    # Initialize
    workspace = WorkspaceManager(base_dir)
    db = Database(workspace.db_path)
    
    print('=' * 60)
    print('Path Conversion Tool / 路径转换工具')
    print('=' * 60)
    print(f'Program root / 程序根目录: {base_dir}')
    print(f'Data directory / 数据目录: {workspace.data_dir}')
    print()
    
    # Get all applications
    apps = db.get_all_applications()
    
    if not apps:
        print('No applications found in database / 数据库中没有应用记录')
        return
    
    print(f'Found {len(apps)} applications / 找到 {len(apps)} 个应用记录')
    print()
    
    converted_count = 0
    skipped_count = 0
    
    for app in apps:
        app_id = app['id']
        app_name = app['name']
        old_path = app['package_path']
        
        # Convert path
        path_obj = Path(old_path)
        
        # Skip if already relative path
        if not path_obj.is_absolute():
            print(f'[SKIP/跳过] {app_name}: Already relative path / 已经是相对路径')
            skipped_count += 1
            continue
        
        # Convert to relative path
        try:
            new_path = workspace.to_relative_path(path_obj)
            
            # Skip if path didn't change (not in program directory)
            if new_path == old_path:
                print(f'[SKIP/跳过] {app_name}: Not in program directory / 不在程序目录下')
                skipped_count += 1
                continue
            
            # Update database
            db.update_application(app_id, package_path=new_path)
            
            print(f'[CONVERT/转换] {app_name}')
            print(f'  Old path / 旧路径: {old_path}')
            print(f'  New path / 新路径: {new_path}')
            print()
            
            converted_count += 1
        
        except Exception as e:
            print(f'[ERROR/错误] {app_name}: {e}')
            print()
    
    print('=' * 60)
    print(f'Conversion completed! / 转换完成!')
    print(f'  Converted / 已转换: {converted_count}')
    print(f'  Skipped / 已跳过: {skipped_count}')
    print(f'  Total / 总计: {len(apps)}')
    print('=' * 60)
    
    db.close()


if __name__ == '__main__':
    try:
        convert_paths()
    except KeyboardInterrupt:
        print('\n\nOperation cancelled / 操作已取消')
    except Exception as e:
        print(f'\nError / 错误: {e}')
        import traceback
        traceback.print_exc()
    
    input('\nPress Enter to exit / 按回车键退出...')

