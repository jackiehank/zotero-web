import os
import time
import psutil
import datetime
from typing import Dict, List, Optional, Any, Union
from flask import Flask, abort, send_from_directory, render_template, url_for, jsonify
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

# 存储最近访问的文件
_recent_files: List[str] = []
NUM_RECENT_FILES: int = 5  # 最近访问文件数量限制

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
        # 注意：移动可能涉及 dest_path
        self._invalidate_cache_if_in_storage(event.dest_path)


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
    记录最近访问的文件，最近的文件会显示在列表的最前端。

    Returns:
        List[str]: 文件相对路径列表。
    """
    global _file_cache, _last_update, _recent_files

    # 如果缓存失效，则重新列出文件
    if (_file_cache is None or _last_update == 0 or (time.time() - _last_update) > CACHE_TIMEOUT):
        files: List[str] = []
        for root, _, filenames in os.walk(ZOTERO_STORAGE):
            for f in filenames:
                if f.lower().endswith(('.pdf', '.epub')):
                    full_path: str = os.path.join(root, f)
                    rel_path: str = os.path.relpath(full_path, ZOTERO_STORAGE)
                    # 跨平台：转为正斜杠，用于 URL
                    url_compatible_path = rel_path.replace(os.sep, '/')
                    files.append(url_compatible_path)
                    # files.append(rel_path)

        _file_cache = sorted(files)
        _last_update = time.time()

    # 将最近访问的文件排在文件列表最前面
    # 确保文件只出现在一次（避免重复）
    recent_files = _recent_files[:NUM_RECENT_FILES]  # 取最近的NUM_RECENT_FILES个文件
    remaining_files = [file for file in _file_cache if file not in _recent_files]

    return recent_files + remaining_files


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
    根据文件类型展示文件（PDF 预览或 EPUB 下载链接）,并记录最近访问的文件。

    Args:
        filename (str): 相对于存储目录的文件路径。

    Returns:
        str: 渲染后的 HTML 页面或下载链接。
    """
    global _recent_files

    # 构造完整文件路径
    file_path = os.path.join(ZOTERO_STORAGE, filename)

    # 安全检查：防止路径穿越（如 ../../etc/passwd）
    if not os.path.realpath(file_path).startswith(os.path.realpath(ZOTERO_STORAGE)):
        abort(403)  # Forbidden

    # 存在性检查：文件必须存在
    if not os.path.isfile(file_path):
        abort(404)  # Not Found

    # 如果已存在，先删除
    if filename in _recent_files:
        _recent_files.remove(filename)
    # 总是插入到最前面
    _recent_files.insert(0, filename)
    # 再截断
    _recent_files = _recent_files[:NUM_RECENT_FILES]

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


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    # 启动文件监控
    start_file_watcher()
    app.run(host='0.0.0.0', port=8080, debug=True)
