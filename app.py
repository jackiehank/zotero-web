import os
import time
import psutil
import datetime
from flask import Flask, send_from_directory, render_template, url_for, jsonify
from urllib.parse import quote

try:
    import gpiozero  # 树莓派温度监控
    HAS_GPIOZERO = True
except ImportError:
    HAS_GPIOZERO = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZOTERO_STORAGE = os.path.abspath(os.path.join(BASE_DIR, "../storage"))

app = Flask(__name__, static_url_path='/static')

# 添加监控数据获取函数
def get_system_info():
    try:
        # CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)
        
        # 内存信息
        mem = psutil.virtual_memory()
        mem_total = round(mem.total / (1024 ** 3), 2)
        mem_used = round(mem.used / (1024 ** 3), 2)
        mem_percent = mem.percent
        
        # 磁盘信息 - 使用项目存储目录
        try:
            disk = psutil.disk_usage(ZOTERO_STORAGE)
        except Exception:
            disk = psutil.disk_usage('/')
        disk_total = round(disk.total / (1024 ** 3), 2)
        disk_used = round(disk.used / (1024 ** 3), 2)
        disk_percent = disk.percent
        
        # 网络信息
        net = psutil.net_io_counters()
        net_sent = round(net.bytes_sent / (1024 ** 2), 2)
        net_recv = round(net.bytes_recv / (1024 ** 2), 2)
        
        # 系统信息
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        uptime_seconds = int(time.time()) - int(psutil.boot_time())
        uptime = str(datetime.timedelta(seconds=uptime_seconds))

        # 温度信息
        temps = {}
        if HAS_GPIOZERO:
            # 树莓派温度监控
            cpu_temp = gpiozero.CPUTemperature().temperature
            temps['cpu'] = round(cpu_temp, 1)
        else:
            # 其他系统尝试通过 psutil 获取
            try:
                temps = psutil.sensors_temperatures()
                if 'coretemp' in temps:
                    # 获取第一个核心温度
                    cpu_temp = temps['coretemp'][0].current
                elif temps:
                    # 获取第一个可用的温度传感器
                    first_sensor = list(temps.keys())[0]
                    cpu_temp = temps[first_sensor][0].current
                else:
                    cpu_temp = None
            except Exception:
                cpu_temp = None
        
        # 添加项目特定信息
        files_count = len(list_files())
        
        return {
            'status': 'success',
            'cpu': {
                'percent': cpu_percent,
                'cores': cpu_count,
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
            },
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

_file_cache = None
_last_update = 0
CACHE_TIMEOUT = 600  # 10 分钟

def list_files():
    global _file_cache, _last_update
    
    current_time = time.time()
    # 缓存有效且未超时
    if _file_cache and current_time - _last_update < CACHE_TIMEOUT:
        return _file_cache
    
    files = []
    for root, _, filenames in os.walk(ZOTERO_STORAGE):
        for f in filenames:
            if f.lower().endswith(('.pdf', '.epub')):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, ZOTERO_STORAGE)
                files.append(rel_path)

    _file_cache = sorted(files)
    _last_update = current_time
    return _file_cache
    # return sorted(files)

@app.route('/')
def index():
    files = list_files()
    return render_template('index.html', files=files)

@app.route('/view/<path:filename>')
def view_file(filename):
    if filename.lower().endswith('.pdf'):
        # PDF.js 预览
        pdf_url = url_for('serve_file', filename=filename)
        # 获取不带路径的文件名（含扩展名）
        pdf_title = os.path.basename(filename)
        return render_template('viewer.html', pdf_url=pdf_url, pdf_title=pdf_title)
    else:
        # EPUB 先简单提供下载（可后续集成 epub.js）
        return f'<a href="{url_for("serve_file", filename=filename)}">Download EPUB</a>'

@app.route('/file/<path:filename>')
def serve_file(filename):
    return send_from_directory(ZOTERO_STORAGE, filename)

# 监控页面路由
@app.route('/monitor')
def monitor():
    # 直接渲染监控页面模板
    return render_template('monitor.html')

# 监控数据API路由
@app.route('/monitor/system-info')
def system_info():
    return jsonify(get_system_info())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)