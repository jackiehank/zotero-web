# Zotero Web

一个基于 aiohttp 的 Web 应用，用于局域网内浏览和查看 Zotero 存储中的 PDF 和 EPUB 文件，并提供系统监控功能。

## 功能特性

- 📚 局域网内浏览、搜索 Zotero 存储中的 PDF 和 EPUB 文件
- 📖 内嵌 PDF 查看器（使用 pdf.js）
- 📘 内嵌 EPUB 查看器（使用 epub.js）
- 📊 系统监控仪表板（CPU、内存、磁盘、网络等）
- ⏰ 最近访问文件记录
- 🔄 自动文件变化监控（无需重启即可更新文件列表）
- 🔒 安全路径检查防止目录遍历攻击

## 界面展示
文件搜索：
![search](/static/img/search.jpeg)

pdf 查看：
![pdf](/static/img/pdf.jpeg)

epub 查看：
![epub](/static/img/epub.jpeg)

电脑状态监控：
![monitor](/static/img/monitor.jpeg)

## 项目结构

```
Zotero/web/
├── app.py              # 主应用文件
├── pyproject.toml      # Python 项目配置
├── README.md           # 项目说明文档
├── static/             # 静态文件目录
│   ├── epubjs/         # EPUB.js 库文件
│   ├── icons/          # 图标资源
│   ├── index.css       # 主页样式表
│   ├── monitor.css     # 监控页面样式表
│   └── pdfjs/          # PDF.js 库文件
├── templates/          # HTML 模板目录
│   ├── 404.html        # 404 错误页面
│   ├── epubviewer.html # EPUB 查看器模板
│   ├── index.html      # 主页模板
│   ├── monitor.html    # 监控页面模板
│   └── pdfviewer.html  # PDF 查看器模板
├── uv.lock             # UV 锁文件
├── zweb.log            # 应用日志文件
├── zweb.pid            # 应用进程 ID 文件
└── zweb                # 应用启动脚本
```

## 安装与运行

### 前置要求

- Python 3.7+
- Zotero 文献管理软件
- UV (推荐) 或 pip

### 下载到`Zotero/`
1. 进入`Zotero`文件夹
2. git clone 本项目

### 使用 UV 配置依赖(推荐)

1. 安装 UV (如果尚未安装):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 安装依赖:
```bash
uv sync
```

3. 运行应用:
```bash
uv run python app.py
```

### 或者使用 pip 

1. 安装依赖:
```bash
pip install --user aiohttp aiohttp-jinja2 jinja2 watchdog psutil
```

2. 运行应用:
```bash
python app.py
```

### 使用启动脚本

项目包含一个启动脚本 `zweb`，可以使用以下命令管理应用:

```bash
# 启动应用
zweb run

# 停止应用
zweb stop

# 查看应用状态
zweb status

# 查看应用日志
zweb log
```

确保脚本有执行权限:
```bash
chmod +x ~/.local/bin/zweb
```

## 配置

应用默认使用 `../storage` 作为 Zotero 存储路径。如果需要修改，可以在 `app.py` 中调整 `ZOTERO_STORAGE` 变量。

## 访问应用

- 主页: http://localhost:8080
- 系统监控: http://localhost:8080/monitor

## API 端点

- `GET /` - 主文件浏览页面
- `GET /view/{filename}` - 查看文件（PDF/EPUB）
- `GET /file/{filename}` - 直接访问文件
- `GET /monitor` - 系统监控页面
- `GET /monitor/system-info` - 系统信息 API

## 注意事项

- 应用会自动监控 Zotero 存储目录的文件变化
- 最近访问的文件会显示在文件列表顶部（最多5个）
- 应用包含基本的安全检查，防止目录遍历攻击
- 支持范围请求，便于大文件的分段加载

## 故障排除

如果遇到文件访问问题，可以:

1. 检查 Zotero 存储路径配置是否正确
2. 查看应用日志: `zweb log`
3. 确保文件路径不包含特殊字符

## 许可证

MIT License