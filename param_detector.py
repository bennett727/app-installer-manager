# -*- coding: utf-8 -*-
"""
静默参数检测模块
自动检测Windows安装包的静默安装参数
"""

from pathlib import Path
from typing import Tuple, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class ParamDetector:
    """静默参数检测器"""
    
    # 常见软件的静默参数库
    KNOWN_SOFTWARE = {
        # === Adobe 系列（需在通用 adobe/reader 之前匹配） ===
        'adobe reader': '/sPB /rs',
        'acrobat reader': '/sPB /rs',
        'adobe acrobat': '/sPB /rs',
        'flash': '-silent',
        'adobe': '/i',
        'reader': '/i',
        # === 浏览器 ===
        'chrome': '/silent /install',
        'google chrome': '/silent /install',
        'firefox': '/S',
        'edge': '/silent',
        'microsoft edge': '/silent',
        'ie': '/quiet',
        'iexplore': '/quiet',
        # === 压缩工具 ===
        '7-zip': '/S',
        '7zip': '/S',
        'winrar': '/s',
        'bandizip': '/S',
        '2345': '/S',
        # === 开发工具 ===
        'vscode': '/VERYSILENT /MERGETASKS=!runcode',
        'git': '/VERYSILENT',
        'python': '/quiet InstallAllUsers=1 PrependPath=1',
        'notepad++': '/S',
        'putty': '/VERYSILENT',
        # === 运行环境 ===
        'jre': '/s',
        'jdk': '/s',
        # === 通讯工具 ===
        'rtx': '/S',
        '腾讯通': '/S',
        'zoom': '/silent',
        'teamviewer': '/S',
        'anydesk': '/S',
        'discord': '/S',
        'steam': '/S',
        'vlc': '/S',
        # === 办公软件 ===
        'office': '',  # Office 需要特殊处理，见 build_office_install_command
        'microsoft office': '',  # Office 需要特殊处理，见 build_office_install_command
        'office_2016': '',  # Office 需要特殊处理
        'office_2019': '',  # Office 需要特殊处理
        'office_2021': '',  # Office 需要特殊处理
        'wps': '/silent',
        # === 安全软件 ===
        '火绒': '/S',
        'huorong': '/S',
        '360': '/S',
        '亚信': '/S /norestart',
        'aved': '/S /norestart',
        'avdf': '/S /norestart',
        'aishesm': '/S /norestart',
        'lva': '/S',
        '民航': '/S',
        '安全助手': '/S',
        '卡巴斯基': '/s',
        'kaspersky': '/s',
        '迈克菲': '/qn',
        'mcafee': '/qn',
        # === 下载工具 ===
        '迅雷': '/S',
        'idm': '/silent',
        # === 输入法 ===
        '搜狗': '/S',
        'sogou': '/S',
        'qq输入法': '/S',
    }
    
    # 打包工具特征和对应参数
    INSTALLER_SIGNATURES = {
        'NSIS': {
            'signature': [b'Nullsoft', b'NSIS'],
            'params': '/S',
            'dir_param': '/D='
        },
        'Inno Setup': {
            'signature': [b'Inno Setup'],
            'params': '/VERYSILENT /NORESTART',
            'dir_param': '/DIR='
        },
        'InstallShield': {
            'signature': [b'InstallShield'],
            'params': '/s /v/qn',
            'dir_param': 'INSTALLDIR='
        }
    }
    
    def __init__(self, database=None):
        """
        初始化参数检测器
        
        Args:
            database: Database实例，用于缓存查询
        """
        self.db = database
        self._file_content_cache = {}  # 文件内容缓存 {path: bytes}
        self._installer_type_cache = {}  # 打包工具类型缓存 {path: str}
    
    def detect_params(self, package_path: str, software_name: str = '') -> Tuple[str, str]:
        """
        检测静默安装参数（主入口）
        
        Args:
            package_path: 安装包文件路径
            software_name: 软件名称（可选，用于缓存查询和网络搜索）
        
        Returns:
            (install_args, source) 元组
            install_args: 检测到的参数
            source: 参数来源（缓存/网络/本地库/识别/默认）
        """
        package_path = Path(package_path)
        
        if not package_path.exists():
            return '', 'error'
        
        # 1. 查询缓存
        if self.db and software_name:
            cached = self.db.get_cached_params(software_name)
            if cached:
                return cached, '缓存'
        
        # 2. 网络查询（静默处理，不阻塞）
        if software_name:
            network_result = self._query_network(software_name)
            if network_result:
                # 缓存结果
                if self.db:
                    self.db.cache_params(software_name, network_result, '网络')
                return network_result, '网络'
        
        # 3. 本地参数库匹配
        local_result = self._match_local_database(package_path.name, software_name)
        if local_result:
            if self.db and software_name:
                self.db.cache_params(software_name, local_result, '本地库')
            return local_result, '本地库'
        
        # 4. 文件类型判断
        if package_path.suffix.lower() == '.msi':
            params = '/qn /norestart'
            return params, 'MSI标准'
        
        # 5. 打包工具识别（仅.exe）
        if package_path.suffix.lower() == '.exe':
            detected = self._detect_installer_type(package_path)
            if detected:
                if self.db and software_name:
                    self.db.cache_params(software_name, detected, '工具识别')
                return detected, '工具识别'
        
        # 6. 默认参数
        default_params = '/S'
        return default_params, '默认'
    
    def _query_network(self, software_name: str, timeout: int = 3) -> Optional[str]:
        """
        从网络查询静默参数（静默处理，超时自动失败）
        
        Args:
            software_name: 软件名称
            timeout: 超时时间（秒）
        
        Returns:
            检测到的参数，失败返回None
        """
        # 如果没有安装requests库，直接返回None（离线模式）
        if not HAS_REQUESTS:
            return None
            
        try:
            # 方案1: 尝试查询 silentinstallhq.com 的模拟
            # 注意：实际使用时需要根据真实API调整
            # 这里仅作示例，实际可能需要爬虫或API
            
            # 简化处理：直接返回None，避免网络依赖
            # 实际部署时可以实现真实的网络查询
            return None
            
        except Exception:
            # 网络查询失败，静默处理
            return None
    
    def _match_local_database(self, filename: str, software_name: str) -> Optional[str]:
        """
        匹配本地参数库（优先匹配更长、更具体的关键词）
        
        Args:
            filename: 文件名
            software_name: 软件名称
        
        Returns:
            匹配到的参数，未匹配返回None
        """
        search_text = f"{filename} {software_name}".lower()

        # 找出所有匹配的关键词，选取最长的（最具体）那个
        matched_keyword = None
        for keyword in self.KNOWN_SOFTWARE:
            if keyword in search_text:
                if matched_keyword is None or len(keyword) > len(matched_keyword):
                    matched_keyword = keyword

        if matched_keyword:
            return self.KNOWN_SOFTWARE[matched_keyword]
        return None
    
    def _detect_installer_type(self, exe_path: Path) -> Optional[str]:
        """
        检测.exe安装包的打包工具类型（带缓存）
        
        Args:
            exe_path: .exe文件路径
        
        Returns:
            检测到的参数，未检测到返回None
        """
        # 检查缓存
        cache_key = str(exe_path)
        if cache_key in self._installer_type_cache:
            return self._installer_type_cache[cache_key]
        
        try:
            # 读取文件内容（使用缓存）
            content = self._get_file_content(exe_path, max_size=1024 * 1024)
            
            # 检测各种打包工具的特征
            for tool_name, tool_info in self.INSTALLER_SIGNATURES.items():
                for signature in tool_info['signature']:
                    if signature in content:
                        result = tool_info['params']
                        self._installer_type_cache[cache_key] = result
                        return result
            
            self._installer_type_cache[cache_key] = None
            return None
            
        except Exception:
            self._installer_type_cache[cache_key] = None
            return None
    
    def _get_file_content(self, file_path: str, max_size: int = 64 * 1024) -> bytes:
        """
        获取文件内容（带缓存）
        
        Args:
            file_path: 文件路径
            max_size: 最大读取字节数
        
        Returns:
            文件字节内容
        """
        cache_key = str(file_path)
        if cache_key in self._file_content_cache:
            return self._file_content_cache[cache_key]
        
        with open(file_path, 'rb') as f:
            content = f.read(max_size)
        
        self._file_content_cache[cache_key] = content
        return content
    
    def is_office_install(self, package_path: str, software_name: str = '') -> bool:
        """
        检测是否是 Office 安装包

        Args:
            package_path: 安装包路径
            software_name: 软件名称

        Returns:
            是否是 Office 安装包
        """
        search_text = f"{package_path} {Path(package_path).name} {software_name}".lower()
        office_keywords = ['office', 'office_2016', 'office_2019', 'office_2021', 'microsoft office']
        for keyword in office_keywords:
            if keyword in search_text:
                return True
        return False
    
    def build_office_install_command(self, package_path: str, target_dir: str = '', is_silent: bool = True) -> str:
        """
        构建 Office 安装命令

        Args:
            package_path: Office 安装包路径
            target_dir: 目标安装目录（Office 不支持命令行指定）
            is_silent: 是否静默安装（默认True）

        Returns:
            Office 安装命令
        """
        package_path = Path(package_path)
        parent_dir = package_path.parent
        setup_exe = parent_dir / 'setup.exe'

        if not setup_exe.exists():
            return f'"{package_path}"'

        if is_silent:
            return f'"{setup_exe}" /quiet'
        
        return f'"{setup_exe}"'

