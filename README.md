# 批量应用安装管理器

基于 Python 的 Windows 应用程序批量安装管理工具，支持静默安装、智能参数检测、应用管理和智能卸载。

## 核心功能

- **批量安装管理** — 一键批量安装多个应用程序
- **智能参数检测** — 自动检测静默安装参数（本地库 + 打包工具识别）
- **安装回退机制** — 静默安装失败自动回退到正常安装模式
- **智能卸载** — 读取注册表获取卸载信息，优先静默卸载
- **开机自启管理** — 检测、禁用、删除安装时添加的启动项
- **完整日志** — 记录所有安装/卸载操作，可追溯
- **完全本地运行** — 所有数据存储在本地，无需联网，不收集任何信息

## 系统要求

- Windows 7 及以上
- Python 3.8+（源码运行）/ 无需 Python（打包后的 exe）

## 快速开始

### 方式1：使用打包后的 exe（推荐）

1. 将 `AppInstaller.exe` 放在非系统保护目录（如 `D:\AppInstaller\`）
2. 双击运行，首次启动自动创建 `data/` 目录
3. 点击"添加应用"上传安装包即可使用

### 方式2：使用 Python 运行

```bash
pip install -r requirements.txt
python gui_main.py
```

## 项目结构

```
app_installer-main/
├── gui_main.py           # GUI 主程序（推荐使用）
├── app_installer.py      # CLI 命令行主程序
├── database.py           # SQLite 数据库操作
├── installer.py          # 安装执行逻辑
├── uninstaller.py        # 卸载执行逻辑
├── param_detector.py     # 静默参数检测
├── config.py             # 配置管理与激活系统
├── startup_manager.py    # 开机自启管理
├── logger.py             # 日志系统
├── convert_paths.py      # 路径转换工具
├── requirements.txt      # Python 依赖
├── build.bat             # 打包脚本
├── build_gui.bat         # GUI 打包脚本
├── start_gui.bat         # GUI 启动脚本
└── data/                 # 运行时数据（自动创建）
    ├── packages/         # 安装包存储
    ├── logs/             # 日志文件
    ├── app_manager.db    # SQLite 数据库
    └── config.json       # 配置文件
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `gui_main.py` | GUI 图形界面，包含应用管理、批量安装、卸载、开机自启、日志、设置等标签页 |
| `app_installer.py` | CLI 命令行界面，支持 add/list/install/install-all/uninstall/logs 等命令 |
| `database.py` | SQLite 数据库，管理 applications/install_logs/param_cache/startup_items 四张表 |
| `installer.py` | 安装执行器，支持静默安装回退、磁盘空间预检、开机自启跟踪 |
| `uninstaller.py` | 卸载器，通过读取注册表获取卸载命令，优先静默卸载 |
| `param_detector.py` | 参数检测器，按优先级：缓存→网络→本地库→打包工具识别→默认 |
| `config.py` | 配置管理 + 激活码系统 + 工作目录管理 |
| `startup_manager.py` | 开机自启管理，读取注册表和启动文件夹 |
| `logger.py` | 日志系统，支持控制台和文件输出，UTF-8 编码 |
| `convert_paths.py` | 数据库路径转换工具 |

## 参数检测原理

按以下优先级检测静默参数：

1. **缓存查询** — 检测过的软件直接使用缓存
2. **网络查询** — 查询在线参数数据库（3秒超时，实际为离线模式）
3. **本地参数库** — 匹配内置的常见软件参数（Chrome/Firefox/7-Zip/Notepad++ 等）
4. **打包工具识别** — 检测 NSIS/Inno Setup/InstallShield 特征
5. **MSI 标准** — .msi 文件使用 `/qn /norestart`
6. **默认参数** — 通用参数 `/S`

### 支持的打包工具

- **NSIS** — 参数 `/S`，目录参数 `/D=`
- **Inno Setup** — 参数 `/VERYSILENT /NORESTART`，目录参数 `/DIR=`
- **InstallShield** — 参数 `/s /v/qn`，目录参数 `INSTALLDIR=`
- **MSI** — 参数 `/qn /norestart`，目录参数 `INSTALLDIR=`
- **Office C2R** — 特殊处理，使用 `setup.exe /quiet`

## CLI 使用说明

### 基本命令

```bash
python app_installer.py add <package_path>      # 添加应用（交互式）
python app_installer.py list                     # 查看应用列表
python app_installer.py install <id>             # 安装单个应用
python app_installer.py install-all              # 批量安装所有待安装应用
python app_installer.py uninstall-list           # 显示已安装应用
python app_installer.py uninstall <id>           # 卸载应用
python app_installer.py scan-packages            # 扫描 packages 目录自动添加
python app_installer.py logs [app_name]          # 查看日志
python app_installer.py status                   # 查看状态统计
python app_installer.py edit <id>                # 编辑应用参数
python app_installer.py remove <id>              # 删除应用记录
```

### 路径管理

```bash
python app_installer.py set-base-path <path>     # 设置默认安装路径
python app_installer.py set-path <id> <path>     # 设置单个应用路径
```

## 打包部署

```bash
# CLI 版本
build.bat

# GUI 版本（推荐）
build_gui.bat
```

打包输出在 `dist/` 目录。打包后的 exe 可以复制到其他电脑直接使用。

### 跨电脑使用

**必要文件**：`AppInstaller.exe`（主程序）

**注意事项**：
- 将程序放在非系统保护目录（如 `D:\AppInstaller\`）
- 首次运行自动创建 data/ 目录
- 安装路径可能需要根据新电脑调整

## 常见问题

**Q: 提示"无写入权限"？**  
A: 将程序移到非系统目录（如 `D:\AppInstaller\`），或右键"以管理员身份运行"。

**Q: 检测到的参数不正确？**  
A: 添加应用时可手动修改参数，或使用 `edit` 命令修改。

**Q: 安装失败？**  
A: 查看日志文件获取详细错误。常见原因：安装包损坏、参数不正确、权限不足、磁盘空间不足。

**Q: 无法自动卸载？**  
A: 绿色软件/便携版不会在注册表中注册，需手动删除。

**Q: GUI 界面启动失败？**  
A: 确保安装了 tkinter（`pip install tk`），或直接使用打包好的 exe。

## 开发说明

### 添加新的软件参数

编辑 `param_detector.py`，在 `KNOWN_SOFTWARE` 字典中添加：

```python
KNOWN_SOFTWARE = {
    'your_software': '/silent /install',
    # ...
}
```

### 注意事项

- 遵循 PEP 8 编码规范
- 添加适当的注释
- 功能改动后及时更新相关文档

## 许可证

MIT License

---

批量应用安装管理器 v1.1

<!-- 激活码备忘：续1个月=zfb_app_month_1 | 续6个月=zfb_app_month_6 | 永久=zfb_app_forever -->