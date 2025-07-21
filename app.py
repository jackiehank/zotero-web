import os
from flask import Flask, send_from_directory, render_template, url_for
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZOTERO_STORAGE = os.path.abspath(os.path.join(BASE_DIR, "../storage"))

app = Flask(__name__, static_url_path='/static')
def list_files():
    files = []
    for root, _, filenames in os.walk(ZOTERO_STORAGE):
        for f in filenames:
            if f.lower().endswith(('.pdf', '.epub')):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, ZOTERO_STORAGE)
                files.append(rel_path)
    return sorted(files)

@app.route('/')
def index():
    files = list_files()
    return render_template('index.html', files=files)

@app.route('/view/<path:filename>')
def view_file(filename):
    if filename.lower().endswith('.pdf'):
        # PDF.js 预览
        pdf_url = url_for('serve_file', filename=filename)
        # pdf_url = quote(pdf_url, safe="/:?=&")  # URL 编码
        return render_template('viewer.html', pdf_url=pdf_url)
    else:
        # EPUB 先简单提供下载（可后续集成 epub.js）
        return f'<a href="{url_for("serve_file", filename=filename)}">Download EPUB</a>'

@app.route('/file/<path:filename>')
def serve_file(filename):
    return send_from_directory(ZOTERO_STORAGE, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)