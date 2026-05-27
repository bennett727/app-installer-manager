# -*- coding: utf-8 -*-
"""
SQLite数据库操作模块
管理应用信息、安装日志和参数缓存
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    """数据库管理类"""
    
    # update_application 允许更新的字段白名单（防止 SQL 字段名注入）
    _ALLOWED_UPDATE_FIELDS = {
        'name', 'package_path', 'folder_name', 'base_install_path',
        'final_install_path', 'version', 'install_args', 'status',
        'uninstall_available'
    }
    
    def __init__(self, db_path: str):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 返回字典形式的结果
        return self.conn
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 创建应用信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                package_path TEXT NOT NULL UNIQUE,
                folder_name TEXT NOT NULL,
                base_install_path TEXT DEFAULT 'C:\\Program Files',
                final_install_path TEXT,
                version TEXT,
                install_args TEXT,
                status TEXT DEFAULT '待安装',
                uninstall_available INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建安装日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS install_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id INTEGER,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES applications(id)
            )
        ''')
        
        # 创建参数缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS param_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                software_name TEXT UNIQUE NOT NULL,
                install_args TEXT NOT NULL,
                source TEXT,
                cached_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建开机自启项表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS startup_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id INTEGER,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                location TEXT,
                type TEXT,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                removed INTEGER DEFAULT 0,
                FOREIGN KEY (app_id) REFERENCES applications(id)
            )
        ''')

        # 添加 package_path 唯一索引（防止重复插入相同路径）
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_package_path_unique
            ON applications(package_path)
        ''')

        conn.commit()
    
    # ==================== 应用管理 ====================
    
    def add_application(self, name: str, package_path: str, folder_name: str,
                       base_install_path: str = 'C:\\Program Files',
                       version: str = '', install_args: str = '') -> int:
        """
        添加应用到数据库

        Args:
            name: 应用名称
            package_path: 安装包路径
            folder_name: 安装文件夹名称
            base_install_path: 基础安装路径
            version: 版本号
            install_args: 静默安装参数

        Returns:
            新添加应用的ID，若路径已存在则返回已有ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 二次防御：INSERT 前再次检查路径是否已存在
        cursor.execute('SELECT id FROM applications WHERE package_path = ?', (package_path,))
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # 计算最终安装路径
        final_install_path = str(Path(base_install_path) / folder_name)
        
        cursor.execute('''
            INSERT INTO applications 
            (name, package_path, folder_name, base_install_path, 
             final_install_path, version, install_args, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, package_path, folder_name, base_install_path,
              final_install_path, version, install_args, datetime.now().isoformat()))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_application(self, app_id: int) -> Optional[Dict]:
        """
        获取单个应用信息
        
        Args:
            app_id: 应用ID
        
        Returns:
            应用信息字典，不存在则返回None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_application_by_path(self, package_path: str) -> Optional[Dict]:
        """
        根据安装包路径查找应用
        
        Args:
            package_path: 安装包路径
        
        Returns:
            应用信息，未找到返回None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE package_path = ?', (package_path,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_applications(self, status: Optional[str] = None) -> List[Dict]:
        """
        获取所有应用列表
        
        Args:
            status: 筛选状态（待安装/已安装/失败），None表示获取所有
        
        Returns:
            应用信息列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM applications WHERE status = ? ORDER BY id', (status,))
        else:
            cursor.execute('SELECT * FROM applications ORDER BY id')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_application(self, app_id: int, **kwargs):
        """
        更新应用信息
        
        Args:
            app_id: 应用ID
            **kwargs: 要更新的字段和值
        """
        if not kwargs:
            return
        
        # 白名单过滤：仅允许更新预定义的字段（防御性编程）
        kwargs = {k: v for k, v in kwargs.items() if k in self._ALLOWED_UPDATE_FIELDS}
        if not kwargs:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 添加更新时间
        kwargs['updated_at'] = datetime.now().isoformat()
        
        # 如果更新了base_install_path或folder_name，重新计算final_install_path
        if 'base_install_path' in kwargs or 'folder_name' in kwargs:
            app = self.get_application(app_id)
            if app:
                base = kwargs.get('base_install_path', app['base_install_path'])
                folder = kwargs.get('folder_name', app['folder_name'])
                kwargs['final_install_path'] = str(Path(base) / folder)
        
        # 构建SQL语句
        fields = ', '.join([f'{key} = ?' for key in kwargs.keys()])
        values = list(kwargs.values()) + [app_id]
        
        cursor.execute(f'UPDATE applications SET {fields} WHERE id = ?', values)
        conn.commit()
    
    def delete_application(self, app_id: int):
        """
        删除应用记录
        
        Args:
            app_id: 应用ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM applications WHERE id = ?', (app_id,))
        conn.commit()
    
    def update_install_status(self, app_id: int, status: str):
        """
        更新应用安装状态
        
        Args:
            app_id: 应用ID
            status: 状态（待安装/已安装/失败）
        """
        self.update_application(app_id, status=status)
    
    def batch_update_base_path(self, new_base_path: str):
        """
        批量更新所有应用的基础安装路径
        
        Args:
            new_base_path: 新的基础路径
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 获取所有应用
        apps = self.get_all_applications()
        
        for app in apps:
            final_path = str(Path(new_base_path) / app['folder_name'])
            cursor.execute('''
                UPDATE applications 
                SET base_install_path = ?, final_install_path = ?, updated_at = ?
                WHERE id = ?
            ''', (new_base_path, final_path, datetime.now().isoformat(), app['id']))
        
        conn.commit()
    
    # ==================== 日志管理 ====================
    
    def add_log(self, app_id: int, action: str, status: str, message: str = ''):
        """
        添加安装/卸载日志
        
        Args:
            app_id: 应用ID
            action: 操作类型（install/uninstall）
            status: 状态（success/failed）
            message: 详细信息
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO install_logs (app_id, action, status, message)
            VALUES (?, ?, ?, ?)
        ''', (app_id, action, status, message))
        
        conn.commit()
    
    def get_logs(self, app_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        获取日志记录
        
        Args:
            app_id: 应用ID（None表示获取所有）
            limit: 返回记录数限制
        
        Returns:
            日志记录列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if app_id:
            cursor.execute('''
                SELECT l.*, a.name as app_name 
                FROM install_logs l
                LEFT JOIN applications a ON l.app_id = a.id
                WHERE l.app_id = ?
                ORDER BY l.timestamp DESC
                LIMIT ?
            ''', (app_id, limit))
        else:
            cursor.execute('''
                SELECT l.*, a.name as app_name 
                FROM install_logs l
                LEFT JOIN applications a ON l.app_id = a.id
                ORDER BY l.timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_status_statistics(self) -> Dict[str, int]:
        """
        获取应用状态统计
        
        Returns:
            状态统计字典 {'待安装': 5, '已安装': 10, '失败': 2}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM applications
            GROUP BY status
        ''')
        
        stats = {row['status']: row['count'] for row in cursor.fetchall()}
        return stats
    
    # ==================== 参数缓存管理 ====================
    
    def get_cached_params(self, software_name: str) -> Optional[str]:
        """
        从缓存获取静默参数
        
        Args:
            software_name: 软件名称
        
        Returns:
            静默参数字符串，未找到返回None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT install_args FROM param_cache 
            WHERE software_name = ?
        ''', (software_name.lower(),))
        
        row = cursor.fetchone()
        return row['install_args'] if row else None
    
    def cache_params(self, software_name: str, install_args: str, source: str = 'auto'):
        """
        缓存静默参数
        
        Args:
            software_name: 软件名称
            install_args: 静默参数
            source: 来源（网络/本地/用户输入/auto）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO param_cache 
            (software_name, install_args, source, cached_at)
            VALUES (?, ?, ?, ?)
        ''', (software_name.lower(), install_args, source, datetime.now().isoformat()))
        
        conn.commit()
    
    # ==================== 开机自启管理 ====================
    
    def record_startup_items(self, app_id: int, items: List[Dict]):
        """
        记录应用的开机自启项
        
        Args:
            app_id: 应用ID
            items: 启动项列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for item in items:
            cursor.execute('''
                INSERT INTO startup_items (app_id, name, path, location, type)
                VALUES (?, ?, ?, ?, ?)
            ''', (app_id, item['name'], item['path'], item['location'], item.get('type', 'unknown')))
        
        conn.commit()
    
    def get_startup_items_by_app(self, app_id: int) -> List[Dict]:
        """
        获取特定应用的开机自启项
        
        Args:
            app_id: 应用ID
        
        Returns:
            启动项列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM startup_items 
            WHERE app_id = ? AND removed = 0
            ORDER BY detected_at DESC
        ''', (app_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_recorded_startup_items(self) -> List[Dict]:
        """
        获取所有记录的开机自启项（包含应用信息）
        
        Returns:
            启动项列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.*, a.name as app_name
            FROM startup_items s
            LEFT JOIN applications a ON s.app_id = a.id
            WHERE s.removed = 0
            ORDER BY s.detected_at DESC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def mark_startup_removed(self, startup_id: int):
        """
        标记启动项已删除
        
        Args:
            startup_id: 启动项ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE startup_items 
            SET removed = 1
            WHERE id = ?
        ''', (startup_id,))
        
        conn.commit()
    
    # ==================== 其他 ====================
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

