# -*- coding: utf-8 -*-
"""
批量应用安装管理器 - GUI主窗口
基于 Tkinter 的图形界面
"""

import os
import sys
import threading
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox, scrolledtext

from database import Database
from logger import get_logger
from installer import Installer
from uninstaller import Uninstaller
from param_detector import ParamDetector
from config import Config, WorkspaceManager, check_expiration, get_expiration_info, activate
from startup_manager import StartupManager


class AppInstallerGUI:
    """图形界面主类"""
    
    def __init__(self):
        """初始化GUI"""
        # 获取程序根目录
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent.absolute()
        
        # 初始化工作目录
        self.workspace = WorkspaceManager(self.base_dir)
        if not self.workspace.initialize():
            messagebox.showerror(
                "错误",
                f"无法初始化工作目录\n\n"
                f"请确保程序有权限在以下位置创建文件：\n{self.workspace.data_dir}\n\n"
                f"建议：\n"
                f"1. 将程序移动到非系统保护目录（如 D:\\AppInstaller\\）\n"
                f"2. 或以管理员身份运行"
            )
            sys.exit(1)
        
        # 检查有效期
        config_path = self.workspace.data_dir / 'config.json'
        status, expire_msg, days_left = check_expiration(config_path)
        if status == 'expired':
            messagebox.showerror("软件已过期", expire_msg)
            sys.exit(1)
        elif status == 'warning':
            messagebox.showwarning("许可证即将到期", expire_msg)
        
        # 初始化组件
        self.logger = get_logger(log_dir=self.workspace.logs_dir)
        self.config = Config(self.workspace.data_dir / 'config.json')
        self.db = Database(self.workspace.db_path)
        self.param_detector = ParamDetector(database=self.db)
        self.startup_manager = StartupManager(logger=self.logger, database=self.db)
        self.installer = Installer(logger=self.logger, database=self.db, workspace=self.workspace, startup_manager=self.startup_manager, param_detector=self.param_detector)
        self.uninstaller = Uninstaller(logger=self.logger, database=self.db)
        
        self.logger.info('GUI界面启动')
        
        # 创建主窗口
        self.root = Tk()
        self.root.title("批量应用安装管理器 v1.1")

        # 获取屏幕尺寸，智能计算窗口大小和位置
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 窗口大小：根据屏幕自适应（最大85%屏幕，最小1300x800）
        window_width = max(1300, int(screen_width * 0.60))
        window_height = max(800, int(screen_height * 0.60))

        # 居中显示
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 设置最小窗口尺寸（防止缩太小导致布局错乱）
        self.root.minsize(1200, 700)

        # 设置窗口图标（如果存在）
        try:
            icon_path = self.base_dir / 'app_icon.ico'
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        # 设置主题
        self.style = ttk.Style()
        self.style.theme_use('clam')  # 使用现代主题
        
        # 配置颜色
        self.setup_styles()
        
        # 创建界面
        self.create_widgets()
        
        # 加载数据
        self.refresh_app_list()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """设置界面样式"""
        # 配色方案
        self.COLORS = {
            'bg': '#f5f5f5',
            'card_bg': '#ffffff',
            'header_bg': '#1a73e8',
            'header_fg': '#ffffff',
            'primary': '#1a73e8',
            'primary_hover': '#1557b0',
            'success': '#34a853',
            'warning': '#fbbc04',
            'danger': '#ea4335',
            'text': '#202124',
            'text_secondary': '#5f6368',
            'border': '#dadce0',
            'hover': '#f1f3f4',
            'even_row': '#f8f9fa',
            'odd_row': '#ffffff',
        }

        # 根窗口背景
        self.root.configure(bg=self.COLORS['bg'])

        # ttk 主题基础
        self.style.theme_use('clam')
        self.style.configure('.', background=self.COLORS['bg'], foreground=self.COLORS['text'])

        # 标签样式
        self.style.configure('Title.TLabel', font=('微软雅黑', 16, 'bold'), foreground=self.COLORS['header_fg'], background=self.COLORS['header_bg'])
        self.style.configure('Heading.TLabel', font=('微软雅黑', 12, 'bold'), foreground=self.COLORS['text'])
        self.style.configure('Normal.TLabel', font=('微软雅黑', 10), foreground=self.COLORS['text'])
        self.style.configure('CardTitle.TLabel', font=('微软雅黑', 11, 'bold'), foreground=self.COLORS['text'])
        self.style.configure('Subtitle.TLabel', font=('微软雅黑', 9), foreground=self.COLORS['text_secondary'])

        # Treeview 样式
        self.style.configure('Treeview', rowheight=32, font=('微软雅黑', 10))
        self.style.configure('Treeview.Heading', font=('微软雅黑', 10, 'bold'), background=self.COLORS['bg'])
        self.style.map('Treeview',
            background=[('selected', self.COLORS['primary'])],
            foreground=[('selected', 'white')]
        )

        # 标签页（Notebook）样式
        self.style.configure('TNotebook', background=self.COLORS['bg'], borderwidth=0)
        self.style.configure('TNotebook.Tab', font=('微软雅黑', 10), padding=[12, 4])
        self.style.map('TNotebook.Tab',
            background=[('selected', '#ffffff'), ('active', self.COLORS['hover'])],
            foreground=[('selected', self.COLORS['primary'])]
        )

        # 按钮样式
        self.style.configure('TButton', font=('微软雅黑', 9), padding=[8, 4])
        self.style.map('TButton',
            background=[('active', self.COLORS['hover'])],
            foreground=[('active', self.COLORS['primary'])]
        )

        # 滚动条
        self.style.configure('TScrollbar', arrowsize=12)

        # 标签帧（Labelframe）
        self.style.configure('TLabelframe', background=self.COLORS['card_bg'], relief='solid', borderwidth=1)
        self.style.configure('TLabelframe.Label', font=('微软雅黑', 10, 'bold'), foreground=self.COLORS['text'])
    
    def create_widgets(self):
        """创建界面组件"""
        # 顶部标题栏
        self.create_header()
        
        # 主要内容区域（使用Notebook实现标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # 创建各个标签页
        self.create_app_list_tab()
        self.create_install_tab()
        self.create_uninstall_tab()
        self.create_startup_tab()
        self.create_logs_tab()
        self.create_settings_tab()
        
        # 底部状态栏
        self.create_statusbar()
    
    def create_header(self):
        """创建顶部标题栏"""
        header_frame = Frame(self.root, bg=self.COLORS['header_bg'], height=60)
        header_frame.pack(fill=X)
        header_frame.pack_propagate(False)

        # 标题和副标题
        title_frame = Frame(header_frame, bg=self.COLORS['header_bg'])
        title_frame.pack(side=LEFT, padx=20, pady=8)

        title_label = Label(
            title_frame,
            text="📦 批量应用安装管理器",
            font=('微软雅黑', 16, 'bold'),
            fg=self.COLORS['header_fg'],
            bg=self.COLORS['header_bg']
        )
        title_label.pack(anchor=W)

        subtitle = Label(
            title_frame,
            text="智能静默安装 · 批量部署 · 开机自启管理",
            font=('微软雅黑', 9),
            fg='#b3d4fc',
            bg=self.COLORS['header_bg']
        )
        subtitle.pack(anchor=W)

        # 右侧快捷按钮
        btn_frame = Frame(header_frame, bg=self.COLORS['header_bg'])
        btn_frame.pack(side=RIGHT, padx=20)

        ttk.Button(
            btn_frame,
            text="➕ 添加应用",
            command=self.add_application,
            width=12
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="🔄 刷新",
            command=self.refresh_app_list,
            width=10
        ).pack(side=LEFT, padx=5)
    
    def create_statusbar(self):
        """创建底部状态栏"""
        self.statusbar = Label(
            self.root,
            text="就绪",
            relief=SUNKEN,
            anchor=W,
            font=('微软雅黑', 9),
            bg=self.COLORS['hover'],
            fg=self.COLORS['text_secondary'],
            padx=10
        )
        self.statusbar.pack(side=BOTTOM, fill=X)
    
    def create_app_list_tab(self):
        """创建应用列表标签页"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="📋 应用列表")
        
        # 工具栏
        toolbar = Frame(tab)
        toolbar.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(
            toolbar,
            text="➕ 添加",
            command=self.add_application
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="✏️ 编辑",
            command=self.edit_application
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="🗑️ 删除",
            command=self.delete_application
        ).pack(side=LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        
        ttk.Button(
            toolbar,
            text="🔄 刷新",
            command=self.refresh_app_list
        ).pack(side=LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        
        ttk.Button(
            toolbar,
            text="🔄 重试安装",
            command=self.retry_install
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="📁 打开安装文件夹",
            command=self.open_install_folder
        ).pack(side=LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        
        ttk.Button(
            toolbar,
            text="📂 扫描安装包",
            command=self.scan_packages
        ).pack(side=LEFT, padx=2)
        
        # 统计信息
        self.stats_label = Label(
            toolbar,
            text="",
            font=('微软雅黑', 10),
            fg='#666'
        )
        self.stats_label.pack(side=RIGHT, padx=10)
        
        # 应用列表（Treeview）
        list_frame = Frame(tab)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # 创建Treeview
        columns = ('ID', '名称', '版本', '状态', '安装路径', '参数')
        self.app_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            yscrollcommand=scrollbar.set
        )
        
        # 设置列
        self.app_tree.heading('ID', text='ID')
        self.app_tree.heading('名称', text='应用名称')
        self.app_tree.heading('版本', text='版本')
        self.app_tree.heading('状态', text='状态')
        self.app_tree.heading('安装路径', text='安装路径')
        self.app_tree.heading('参数', text='静默参数')
        
        self.app_tree.column('ID', width=50, anchor=CENTER)
        self.app_tree.column('名称', width=200, anchor=W)
        self.app_tree.column('版本', width=100, anchor=CENTER)
        self.app_tree.column('状态', width=100, anchor=CENTER)
        self.app_tree.column('安装路径', width=350, anchor=W)
        self.app_tree.column('参数', width=250, anchor=W)
        
        self.app_tree.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.app_tree.yview)
        
        # 双击编辑
        self.app_tree.bind('<Double-1>', lambda e: self.edit_application())
    
    def create_install_tab(self):
        """创建安装标签页"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="⬇️ 批量安装")
        
        # 左侧：待安装列表
        left_frame = Frame(tab)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)
        
        Label(
            left_frame,
            text="待安装应用",
            font=('微软雅黑', 12, 'bold')
        ).pack(anchor=W, pady=5)
        
        # 待安装列表
        list_frame = Frame(left_frame)
        list_frame.pack(fill=BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        columns = ('ID', '名称', '版本', '安装路径')
        self.pending_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            selectmode='extended',
            yscrollcommand=scrollbar.set
        )
        
        self.pending_tree.heading('ID', text='ID')
        self.pending_tree.heading('名称', text='应用名称')
        self.pending_tree.heading('版本', text='版本')
        self.pending_tree.heading('安装路径', text='安装路径')
        
        self.pending_tree.column('ID', width=50, anchor=CENTER)
        self.pending_tree.column('名称', width=200, anchor=W)
        self.pending_tree.column('版本', width=100, anchor=CENTER)
        self.pending_tree.column('安装路径', width=300, anchor=W)
        
        self.pending_tree.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.pending_tree.yview)
        
        # 右侧：安装控制
        right_frame = Frame(tab, width=300)
        right_frame.pack(side=RIGHT, fill=Y, padx=10, pady=10)
        right_frame.pack_propagate(False)
        
        Label(
            right_frame,
            text="安装控制",
            font=('微软雅黑', 12, 'bold')
        ).pack(anchor=W, pady=5)
        
        ttk.Separator(right_frame, orient=HORIZONTAL).pack(fill=X, pady=10)
        
        # 按钮
        ttk.Button(
            right_frame,
            text="🚀 批量安装所有 (慎重)",
            command=self.batch_install,
            width=20
        ).pack(pady=5, fill=X)
        
        ttk.Button(
            right_frame,
            text="▶️ 安装选中 (可多选)",
            command=self.install_selected,
            width=20
        ).pack(pady=5, fill=X)
        
        ttk.Separator(right_frame, orient=HORIZONTAL).pack(fill=X, pady=10)
        
        # 进度显示
        Label(
            right_frame,
            text="安装进度",
            font=('微软雅黑', 10, 'bold')
        ).pack(anchor=W, pady=5)
        
        self.install_progress = ttk.Progressbar(
            right_frame,
            mode='determinate'
        )
        self.install_progress.pack(fill=X, pady=5)
        
        self.install_status_label = Label(
            right_frame,
            text="未开始",
            font=('微软雅黑', 9),
            fg='#666',
            wraplength=280,
            justify=LEFT
        )
        self.install_status_label.pack(anchor=W, pady=5)
        
        # 日志输出框
        Label(
            right_frame,
            text="实时日志",
            font=('微软雅黑', 10, 'bold')
        ).pack(anchor=W, pady=(10, 5))
        
        self.install_log = scrolledtext.ScrolledText(
            right_frame,
            height=15,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white'
        )
        self.install_log.pack(fill=BOTH, expand=True, pady=5)
        
        # 绑定刷新事件
        tab.bind('<Visibility>', lambda e: self.refresh_pending_list())
    
    def create_uninstall_tab(self):
        """创建卸载标签页"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="🗑️ 应用卸载")
        
        # 工具栏
        toolbar = Frame(tab)
        toolbar.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(
            toolbar,
            text="🔄 刷新卸载状态",
            command=self.refresh_uninstall_status
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="🗑️ 卸载选中",
            command=self.uninstall_selected
        ).pack(side=LEFT, padx=2)
        
        # 已安装应用列表
        list_frame = Frame(tab)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        columns = ('ID', '名称', '版本', '安装路径', '卸载状态')
        self.installed_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            yscrollcommand=scrollbar.set
        )
        
        self.installed_tree.heading('ID', text='ID')
        self.installed_tree.heading('名称', text='应用名称')
        self.installed_tree.heading('版本', text='版本')
        self.installed_tree.heading('安装路径', text='安装路径')
        self.installed_tree.heading('卸载状态', text='卸载状态')
        
        self.installed_tree.column('ID', width=50, anchor=CENTER)
        self.installed_tree.column('名称', width=250, anchor=W)
        self.installed_tree.column('版本', width=100, anchor=CENTER)
        self.installed_tree.column('安装路径', width=400, anchor=W)
        self.installed_tree.column('卸载状态', width=150, anchor=CENTER)
        
        self.installed_tree.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.installed_tree.yview)
        
        # 绑定刷新事件
        tab.bind('<Visibility>', lambda e: self.refresh_installed_list())
    
    def create_startup_tab(self):
        """创建开机自启管理标签页"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="🚀 开机自启")
        
        # 工具栏
        toolbar = Frame(tab)
        toolbar.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(
            toolbar,
            text="🔄 刷新列表",
            command=self.refresh_startup_list
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="🗑️ 删除选中",
            command=self.remove_startup_selected
        ).pack(side=LEFT, padx=2)
        
        Label(
            toolbar,
            text="提示：显示系统所有开机自启项，可选中后删除",
            font=('微软雅黑', 9),
            fg='#666'
        ).pack(side=RIGHT, padx=10)
        
        # 开机自启列表
        list_frame = Frame(tab)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        columns = ('应用', '名称', '位置', '路径')
        self.startup_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            yscrollcommand=scrollbar.set
        )
        
        self.startup_tree.heading('应用', text='所属应用')
        self.startup_tree.heading('名称', text='启动项名称')
        self.startup_tree.heading('位置', text='启动位置')
        self.startup_tree.heading('路径', text='程序路径')
        
        self.startup_tree.column('应用', width=150, anchor=W)
        self.startup_tree.column('名称', width=200, anchor=W)
        self.startup_tree.column('位置', width=200, anchor=W)
        self.startup_tree.column('路径', width=450, anchor=W)
        
        self.startup_tree.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.startup_tree.yview)
        
        # 底部说明
        info_frame = Frame(tab, bg='#fff3cd', height=60)
        info_frame.pack(fill=X, padx=10, pady=5)
        info_frame.pack_propagate(False)
        
        Label(
            info_frame,
            text="💡 提示：",
            font=('微软雅黑', 10, 'bold'),
            bg='#fff3cd',
            fg='#856404'
        ).pack(side=LEFT, padx=10)
        
        Label(
            info_frame,
            text="这里显示的是系统中所有开机自启项。选中后点击[删除选中]可移除，移除后该程序将不再开机自动运行。",
            font=('微软雅黑', 9),
            bg='#fff3cd',
            fg='#856404',
            wraplength=1000,
            justify=LEFT
        ).pack(side=LEFT, padx=5)
        
        # 绑定刷新事件
        tab.bind('<Visibility>', lambda e: self.refresh_startup_list())
    
    def create_logs_tab(self):
        """创建日志标签页"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="📝 操作日志")
        
        # 工具栏
        toolbar = Frame(tab)
        toolbar.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(
            toolbar,
            text="🔄 刷新日志",
            command=self.refresh_logs
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="🗑️ 清空显示",
            command=self.clear_log_display
        ).pack(side=LEFT, padx=2)
        
        Label(toolbar, text="显示条数:").pack(side=LEFT, padx=(20, 5))
        
        self.log_limit_var = StringVar(value='100')
        limit_combo = ttk.Combobox(
            toolbar,
            textvariable=self.log_limit_var,
            values=['50', '100', '200', '500', '1000'],
            width=10
        )
        limit_combo.pack(side=LEFT, padx=2)
        limit_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_logs())
        
        # 日志列表
        list_frame = Frame(tab)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        columns = ('时间', '应用', '操作', '状态', '消息')
        self.log_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            yscrollcommand=scrollbar.set
        )
        
        self.log_tree.heading('时间', text='时间')
        self.log_tree.heading('应用', text='应用名称')
        self.log_tree.heading('操作', text='操作')
        self.log_tree.heading('状态', text='状态')
        self.log_tree.heading('消息', text='消息')
        
        self.log_tree.column('时间', width=150, anchor=W)
        self.log_tree.column('应用', width=200, anchor=W)
        self.log_tree.column('操作', width=100, anchor=CENTER)
        self.log_tree.column('状态', width=100, anchor=CENTER)
        self.log_tree.column('消息', width=500, anchor=W)
        
        self.log_tree.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.log_tree.yview)
        
        # 绑定刷新事件
        tab.bind('<Visibility>', lambda e: self.refresh_logs())
    
    def create_settings_tab(self):
        """创建设置标签页（带智能滚动支持）"""
        tab = Frame(self.notebook)
        self.notebook.add(tab, text="⚙️ 设置")

        # 创建Canvas和Scrollbar实现滚动
        canvas = Canvas(tab, bg=self.COLORS['bg'], highlightthickness=0)
        scrollbar = Scrollbar(tab, orient="vertical", command=canvas.yview)

        # 可滚动的设置面板
        settings_frame = Frame(canvas, bg=self.COLORS['bg'])

        # 创建Canvas窗口
        canvas_window = canvas.create_window((0, 0), window=settings_frame, anchor="nw")

        # 配置滚动
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_frame_configure(event=None):
            """当内容框架大小改变时，更新滚动区域"""
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event=None):
            """当Canvas大小改变时，调整内容宽度并检查是否需要滚动"""
            # 让内容框架宽度跟随Canvas宽度
            canvas.itemconfig(canvas_window, width=event.width)

            # 更新滚动区域
            canvas.configure(scrollregion=canvas.bbox("all"))

            # 检查是否需要滚动条
            bbox = canvas.bbox("all")
            if bbox:
                content_height = bbox[3] - bbox[1]
                canvas_height = event.height

                if content_height <= canvas_height:
                    # 内容完全可见，禁用滚动
                    scrollbar.pack_forget()
                    canvas.configure(yscrollcommand=lambda *args: None)
                else:
                    # 内容超出可视区域，显示滚动条
                    if not scrollbar.winfo_ismapped():
                        scrollbar.pack(side=RIGHT, fill=Y, pady=20, padx=(0, 20))
                        canvas.configure(yscrollcommand=scrollbar.set)

        # 绑定事件
        settings_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        # 鼠标滚轮事件（只在需要滚动时生效）
        def _on_mousewheel(event):
            # 只有在内容超出可视区域时才允许滚动
            bbox = canvas.bbox("all")
            if bbox:
                content_height = bbox[3] - bbox[1]
                canvas_height = canvas.winfo_height()
                if content_height > canvas_height:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # 绑定到settings_frame以确保鼠标在内容上也能滚动
        settings_frame.bind("<MouseWheel>", _on_mousewheel)

        # 布局
        canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=(20, 0), pady=20)
        # 初始不显示滚动条，根据需要动态显示

        # ===== 默认安装路径 =====
        Label(
            settings_frame,
            text="默认安装路径",
            font=('微软雅黑', 11, 'bold'),
            bg=self.COLORS['bg']
        ).pack(anchor=W, pady=(0, 5))

        path_frame = Frame(settings_frame, bg=self.COLORS['bg'])
        path_frame.pack(fill=X, pady=(0, 15))

        self.base_path_var = StringVar(value=self.config.get_default_base_path())
        path_entry = ttk.Entry(
            path_frame,
            textvariable=self.base_path_var,
            font=('微软雅黑', 10),
            width=55
        )
        path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        ttk.Button(path_frame, text="浏览...", command=self.browse_base_path).pack(side=LEFT, padx=2)
        ttk.Button(path_frame, text="保存", command=self.save_base_path).pack(side=LEFT, padx=2)
        ttk.Button(path_frame, text="批量应用", command=self.apply_base_path_to_all).pack(side=LEFT, padx=2)

        # 分隔线
        ttk.Separator(settings_frame, orient=HORIZONTAL).pack(fill=X, pady=15)

        # ===== 系统信息 =====
        Label(
            settings_frame,
            text="系统信息",
            font=('微软雅黑', 11, 'bold'),
            bg=self.COLORS['bg']
        ).pack(anchor=W, pady=(0, 10))

        info_text = f"""工作目录: {self.workspace.data_dir}
数据库路径: {self.workspace.db_path}
日志目录: {self.workspace.logs_dir}
安装包目录: {self.workspace.packages_dir}

管理员权限: {'是' if Config.is_admin() else '否'}"""

        info_label = Label(
            settings_frame,
            text=info_text.strip(),
            font=('Consolas', 9),
            justify=LEFT,
            fg='#666',
            bg=self.COLORS['bg']
        )
        info_label.pack(anchor=W)

        # 分隔线
        ttk.Separator(settings_frame, orient=HORIZONTAL).pack(fill=X, pady=15)

        # ===== 关于 =====
        Label(
            settings_frame,
            text="关于",
            font=('微软雅黑', 11, 'bold'),
            bg=self.COLORS['bg']
        ).pack(anchor=W, pady=(0, 10))

        exp_date, exp_desc = get_expiration_info(self.workspace.data_dir / 'config.json')
        about_text = f"""批量应用安装管理器  v1.1

一款 Windows 平台的应用批量安装管理工具，帮助人员高效管理
多个软件的安装、卸载和开机自启动。

📦 核心功能
    • 批量静默安装  • 智能参数自动检测
    • 注册表卸载    • 开机自启管理
    • 安装日志追溯  • 安装包本地管理

🔒 隐私保护
    所有数据存储在本地，无需联网，不会上传任何信息。

⏳ 使用期限
    有效期至：{exp_date}（{exp_desc}）

📞 技术支持
    开发者：只是向着
    如遇问题，欢迎来电咨询

© 2026 批量应用安装管理器"""

        about_label = Label(
            settings_frame,
            text=about_text.strip(),
            font=('微软雅黑', 9),
            justify=LEFT,
            fg='#666',
            bg=self.COLORS['bg']
        )
        about_label.pack(anchor=W)

        # 续期按钮
        ttk.Button(
            settings_frame,
            text="🔑 续期激活",
            command=self._show_activation_dialog
        ).pack(anchor=W, pady=(10, 0))
    
    # ==================== 事件处理函数 ====================
    
    def add_application(self):
        """添加应用对话框"""
        dialog = AddAppDialog(self.root, self)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.refresh_app_list()
            self.set_status(f"已添加应用: {dialog.result['name']}")
    
    def edit_application(self):
        """编辑应用"""
        selection = self.app_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要编辑的应用")
            return
        
        item = self.app_tree.item(selection[0])
        app_id = int(item['values'][0])
        
        dialog = EditAppDialog(self.root, self, app_id)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.refresh_app_list()
            self.set_status("应用信息已更新")
    
    def delete_application(self):
        """删除应用"""
        selection = self.app_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的应用")
            return
        
        item = self.app_tree.item(selection[0])
        app_id = int(item['values'][0])
        app_name = item['values'][1]
        
        if messagebox.askyesno("确认删除", f"确定要删除应用 '{app_name}' 吗？\n\n此操作不会卸载已安装的软件。"):
            self.db.delete_application(app_id)
            self.refresh_app_list()
            self.set_status(f"已删除应用: {app_name}")
            self.logger.info(f"删除应用: {app_name} (ID: {app_id})")
    
    def refresh_app_list(self):
        """刷新应用列表"""
        for item in self.app_tree.get_children():
            self.app_tree.delete(item)

        # 隔行变色
        self.app_tree.tag_configure('even', background=self.COLORS['even_row'])
        self.app_tree.tag_configure('odd', background=self.COLORS['odd_row'])

        apps = self.db.get_all_applications()

        if not apps:
            self.show_new_user_guide()
            stats_text = "总计: 0  |  待安装: 0  |  已安装: 0  |  失败: 0"
            self.stats_label.config(text=stats_text)
            self.set_status("暂无应用，请添加软件包")
            return

        for i, app in enumerate(apps):
            if app['status'] == '已安装':
                status = '✅ 已安装'
            elif app['status'] == '待安装':
                status = '⏳ 待安装'
            else:
                status = '❌ 失败'

            tag = 'even' if i % 2 == 0 else 'odd'
            self.app_tree.insert('', END, values=(
                app['id'],
                app['name'],
                app['version'] or '-',
                status,
                app['final_install_path'],
                app['install_args']
            ), tags=(tag,))
        
        # 更新统计信息
        stats = self.db.get_status_statistics()
        total = sum(stats.values())
        stats_text = f"总计: {total}  |  " + "  |  ".join([f"{k}: {v}" for k, v in stats.items()])
        self.stats_label.config(text=stats_text)
        
        self.set_status(f"已加载 {total} 个应用")
    
    def show_new_user_guide(self):
        """显示新用户引导"""
        # 创建引导对话框
        guide_dialog = Toplevel(self.root)
        guide_dialog.title("欢迎使用批量应用安装管理器")
        guide_dialog.geometry("600x500")
        guide_dialog.transient(self.root)
        guide_dialog.grab_set()
        
        # 居中显示
        guide_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - guide_dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - guide_dialog.winfo_height()) // 2
        guide_dialog.geometry(f"+{x}+{y}")
        
        # 主框架
        main_frame = Frame(guide_dialog, padx=20, pady=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # 标题
        title_label = Label(
            main_frame,
            text="🎉 欢迎使用批量应用安装管理器",
            font=('微软雅黑', 16, 'bold'),
            fg='#0078d7'
        )
        title_label.pack(pady=(0, 20))
        
        # 说明文本
        info_text = """
本软件是一个本地化的批量应用安装管理工具，可以帮助您：
• 集中管理多个软件的安装包
• 批量或单个安装软件
• 自动检测安装参数
• 管理已安装软件的卸载
• 管理开机自启动项

🔒 隐私保护：
• 所有数据均存储在本地，无需联网
• 不会上传任何软件包或个人信息
• 软件仅用于本地管理和安装

📦 使用方法：
1. 点击"添加应用"按钮，上传您需要安装的软件包
2. 软件会自动检测安装参数
3. 设置安装路径（建议非C盘）
4. 批量或单个安装软件
        """
        
        info_label = Label(
            main_frame,
            text=info_text,
            font=('微软雅黑', 10),
            justify=LEFT,
            wraplength=550
        )
        info_label.pack(pady=10, anchor=W)
        
        # 注意事项
        note_text = """
⚠️ 注意事项：
• 您需要自行准备需要安装的软件包
• 上传的软件包仅用于方便识别、管理和安装
• 请确保您有合法使用这些软件的授权
• 建议将软件包存放在非系统盘
        """
        
        note_label = Label(
            main_frame,
            text=note_text,
            font=('微软雅黑', 9),
            justify=LEFT,
            fg='#666666',
            wraplength=550
        )
        note_label.pack(pady=10, anchor=W)
        
        # 按钮
        btn_frame = Frame(main_frame)
        btn_frame.pack(pady=20)
        
        def add_first_app():
            guide_dialog.destroy()
            self.add_application()
        
        ttk.Button(
            btn_frame,
            text="📦 添加第一个应用",
            command=add_first_app,
            width=20
        ).pack(side=LEFT, padx=10)
        
        ttk.Button(
            btn_frame,
            text="❌ 关闭",
            command=guide_dialog.destroy,
            width=15
        ).pack(side=LEFT, padx=10)
    
    def refresh_pending_list(self):
        """刷新待安装列表"""
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)

        self.pending_tree.tag_configure('even', background=self.COLORS['even_row'])
        self.pending_tree.tag_configure('odd', background=self.COLORS['odd_row'])

        apps = self.db.get_all_applications(status='待安装')
        for i, app in enumerate(apps):
            tag = 'even' if i % 2 == 0 else 'odd'
            self.pending_tree.insert('', END, values=(
                app['id'],
                app['name'],
                app['version'] or '-',
                app['final_install_path']
            ), tags=(tag,))
    
    def refresh_installed_list(self):
        """刷新已安装列表"""
        for item in self.installed_tree.get_children():
            self.installed_tree.delete(item)

        self.installed_tree.tag_configure('even', background=self.COLORS['even_row'])
        self.installed_tree.tag_configure('odd', background=self.COLORS['odd_row'])

        apps = self.db.get_all_applications(status='已安装')
        for i, app in enumerate(apps):
            tag = 'even' if i % 2 == 0 else 'odd'
            status = '✅ 可卸载' if app['uninstall_available'] else '❌ 需手动卸载'
            self.installed_tree.insert('', END, values=(
                app['id'],
                app['name'],
                app['version'] or '-',
                app['final_install_path'],
                status
            ), tags=(tag,))
    
    def refresh_startup_list(self):
        """刷新开机自启列表"""
        for item in self.startup_tree.get_children():
            self.startup_tree.delete(item)

        self.startup_tree.tag_configure('even', background=self.COLORS['even_row'])
        self.startup_tree.tag_configure('odd', background=self.COLORS['odd_row'])

        # 获取系统当前所有启动项
        system_items = self.startup_manager.get_all_startup_items()

        # 获取数据库记录的启动项（用于关联应用名称）
        recorded_items = self.db.get_all_recorded_startup_items()
        # 构建路径→应用名称的映射
        path_to_app = {}
        for r in recorded_items:
            path_to_app[r['path'].lower()] = r.get('app_name', 'N/A')
            path_to_app[r['name'].lower()] = r.get('app_name', 'N/A')

        for i, item in enumerate(system_items):
            tag = 'even' if i % 2 == 0 else 'odd'
            # 尝试匹配数据库中的应用名称
            app_name = path_to_app.get(item['path'].lower(),
                        path_to_app.get(item['name'].lower(), ''))
            self.startup_tree.insert('', END, values=(
                app_name or '-',
                item['name'],
                item['location'],
                item['path']
            ), tags=(str(i), tag))
    
    def remove_startup_selected(self):
        """删除选中的开机自启项"""
        selection = self.startup_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的启动项")
            return

        item_widget = self.startup_tree.item(selection[0])
        values = item_widget['values']
        name = values[1]
        location = values[2]
        target_path = values[3]

        if not messagebox.askyesno("确认删除",
            f"确定要删除开机自启项 '{name}' 吗？\n\n"
            f"删除后该程序将不再开机自动运行。"
        ):
            return

        # 从系统中查找并删除启动项
        system_items = self.startup_manager.get_all_startup_items()
        found = False
        for sys_item in system_items:
            if (sys_item['name'] == name and sys_item['location'] == location):
                success, msg = self.startup_manager.remove_startup_item(sys_item)
                if success:
                    self.logger.info(f"已删除系统启动项: {name}")
                    found = True
                else:
                    self.logger.warning(f"删除系统启动项失败: {msg}")
                    messagebox.showerror("删除失败", msg)
                    return
                break

        # 同时在数据库中标记为已删除（如果有记录）
        recorded_items = self.db.get_all_recorded_startup_items()
        for r in recorded_items:
            if r['name'].lower() == name.lower():
                self.db.mark_startup_removed(r['id'])

        self.refresh_startup_list()

        if found:
            self.set_status(f"已删除开机自启项: {name}")
            messagebox.showinfo("成功",
                f"已删除开机自启项: {name}\n\n"
                f"注意：部分更改可能需要重启电脑才能生效"
            )
        else:
            self.set_status(f"未找到系统启动项: {name}")
            messagebox.showinfo("提示",
                f"未在系统中找到启动项: {name}\n\n"
                f"该启动项可能已被手动删除"
            )
    
    def refresh_logs(self):
        """刷新日志"""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        try:
            limit = int(self.log_limit_var.get())
        except (ValueError, TypeError):
            limit = 100
        
        logs = self.db.get_logs(limit=limit)
        for log in logs:
            status_icon = '✅' if log['status'] == 'success' else '❌'
            self.log_tree.insert('', END, values=(
                log['timestamp'][:19] if log['timestamp'] else '-',
                log.get('app_name', 'N/A'),
                log['action'],
                f"{status_icon} {log['status']}",
                log['message'] or '-'
            ))
    
    def _check_c_drive_apps(self, apps):
        """
        统一的 C 盘路径检查方法

        Args:
            apps: 应用列表，每个应用需包含 name 和 base_install_path 字段

        Returns:
            True 表示可以继续安装，False 表示需要停止/跳转
        """
        c_drive_apps = [
            app for app in apps
            if app.get('base_install_path') and app['base_install_path'].lower().startswith('c:')
        ]
        
        if not c_drive_apps:
            return True
        
        app_names = '\n'.join([f"  • {app['name']} ({app['base_install_path']})" for app in c_drive_apps])
        message = (
            f"以下 {len(c_drive_apps)} 个应用的安装路径在C盘：\n\n"
            f"{app_names}\n\n"
            f"是否需要更换到其他盘？\n\n"
            f"点击'是'跳转到设置页面修改路径\n"
            f"点击'否'继续在C盘安装\n"
            f"点击'取消'放弃安装"
        )
        
        result = messagebox.askyesnocancel("路径提示", message)
        
        if result is None:
            return False
        elif result:
            self.notebook.select(3)
            return False
        
        return True
    
    def batch_install(self):
        """批量安装"""
        apps = self.db.get_all_applications(status='待安装')
        if not apps:
            messagebox.showinfo("提示", "没有待安装的应用")
            return
        
        # 检查是否有应用安装在C盘
        if not self._check_c_drive_apps(apps):
            return
        
        if messagebox.askyesno("确认安装", f"确定要批量安装 {len(apps)} 个应用吗？"):
            # 在新线程中执行安装
            thread = threading.Thread(target=self._do_batch_install, args=(apps,))
            thread.daemon = True
            thread.start()
    
    def _do_batch_install(self, apps):
        """执行批量安装（在后台线程）"""
        total = len(apps)
        app_ids = [app['id'] for app in apps]
        
        self.root.after(0, lambda: self.install_progress.config(maximum=total, value=0))
        
        # 进度回调（线程安全，通过 root.after 调度到主线程）
        def _safe_gui_update(func, *args, **kwargs):
            """安全的 GUI 更新（通过主线程调度）"""
            try:
                if hasattr(self, 'root') and self.root and self.root.winfo_exists():
                    self.root.after(0, lambda: func(*args, **kwargs))
            except (tk.TclError, AttributeError):
                pass  # 窗口已销毁或正在销毁，忽略
        
        def progress_callback(current, total, app_name, success):
            _safe_gui_update(self.install_status_label.config, {'text': f"[{current}/{total}] 正在安装 {app_name}..."})
            _safe_gui_update(self.install_progress.config, {'value': current})
            result_icon = '✅' if success else '❌'
            _safe_gui_update(self.log_to_install, f"[{current}/{total}] {app_name} {result_icon}\n")
        
        # 执行批量安装
        stats = self.installer.batch_install(app_ids, progress_callback)
        
        # 完成
        success_count = stats['success']
        failed_count = stats['failed']
        reboot_required = stats.get('reboot_required', [])
        
        self.root.after(0, self.install_status_label.config, {'text': f"安装完成! {success_count} 成功，{failed_count} 失败"})
        self.root.after(0, self.refresh_app_list)
        self.root.after(0, self.refresh_pending_list)
        
        # 处理需要重启的应用
        if reboot_required:
            self.root.after(0, self._show_reboot_dialog, reboot_required)
        else:
            self.root.after(0, messagebox.showinfo, "完成", f"批量安装完成!\n\n成功: {success_count}\n失败: {failed_count}")
    
    def install_selected(self):
        """安装选中的多个应用"""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要安装的应用（可按住 Ctrl 多选）")
            return

        # 收集所有选中应用的信息
        selected_apps = []
        for item_id in selection:
            item = self.pending_tree.item(item_id)
            app_id = int(item['values'][0])
            app = self.db.get_application(app_id)
            if app:
                selected_apps.append(app)

        if not selected_apps:
            messagebox.showerror("错误", "无法获取选中应用的信息")
            return

        # 检查是否有应用安装在C盘
        if not self._check_c_drive_apps(selected_apps):
            return

        # 显示安装确认
        app_names = '\n'.join([f"  • {app['name']}" for app in selected_apps])
        if not messagebox.askyesno(
            "确认安装",
            f"确定要安装以下 {len(selected_apps)} 个应用吗？\n\n{app_names}"
        ):
            return

        # 在新线程中执行批量安装
        thread = threading.Thread(target=self._do_install_selected, args=(selected_apps,))
        thread.daemon = True
        thread.start()

    def _do_install_selected(self, selected_apps):
        """执行选中应用的批量安装（在后台线程）"""
        total = len(selected_apps)
        app_ids = [app['id'] for app in selected_apps]

        self.root.after(0, self.install_progress.configure, {'maximum': total, 'value': 0})
        self.root.after(0, self.install_log.delete, '1.0', END)
        self.root.after(0, self.log_to_install, f"开始安装选中的 {total} 个应用...\n{'='*40}\n")

        # 安全的 GUI 更新（线程安全，通过 root.after 调度到主线程）
        def _safe_gui_update(func, *args, **kwargs):
            try:
                if hasattr(self, 'root') and self.root and self.root.winfo_exists():
                    self.root.after(0, lambda: func(*args, **kwargs))
            except (tk.TclError, AttributeError):
                pass

        def progress_callback(current, total, app_name, success):
            _safe_gui_update(self.install_status_label.config, {'text': f"[{current}/{total}] 正在安装 {app_name}..."})
            _safe_gui_update(self.install_progress.config, {'value': current})
            result_icon = '✅' if success else '❌'
            _safe_gui_update(self.log_to_install, f"[{current}/{total}] {app_name} {result_icon}\n")

        stats = self.installer.batch_install(app_ids, progress_callback)

        success_count = stats['success']
        failed_count = stats['failed']
        reboot_required = stats.get('reboot_required', [])

        self.root.after(0, self.install_status_label.config, {'text': f"安装完成! {success_count} 成功，{failed_count} 失败"})
        self.root.after(0, self.refresh_app_list)
        self.root.after(0, self.refresh_pending_list)

        if reboot_required:
            self.root.after(0, self._show_reboot_dialog, reboot_required)
        else:
            self.root.after(0, messagebox.showinfo, "完成", f"选中应用安装完成!\n\n成功: {success_count}\n失败: {failed_count}")

    def _show_reboot_dialog(self, reboot_required):
        """显示重启对话框"""
        # 构建消息
        app_names = '\n'.join([f"  • {app['name']}" for app in reboot_required])
        message = f"以下应用需要重启电脑才能完成安装：\n\n{app_names}\n\n是否现在重启电脑？"
        
        # 自定义对话框
        dialog = Toplevel(self.root)
        dialog.title("需要重启")
        dialog.geometry("450x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 图标和标题
        frame = Frame(dialog, padx=20, pady=20)
        frame.pack(fill=BOTH, expand=True)
        
        Label(
            frame,
            text="⚠️ 需要重启电脑",
            font=('微软雅黑', 14, 'bold'),
            fg='#ff6b00'
        ).pack(pady=(0, 10))
        
        Label(
            frame,
            text=message,
            font=('微软雅黑', 10),
            justify=LEFT,
            wraplength=400
        ).pack(pady=10)
        
        Label(
            frame,
            text='点击"立即重启"将在 10 秒后重启系统',
            font=('微软雅黑', 9),
            fg='#666'
        ).pack(pady=(10, 0))
        
        # 按钮
        btn_frame = Frame(frame)
        btn_frame.pack(pady=20)
        
        def do_reboot():
            dialog.destroy()
            # 显示倒计时
            countdown_dialog = Toplevel(self.root)
            countdown_dialog.title("正在重启")
            countdown_dialog.geometry("300x150")
            countdown_dialog.transient(self.root)
            
            countdown_label = Label(
                countdown_dialog,
                text="系统将在 10 秒后重启...",
                font=('微软雅黑', 12),
                pady=30
            )
            countdown_label.pack()
            
            cancel_btn = ttk.Button(
                countdown_dialog,
                text="取消重启",
                command=lambda: [countdown_dialog.destroy(), self._cancel_reboot()]
            )
            cancel_btn.pack()
            
            # 发送重启命令
            from installer import reboot_system
            reboot_system(10)
            
            self.logger.info('用户选择立即重启电脑')
        
        def do_later():
            dialog.destroy()
            messagebox.showinfo(
                "提示",
                "请稍后手动重启电脑以完成这些应用的安装。"
            )
            self.logger.info('用户选择稍后手动重启')
        
        ttk.Button(
            btn_frame,
            text="立即重启",
            command=do_reboot,
            width=15
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="稍后手动重启",
            command=do_later,
            width=15
        ).pack(side=LEFT, padx=5)
    
    def _cancel_reboot(self):
        """取消重启"""
        os.system('shutdown /a')  # 取消重启命令
        messagebox.showinfo("已取消", "重启已取消")
        self.logger.info('重启已取消')
    
    def _do_install_single(self, app):
        """执行单个安装"""
        self.root.after(0, self.install_status_label.config, {'text': f"正在安装 {app['name']}..."})
        self.root.after(0, self.log_to_install, f"\n开始安装: {app['name']}\n")
        
        success, message = self.installer.install(
            app['id'],
            app['package_path'],
            app['install_args'],
            app['final_install_path']
        )
        
        result_icon = '✅' if success else '❌'
        self.root.after(0, self.log_to_install, f"{result_icon} {message}\n")
        self.root.after(0, self.install_status_label.config, {'text': "安装完成"})
        self.root.after(0, self.refresh_app_list)
        self.root.after(0, self.refresh_pending_list)
        
        # 检查是否需要重启
        if success and ('需要重启' in message or 'reboot' in message.lower()):
            if messagebox.askyesno("需要重启", f"{app['name']} 需要重启电脑才能完成安装。\n\n是否现在重启？"):
                from installer import reboot_system
                reboot_system(10)
                messagebox.showinfo("提示", "系统将在 10 秒后重启")
        elif success:
            self.root.after(0, messagebox.showinfo, "成功", f"{app['name']} 安装成功!")
        else:
            self.root.after(0, messagebox.showerror, "失败", f"{app['name']} 安装失败:\n{message}")
    
    def uninstall_selected(self):
        """卸载选中的应用"""
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要卸载的应用")
            return
        
        item = self.installed_tree.item(selection[0])
        app_id = int(item['values'][0])
        app = self.db.get_application(app_id)
        
        if not app['uninstall_available']:
            messagebox.showwarning("提示", f"{app['name']} 无法自动卸载，请手动卸载")
            return
        
        if messagebox.askyesno("确认卸载", f"确定要卸载 '{app['name']}' 吗？"):
            success, message = self.uninstaller.uninstall(app_id, app['name'])
            
            if success:
                messagebox.showinfo("成功", f"{app['name']} 卸载成功!")
            else:
                messagebox.showerror("失败", f"{app['name']} 卸载失败:\n{message}")
            
            self.refresh_app_list()
            self.refresh_installed_list()
    
    def refresh_uninstall_status(self):
        """刷新卸载状态"""
        self.set_status("正在刷新卸载状态...")
        count = self.uninstaller.refresh_all_uninstall_status()
        self.refresh_installed_list()
        self.set_status(f"已刷新 {count} 个应用的卸载状态")
        messagebox.showinfo("完成", f"已刷新 {count} 个应用的卸载状态")
    
    def clear_log_display(self):
        """清空日志显示"""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
    
    def log_to_install(self, message):
        """输出到安装日志框"""
        self.install_log.insert(END, message)
        self.install_log.see(END)
    
    def browse_base_path(self):
        """浏览基础路径"""
        path = filedialog.askdirectory(title="选择默认安装路径")
        if path:
            self.base_path_var.set(path)
    
    def save_base_path(self):
        """保存基础路径"""
        new_path = self.base_path_var.get()
        self.config.set_default_base_path(new_path)
        self.set_status(f"默认安装路径已更新: {new_path}")
        messagebox.showinfo("成功", "默认安装路径已保存")
    
    def retry_install(self):
        """重试安装选中的应用"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择要重试安装的应用")
            return
        
        # 获取选中项的应用信息
        item = self.app_tree.item(selected[0])
        app_id = item['values'][0]
        app_name = item['values'][1]
        
        # 检查应用状态
        app = self.db.get_application(app_id)
        if not app:
            messagebox.showerror("错误", "应用不存在")
            return
        
        if app['status'] == '已安装':
            messagebox.showinfo("提示", f"{app_name} 已经安装成功，无需重试")
            return
        
        # 确认重试安装
        if not messagebox.askyesno("确认", f"确定要重试安装 {app_name} 吗？"):
            return
        
        # 检查安装路径是否为C盘
        install_path = app['base_install_path']
        if install_path and install_path.lower().startswith('c:'):
            # 询问用户是否更换到其他盘
            result = messagebox.askyesnocancel(
                "路径提示", 
                f"{app_name} 的安装路径在C盘({install_path})，\n是否需要更换到其他盘？\n\n点击'是'跳转到设置页面修改路径\n点击'否'继续在C盘安装\n点击'取消'放弃安装"
            )
            
            if result is None:  # 用户点击取消
                return
            elif result:  # 用户点击是，跳转到设置页面
                self.notebook.select(3)  # 设置选项卡索引为3
                return
        
        # 执行重试安装（在后台线程中，避免阻塞 GUI）
        import threading
        thread = threading.Thread(target=self._do_install_single, args=(app,))
        thread.daemon = True
        thread.start()
        self.set_status(f"正在安装 {app_name}...")
    
    def open_install_folder(self):
        """打开选中应用的安装文件夹"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择要打开安装文件夹的应用")
            return
        
        # 获取选中项的应用信息
        item = self.app_tree.item(selected[0])
        app_id = item['values'][0]
        app_name = item['values'][1]
        
        # 获取应用信息
        app = self.db.get_application(app_id)
        if not app:
            messagebox.showerror("错误", "应用不存在")
            return
        
        # 获取安装路径
        install_path = os.path.join(app['base_install_path'], app['folder_name'])
        
        # 检查路径是否存在
        if not os.path.exists(install_path):
            messagebox.showwarning("提示", f"{app_name} 的安装文件夹不存在:\n{install_path}")
            return
        
        # 打开文件夹
        try:
            os.startfile(install_path)
            self.set_status(f"已打开 {app_name} 的安装文件夹")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹:\n{str(e)}")
    
    def scan_packages(self):
        """扫描 packages 目录并自动添加安装包"""
        packages_dir = self.workspace.packages_dir

        if not packages_dir.exists():
            messagebox.showwarning("提示",
                f"安装包目录不存在：\n{packages_dir}\n\n"
                f"请先创建该目录并将安装包放入其中"
            )
            return

        supported = {'.exe', '.msi', '.bat'}
        installer_files = []
        
        # 1. 扫描 packages 根目录下的文件
        for f in packages_dir.iterdir():
            if f.is_file() and f.suffix.lower() in supported:
                installer_files.append(f)
        
        # 2. 扫描一级子目录，每个子目录只取一个主安装文件
        for subdir in packages_dir.iterdir():
            if subdir.is_dir():
                # 优先级：setup.exe > install*.exe > *.exe > *.msi > *.bat
                priority_names = ['setup.exe', 'install.exe']
                found = None
                
                # 先找优先名称
                for name in priority_names:
                    candidate = subdir / name
                    if candidate.exists() and candidate.suffix.lower() in supported:
                        found = candidate
                        break
                
                # 没找到优先名称，找第一个 .exe
                if not found:
                    for f in sorted(subdir.iterdir()):
                        if f.is_file() and f.suffix.lower() == '.exe':
                            found = f
                            break
                
                # 没有 .exe，找 .msi 或 .bat
                if not found:
                    for f in sorted(subdir.iterdir()):
                        if f.is_file() and f.suffix.lower() in {'.msi', '.bat'}:
                            found = f
                            break
                
                if found:
                    installer_files.append(found)
        
        installer_files = sorted(set(installer_files))

        if not installer_files:
            messagebox.showinfo("扫描结果",
                f"在以下目录中未找到安装包：\n{packages_dir}\n\n"
                f"（已扫描根目录及一级子目录）"
            )
            return

        result = messagebox.askyesno("确认扫描",
            f"扫描到 {len(installer_files)} 个安装包：\n\n" +
            "\n".join(f"  • {f.relative_to(packages_dir.parent)}" for f in installer_files[:20]) +
            (f"\n  • ... 还有 {len(installer_files) - 20} 个" if len(installer_files) > 20 else "") +
            f"\n\n是否自动添加这些安装包到应用列表？"
        )
        if not result:
            return

        thread = threading.Thread(target=self._do_scan_packages, args=(installer_files,))
        thread.daemon = True
        thread.start()
        self.set_status(f"正在扫描添加 {len(installer_files)} 个安装包...")

    def _do_scan_packages(self, installer_files):
        """在后台线程中执行扫描添加"""
        imported = 0
        skipped = 0
        failed = 0
        details = []
        name_seen = {}  # 名称 -> 路径映射，用于检测同名不同路径

        for file_path in installer_files:
            try:
                package_rel = self.workspace.to_relative_path(file_path)
                existing = self.db.get_application_by_path(package_rel)
                if existing:
                    details.append(f"⏭️ [{file_path.name}] 已在列表中 (ID={existing['id']})")
                    skipped += 1
                    continue

                name = self._extract_name_from_filename(file_path.stem)

                install_args = None
                try:
                    detect_result = self.param_detector.detect_params(
                        str(file_path), name
                    )
                    if detect_result:
                        if isinstance(detect_result, tuple):
                            install_args = detect_result[0]
                        else:
                            install_args = detect_result
                except Exception:
                    pass

                base_path = self.config.get_default_base_path()
                folder_name = name.replace(' ', '')
                version = ''

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
                    details.append(f"⚠️ [{file_path.name}] → {name} (ID={app_id}) 与已有软件同名")
                else:
                    details.append(f"✅ [{file_path.name}] → {name} (ID={app_id})")
                name_seen[name] = package_rel

                self.logger.info(f'扫描添加应用: {name} (ID={app_id})')
                imported += 1

            except Exception as e:
                details.append(f"❌ [{file_path.name}] 失败: {e}")
                self.logger.error(f'扫描添加失败: {file_path.name} - {e}')
                failed += 1

        self.root.after(0, self.refresh_app_list)

        summary = (
            f"📊 扫描完成\n\n"
            f"新增: {imported}\n"
            f"已存在: {skipped}\n"
            f"失败: {failed}\n\n"
            + "\n".join(details)
        )
        self.root.after(0, messagebox.showinfo, "扫描完成", summary)
        self.root.after(0, self.set_status, f"扫描完成：新增 {imported} 个")

    def _extract_name_from_filename(self, stem: str) -> str:
        """从文件名中提取干净的软件名称"""
        import re
        name = stem.strip()
        name = re.sub(r'[_\-]+', ' ', name)
        name = re.sub(r'\s*\d+[\d\.]+\s*$', '', name)
        name = re.sub(r'\s*(x64|x86|win64|win32|windows|setup|installer)\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^(setup|install|installer)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip()
        return name.title() if name else stem

    def apply_base_path_to_all(self):
        """批量应用基础路径"""
        if messagebox.askyesno("确认", "确定要将此路径应用到所有应用吗？"):
            new_path = self.base_path_var.get()
            self.db.batch_update_base_path(new_path)
            self.refresh_app_list()
            self.set_status("已批量更新所有应用的安装路径")
            messagebox.showinfo("成功", "已批量更新所有应用的安装路径")
    
    def _show_activation_dialog(self):
        """显示续期激活对话框"""
        dialog = Toplevel(self.root)
        dialog.title("续期激活")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill=BOTH, expand=True)
        
        Label(
            content,
            text="请输入激活码",
            font=('微软雅黑', 12, 'bold')
        ).pack(pady=(0, 5))
        
        Label(
            content,
            text="如需续期，请联系开发者获取激活码\n只是向着",
            font=('微软雅黑', 9),
            fg='#666'
        ).pack(pady=(0, 15))
        
        input_frame = ttk.Frame(content)
        input_frame.pack(fill=X)
        
        code_var = StringVar()
        ttk.Entry(
            input_frame,
            textvariable=code_var,
            font=('微软雅黑', 11),
            width=30
        ).pack()
        
        def do_activate():
            code = code_var.get().strip()
            if not code:
                messagebox.showwarning("提示", "请输入激活码", parent=dialog)
                return
            
            config_path = self.workspace.data_dir / 'config.json'
            success, msg = activate(code, config_path)
            
            if success:
                messagebox.showinfo("激活成功", msg, parent=dialog)
                dialog.destroy()
                self.set_status("激活成功")
            else:
                messagebox.showerror("激活失败", msg, parent=dialog)
        
        ttk.Button(
            content,
            text="立即激活",
            command=do_activate
        ).pack(pady=(15, 0))
    
    def set_status(self, message):
        """设置状态栏消息"""
        self.statusbar.config(text=message)
        self.logger.info(message)
    
    def on_closing(self):
        """窗口关闭事件"""
        if messagebox.askokcancel("退出", "确定要退出程序吗？"):
            self.logger.info("GUI界面关闭")
            if self.db:
                self.db.close()
            self.root.destroy()
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()


# 添加应用对话框（将在下一个文件中实现）
class AddAppDialog:
    """添加应用对话框"""
    
    def __init__(self, parent, main_window):
        self.main_window = main_window
        self.result = None
        
        self.dialog = Toplevel(parent)
        self.dialog.title("添加应用")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """创建对话框组件"""
        # 主框架
        frame = Frame(self.dialog, padx=20, pady=20)
        frame.pack(fill=BOTH, expand=True)
        
        # 安装包路径
        Label(frame, text="安装包路径:", font=('微软雅黑', 10)).grid(row=0, column=0, sticky=W, pady=5)
        
        path_frame = Frame(frame)
        path_frame.grid(row=0, column=1, sticky=EW, pady=5)
        
        self.package_path_var = StringVar()
        Entry(path_frame, textvariable=self.package_path_var, font=('微软雅黑', 10)).pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="浏览...", command=self.browse_package).pack(side=LEFT)
        
        # 软件名称
        Label(frame, text="软件名称:", font=('微软雅黑', 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.name_var = StringVar()
        Entry(frame, textvariable=self.name_var, font=('微软雅黑', 10)).grid(row=1, column=1, sticky=EW, pady=5)
        
        # 安装文件夹名
        Label(frame, text="安装文件夹名:", font=('微软雅黑', 10)).grid(row=2, column=0, sticky=W, pady=5)
        self.folder_var = StringVar()
        Entry(frame, textvariable=self.folder_var, font=('微软雅黑', 10)).grid(row=2, column=1, sticky=EW, pady=5)
        
        # 版本号
        Label(frame, text="版本号(可选):", font=('微软雅黑', 10)).grid(row=3, column=0, sticky=W, pady=5)
        self.version_var = StringVar()
        Entry(frame, textvariable=self.version_var, font=('微软雅黑', 10)).grid(row=3, column=1, sticky=EW, pady=5)
        
        # 分隔线
        ttk.Separator(frame, orient=HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky=EW, pady=15)
        
        # 检测状态
        self.detect_label = Label(frame, text="", font=('微软雅黑', 9), fg='#666', wraplength=500, justify=LEFT)
        self.detect_label.grid(row=5, column=0, columnspan=2, sticky=W, pady=5)
        
        # 静默参数
        Label(frame, text="静默参数:", font=('微软雅黑', 10)).grid(row=6, column=0, sticky=W, pady=5)
        self.args_var = StringVar()
        Entry(frame, textvariable=self.args_var, font=('微软雅黑', 10)).grid(row=6, column=1, sticky=EW, pady=5)
        
        ttk.Button(frame, text="🔍 自动检测参数", command=self.detect_params).grid(row=7, column=1, sticky=W, pady=5)
        
        # 是否复制安装包
        self.copy_var = BooleanVar(value=False)
        Checkbutton(frame, text="复制安装包到本地（勾选后占用双倍磁盘空间）", variable=self.copy_var, font=('微软雅黑', 9)).grid(row=8, column=1, sticky=W, pady=10)
        
        # 按钮
        btn_frame = Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="确定", command=self.ok, width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.cancel, width=15).pack(side=LEFT, padx=5)
        
        frame.columnconfigure(1, weight=1)
    
    def browse_package(self):
        """浏览安装包"""
        filename = filedialog.askopenfilename(
            title="选择安装包",
            filetypes=[("安装包", "*.exe *.msi"), ("所有文件", "*.*")]
        )
        if filename:
            self.package_path_var.set(filename)
            # 自动从文件名提取软件名
            name = Path(filename).stem
            if not self.name_var.get():
                self.name_var.set(name)
            if not self.folder_var.get():
                self.folder_var.set(name)
    
    def detect_params(self):
        """检测参数"""
        package_path = self.package_path_var.get()
        name = self.name_var.get()
        
        if not package_path:
            messagebox.showwarning("提示", "请先选择安装包")
            return
        
        self.detect_label.config(text="正在分析软件信息...")
        self.dialog.update()
        
        args, source = self.main_window.param_detector.detect_params(package_path, name)
        self.args_var.set(args)
        self.detect_label.config(text=f"✓ 检测完成! 参数来源: {source}")
    
    def ok(self):
        """确定"""
        package_path = self.package_path_var.get()
        name = self.name_var.get()
        folder = self.folder_var.get()
        version = self.version_var.get()
        args = self.args_var.get()
        
        if not package_path or not name or not folder:
            messagebox.showwarning("提示", "请填写必填项")
            return
        
        if not Path(package_path).exists():
            messagebox.showerror("错误", "安装包文件不存在")
            return
        
        # 复制安装包
        if self.copy_var.get():
            try:
                package_path = self.main_window.workspace.copy_package(package_path)
            except Exception as e:
                messagebox.showwarning("警告", f"复制安装包失败，将使用原始路径:\n{e}")
        
        # 添加到数据库
        app_id = self.main_window.db.add_application(
            name=name,
            package_path=package_path,
            folder_name=folder,
            base_install_path=self.main_window.config.get_default_base_path(),
            version=version,
            install_args=args
        )
        
        self.result = {'id': app_id, 'name': name}
        self.dialog.destroy()
    
    def cancel(self):
        """取消"""
        self.dialog.destroy()


class EditAppDialog:
    """编辑应用对话框"""
    
    def __init__(self, parent, main_window, app_id):
        self.main_window = main_window
        self.app_id = app_id
        self.result = None
        
        # 加载应用信息
        self.app = main_window.db.get_application(app_id)
        if not self.app:
            messagebox.showerror("错误", "应用不存在")
            return
        
        self.dialog = Toplevel(parent)
        self.dialog.title(f"编辑应用 - {self.app['name']}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """创建对话框组件"""
        frame = Frame(self.dialog, padx=20, pady=20)
        frame.pack(fill=BOTH, expand=True)
        
        # 显示基本信息
        Label(frame, text=f"应用名称: {self.app['name']}", font=('微软雅黑', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky=W, pady=10)
        
        # 静默参数
        Label(frame, text="静默参数:", font=('微软雅黑', 10)).grid(row=1, column=0, sticky=W, pady=5)
        self.args_var = StringVar(value=self.app['install_args'])
        Entry(frame, textvariable=self.args_var, font=('微软雅黑', 10), width=50).grid(row=1, column=1, sticky=EW, pady=5)
        
        # 基础路径
        Label(frame, text="基础路径:", font=('微软雅黑', 10)).grid(row=2, column=0, sticky=W, pady=5)
        self.base_path_var = StringVar(value=self.app['base_install_path'])
        Entry(frame, textvariable=self.base_path_var, font=('微软雅黑', 10), width=50).grid(row=2, column=1, sticky=EW, pady=5)
        
        # 文件夹名
        Label(frame, text="文件夹名:", font=('微软雅黑', 10)).grid(row=3, column=0, sticky=W, pady=5)
        self.folder_var = StringVar(value=self.app['folder_name'])
        Entry(frame, textvariable=self.folder_var, font=('微软雅黑', 10), width=50).grid(row=3, column=1, sticky=EW, pady=5)
        
        # 最终路径预览
        Label(frame, text="最终路径:", font=('微软雅黑', 10)).grid(row=4, column=0, sticky=W, pady=5)
        self.final_path_label = Label(frame, text="", font=('微软雅黑', 9), fg='#666')
        self.final_path_label.grid(row=4, column=1, sticky=W, pady=5)
        
        # 绑定更新事件
        self.base_path_var.trace('w', self.update_final_path)
        self.folder_var.trace('w', self.update_final_path)
        self.update_final_path()
        
        # 按钮
        btn_frame = Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=30)
        
        ttk.Button(btn_frame, text="保存", command=self.save, width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.cancel, width=15).pack(side=LEFT, padx=5)
        
        frame.columnconfigure(1, weight=1)
    
    def update_final_path(self, *args):
        """更新最终路径预览"""
        final = str(Path(self.base_path_var.get()) / self.folder_var.get())
        self.final_path_label.config(text=final)
    
    def save(self):
        """保存"""
        self.main_window.db.update_application(
            self.app_id,
            install_args=self.args_var.get(),
            base_install_path=self.base_path_var.get(),
            folder_name=self.folder_var.get()
        )
        
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """取消"""
        self.dialog.destroy()


def main():
    """程序入口"""
    # 单实例锁：防止重复打开多个 GUI 窗口
    try:
        import ctypes
        mutex_name = "AppInstallerGUI_SingleInstance"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(mutex)
            messagebox.showwarning("提示", "程序已在运行中，无需重复打开")
            sys.exit(0)
    except Exception:
        pass  # 非 Windows 环境或权限不足时跳过检查

    try:
        app = AppInstallerGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("错误", f"程序启动失败:\n{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

