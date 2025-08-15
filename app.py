import os
import time
import psutil
import datetime
from typing import Dict, List, Optional, Any, Union
from flask import Flask, send_from_directory, render_template, url_for, jsonify
from urllib.parse import quote
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import gpiozero  # Raspberry Pi 温度监控支持
    HAS_GPIOZERO = True
except ImportError:
    HAS_GPIOZERO = False

# 项目根目录和存储路径
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
ZOTERO_STORAGE: str = os.path.abspath(os.path.join(BASE_DIR, "../storage"))

# 初始化 Flask 应用
app: Flask = Flask(__name__, static_url_path='/static')

# 文件列表缓存机制
_file_cache: Optional[List[str]] = None
_last_update: float = 0
CACHE_TIMEOUT: int = 600  # 缓存超时时间（秒）


class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory and event.src_path == ZOTERO_STORAGE:
            # 目录发生改变时刷新缓存
            global _file_cache, _last_update
            _file_cache = None  # 使缓存失效
            _last_update = 0  # 使更新时间失效


def start_file_watcher():
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=ZOTERO_STORAGE, recursive=True)
    observer.start()


def get_system_info() -> Dict[str, Any]:
    """
    获取系统运行状态信息，包括 CPU、内存、磁盘、网络等。

    Returns:
        Dict[str, Any]: 包含系统信息的字典。
    """
    try:
        # CPU 信息
        cpu_percent: float = psutil.cpu_percent(interval=1)
        cpu_cores: Optional[int] = psutil.cpu_count(logical=False)
        cpu_threads: Optional[int] = psutil.cpu_count(logical=True)

        # 内存信息
        mem = psutil.virtual_memory()
        mem_total: float = round(mem.total / (1024 ** 3), 2)
        mem_used: float = round(mem.used / (1024 ** 3), 2)
        mem_percent: float = mem.percent

        # 磁盘信息（优先使用 Zotero 存储目录）
        try:
            disk = psutil.disk_usage(ZOTERO_STORAGE)
        except Exception:
            disk = psutil.disk_usage('/')
        disk_total: float = round(disk.total / (1024 ** 3), 2)
        disk_used: float = round(disk.used / (1024 ** 3), 2)
        disk_percent: float = disk.percent

        # 网络信息
        net = psutil.net_io_counters()
        net_sent: float = round(net.bytes_sent / (1024 ** 2), 2)
        net_recv: float = round(net.bytes_recv / (1024 ** 2), 2)

        # 启动时间 & 运行时间
        boot_timestamp: float = psutil.boot_time()
        boot_time: str = datetime.datetime.fromtimestamp(boot_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        uptime_seconds: int = int(time.time()) - int(boot_timestamp)
        uptime: str = str(datetime.timedelta(seconds=uptime_seconds))

        # CPU 温度
        cpu_temp: Optional[float] = None
        if HAS_GPIOZERO:
            cpu_temp = round(gpiozero.CPUTemperature().temperature, 1)
        else:
            try:
                temps = psutil.sensors_temperatures()
                if 'coretemp' in temps:
                    cpu_temp = temps['coretemp'][0].current
                elif temps:
                    first_sensor = list(temps.keys())[0]
                    cpu_temp = temps[first_sensor][0].current
            except Exception:
                pass

        # 项目信息
        files_count: int = len(list_files())

        return {
            'status': 'success',
            'cpu': {
                'percent': cpu_percent,
                'cores': cpu_cores,
                'threads': cpu_threads
            },
            'memory': {
                'total': mem_total,
                'used': mem_used,
                'percent': mem_percent
            },
            'disk': {
                'total': disk_total,
                'used': disk_used,
                'percent': disk_percent,
                'path': ZOTERO_STORAGE
            },
            'network': {
                'sent': net_sent,
                'recv': net_recv
            },
            'system': {
                'boot_time': boot_time,
                'uptime': uptime
            },
            'project': {
                'files_count': files_count,
                'storage_path': ZOTERO_STORAGE
            },
            'temperature': {
                'cpu': cpu_temp,
                'unit': '°C' if cpu_temp is not None else 'N/A'
            }
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def list_files() -> List[str]:
    """
    列出 Zotero 存储目录下的所有 PDF 和 EPUB 文件，并进行缓存。

    Returns:
        List[str]: 文件相对路径列表。
    """
    global _file_cache, _last_update

    # 如果缓存失效，则重新列出文件
    if _file_cache is None or _last_update == 0:
        files: List[str] = []
        for root, _, filenames in os.walk(ZOTERO_STORAGE):
            for f in filenames:
                if f.lower().endswith(('.pdf', '.epub')):
                    full_path: str = os.path.join(root, f)
                    rel_path: str = os.path.relpath(full_path, ZOTERO_STORAGE)
                    files.append(rel_path)

        _file_cache = sorted(files)
        _last_update = time.time()

    return _file_cache


@app.route('/')
def index() -> str:
    """
    主页路由，列出所有 PDF 和 EPUB 文件供浏览。

    Returns:
        str: 渲染后的 HTML 页面。
    """
    files: List[str] = list_files()
    return render_template('index.html', files=files)


@app.route('/view/<path:filename>')
def view_file(filename: str) -> str:
    """
    根据文件类型展示文件（PDF 预览或 EPUB 下载链接）。

    Args:
        filename (str): 相对于存储目录的文件路径。

    Returns:
        str: 渲染后的 HTML 页面或下载链接。
    """
    if filename.lower().endswith('.pdf'):
        pdf_url: str = url_for('serve_file', filename=filename)
        pdf_title: str = os.path.basename(filename)
        return render_template('viewer.html', pdf_url=pdf_url, pdf_title=pdf_title)
    else:
        # EPUB 先简单提供下载（可后续集成 epub.js）
        return f'<a href="{url_for("serve_file", filename=filename)}">Download EPUB</a>'


@app.route('/file/<path:filename>')
def serve_file(filename: str):
    """
    提供存储目录中文件的访问服务。

    Args:
        filename (str): 相对于存储目录的文件路径。

    Returns:
        Response: 文件响应。
    """
    return send_from_directory(ZOTERO_STORAGE, filename)


@app.route('/monitor')
def monitor() -> str:
    """
    渲染系统监控页面。

    Returns:
        str: 渲染后的监控页面。
    """
    return render_template('monitor.html')


@app.route('/monitor/system-info')
def system_info():
    """
    返回 JSON 格式的系统信息。

    Returns:
        Response: JSON 响应。
    """
    return jsonify(get_system_info())


if __name__ == '__main__':
    # 启动文件监控
    start_file_watcher()
    app.run(host='0.0.0.0', port=8080, debug=False)
