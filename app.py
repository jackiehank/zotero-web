import os
import time
import psutil
import datetime
import asyncio
from typing import Dict, List, Optional, Any, Union
from aiohttp import web
import aiohttp_jinja2
import jinja2
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from urllib.parse import quote

try:
    import gpiozero

    HAS_GPIOZERO = True
except ImportError:
    HAS_GPIOZERO = False

# 项目根目录和存储路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZOTERO_STORAGE = os.path.abspath(os.path.join(BASE_DIR, "../storage"))

# 文件列表缓存机制
_file_cache = None
_last_update = 0
CACHE_TIMEOUT = 600

# 存储最近访问的文件
_recent_files = []
NUM_RECENT_FILES = 5


class FileChangeHandler(FileSystemEventHandler):
    def _invalidate_cache_if_in_storage(self, src_path):
        if src_path.startswith(ZOTERO_STORAGE):
            global _file_cache, _last_update
            _file_cache = None
            _last_update = 0

    def on_created(self, event):
        self._invalidate_cache_if_in_storage(event.src_path)

    def on_deleted(self, event):
        self._invalidate_cache_if_in_storage(event.src_path)

    def on_moved(self, event):
        self._invalidate_cache_if_in_storage(event.src_path)
        self._invalidate_cache_if_in_storage(event.dest_path)


def start_file_watcher():
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=ZOTERO_STORAGE, recursive=True)
    observer.start()


async def get_system_info() -> Dict[str, Any]:
    """异步获取系统信息"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_system_info_sync)


def _get_system_info_sync() -> Dict[str, Any]:
    """同步版本的系统信息获取"""
    try:
        # CPU 信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)

        # 内存信息
        mem = psutil.virtual_memory()
        mem_total = round(mem.total / (1024**3), 2)
        mem_used = round(mem.used / (1024**3), 2)
        mem_percent = mem.percent

        # 磁盘信息
        try:
            disk = psutil.disk_usage(ZOTERO_STORAGE)
        except Exception:
            disk = psutil.disk_usage("/")
        disk_total = round(disk.total / (1024**3), 2)
        disk_used = round(disk.used / (1024**3), 2)
        disk_percent = disk.percent

        # 网络信息
        net = psutil.net_io_counters()
        net_sent = round(net.bytes_sent / (1024**2), 2)
        net_recv = round(net.bytes_recv / (1024**2), 2)

        # 启动时间 & 运行时间
        boot_timestamp = psutil.boot_time()
        boot_time = datetime.datetime.fromtimestamp(boot_timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        uptime_seconds = int(time.time()) - int(boot_timestamp)
        uptime = str(datetime.timedelta(seconds=uptime_seconds))

        # CPU 温度
        cpu_temp = None
        if HAS_GPIOZERO:
            cpu_temp = round(gpiozero.CPUTemperature().temperature, 1)
        else:
            try:
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    cpu_temp = temps["coretemp"][0].current
                elif temps:
                    first_sensor = list(temps.keys())[0]
                    cpu_temp = temps[first_sensor][0].current
            except Exception:
                pass

        # 项目信息
        files_count = len(_list_files_sync())

        return {
            "status": "success",
            "cpu": {"percent": cpu_percent, "cores": cpu_cores, "threads": cpu_threads},
            "memory": {"total": mem_total, "used": mem_used, "percent": mem_percent},
            "disk": {
                "total": disk_total,
                "used": disk_used,
                "percent": disk_percent,
                "path": ZOTERO_STORAGE,
            },
            "network": {"sent": net_sent, "recv": net_recv},
            "system": {"boot_time": boot_time, "uptime": uptime},
            "project": {"files_count": files_count, "storage_path": ZOTERO_STORAGE},
            "temperature": {
                "cpu": cpu_temp,
                "unit": "°C" if cpu_temp is not None else "N/A",
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def list_files() -> List[str]:
    """异步列出文件"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_files_sync)


def _list_files_sync() -> List[str]:
    """同步版本的文件列表获取"""
    global _file_cache, _last_update

    if (
        _file_cache is None
        or _last_update == 0
        or (time.time() - _last_update) > CACHE_TIMEOUT
    ):
        files = []
        for root, _, filenames in os.walk(ZOTERO_STORAGE):
            for f in filenames:
                if f.lower().endswith((".pdf", ".epub")):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, ZOTERO_STORAGE)
                    url_compatible_path = rel_path.replace(os.sep, "/")
                    files.append(url_compatible_path)

        _file_cache = sorted(files)
        _last_update = time.time()

    recent_files = _recent_files[:NUM_RECENT_FILES]
    remaining_files = [file for file in _file_cache if file not in _recent_files]

    return recent_files + remaining_files


@aiohttp_jinja2.template("index.html")
async def index(request):
    """主页路由"""
    files = await list_files()
    return {"files": files, "request": request}


async def view_file(request):
    """查看文件"""
    global _recent_files

    filename = request.match_info["filename"]
    file_path = os.path.join(ZOTERO_STORAGE, filename)

    # 安全检查
    if not os.path.realpath(file_path).startswith(os.path.realpath(ZOTERO_STORAGE)):
        return web.Response(text="Forbidden", status=403)

    # 存在性检查
    if not os.path.isfile(file_path):
        return web.Response(text="Not Found", status=404)

    # 更新最近访问文件
    if filename in _recent_files:
        _recent_files.remove(filename)
    _recent_files.insert(0, filename)
    _recent_files = _recent_files[:NUM_RECENT_FILES]

    if filename.lower().endswith(".pdf"):
        pdf_url = request.app.router["serve_file"].url_for(filename=filename)
        context = {
            "pdf_url": str(pdf_url),
            "pdf_title": os.path.basename(filename),
            "request": request,
        }
        return aiohttp_jinja2.render_template("viewer.html", request, context)
    else:
        epub_url = request.app.router["serve_file"].url_for(filename=filename)
        return web.Response(
            text=f'<a href="{epub_url}">Download EPUB</a>', content_type="text/html"
        )


async def serve_file(request):
    """提供文件服务"""
    filename = request.match_info["filename"]
    file_path = os.path.join(ZOTERO_STORAGE, filename)

    # 安全检查
    if not os.path.realpath(file_path).startswith(os.path.realpath(ZOTERO_STORAGE)):
        return web.Response(text="Forbidden", status=403)

    return web.FileResponse(file_path)


@aiohttp_jinja2.template("monitor.html")
async def monitor(request):
    """监控页面"""
    return {"request": request}


async def system_info(request):
    """系统信息API"""
    info = await get_system_info()
    return web.json_response(info)


async def handle_404(request):
    """404处理"""
    return aiohttp_jinja2.render_template(
        "404.html", request, {"request": request}, status=404
    )


# 创建静态URL辅助函数
def static_url(filename):
    """生成静态文件URL"""

    def _static_url(context):
        # 从上下文中获取request对象
        request = context.get("request")
        if request:
            # 使用aiohttp的方式生成静态URL
            static_route = request.app.router["static"]
            return str(static_route.url_for(filename=filename))
        # 如果无法获取request，返回简单的静态路径
        return f"/static/{filename}"

    return _static_url


def init_app():
    """初始化应用"""
    app = web.Application()

    # 设置Jinja2模板
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("templates"))

    # 添加静态URL辅助函数到模板环境
    env = aiohttp_jinja2.get_env(app)

    # 为特定静态文件创建辅助函数
    env.globals["static_url"] = static_url

    # 添加urlencode过滤器
    env.filters["urlencode"] = lambda s: quote(s)

    # 添加路由
    app.router.add_get("/", index, name="index")
    app.router.add_get("/view/{filename:.+}", view_file, name="view_file")
    app.router.add_get("/file/{filename:.+}", serve_file, name="serve_file")
    app.router.add_get("/monitor", monitor, name="monitor")
    app.router.add_get("/monitor/system-info", system_info, name="system_info")

    # 添加静态文件路由
    app.router.add_static("/static/", path="static", name="static")

    # 添加404处理
    app.router.add_route("*", "/{tail:.*}", handle_404)

    return app


if __name__ == "__main__":
    # 启动文件监控
    start_file_watcher()

    # 启动aiohttp服务器
    app = init_app()
    web.run_app(app, host="0.0.0.0", port=8080)
