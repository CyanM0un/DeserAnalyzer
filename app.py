from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from utils import *
from database import *
import threading
import os
import subprocess
import json
import sqlite3
import re

# 以当前文件位置为根目录，避免相对路径问题
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(ROOT_DIR, 'flask_app', 'uploads')
JAVA_DIR = os.path.join(UPLOAD_FOLDER, "java")
PHP_DIR = os.path.join(UPLOAD_FOLDER, "php")

# 确保上传目录存在
os.makedirs(JAVA_DIR, exist_ok=True)
os.makedirs(PHP_DIR, exist_ok=True)

ALLOWED_EXT = {
    "Java": {".jar"},
    "PHP": {".zip", ".tar", ".tar.gz",}
}

app = Flask(__name__, static_url_path='/assets',
            static_folder=os.path.join(ROOT_DIR, 'flask_app', 'assets'), 
            template_folder=os.path.join(ROOT_DIR, 'flask_app', 'templates'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "GCSCAN"

def get_gc_php(gc_file):
    gcs = []
    with open(gc_file, "r", encoding="utf-8") as f:
        contents = f.readlines()
    
    for content in contents: # TODO 增加更多信息
        gc = {}
        temp = json.loads(content)
        gc["gc_stack"] = temp['funcStack']
        gcs.append(gc)

    return gcs

def gc_scan_php(target, hash, filename):
    tool_dir = os.path.join(ROOT_DIR, "tools", "php", "PFortifier")
    run_cmd = ["python", "Main.py"]
    os.environ['PHP_PROG_ROOT'] = target

    result = subprocess.run(run_cmd, cwd=tool_dir, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("Error:", result.stderr)

    results_dir = os.path.join(tool_dir, 'result')
    for result_dir in os.listdir(results_dir):
        if hash in result_dir: # result
            gc_file = os.path.join(results_dir, result_dir, "pop_chains.json")
            gcs = get_gc_php(gc_file)
    
    # 数据库导入
    if gcs is not None:
        gcs_str = json.dumps(gcs)
        db_finish_analyze(hash, gcs_str)
        print(f"{filename} finished analysis")

def gc_scan(file_path, project_path, lang, hash, file_name):
    if lang == "PHP":
        gc_scan_php(project_path, hash, file_name)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/index.html')
def index_html():
    return render_template('index.html')

@app.route('/result')
def result():
    # 结果页面仅从数据库读取调用链数据
    def parse_php_gc_stacks(gc_list):
        """将 PHP 分析结果中的 gc_stack 列表转换为 chains 结构。
        gc_list: 形如 [ {"gc_stack": ["Class#method", ...]}, ... ]
        """
        chains = []
        if not isinstance(gc_list, list):
            return chains
        for idx, item in enumerate(gc_list, start=1):
            stack = item.get('gc_stack') if isinstance(item, dict) else None
            if not stack or not isinstance(stack, list):
                continue
            nodes = []
            edges = []
            prev_id = None
            for i, frame in enumerate(stack):
                label = str(frame)
                # 取短方法名
                short = None
                if '#' in label:
                    short = label.split('#', 1)[1]
                elif '::' in label:
                    short = label.split('::', 1)[1]
                else:
                    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*$", label)
                    short = m.group(1) if m else label
                ntype = 'entry' if i == 0 else ('sink' if i == len(stack) - 1 else 'gadget')
                nid = f"n{i}"
                nodes.append({'id': nid, 'label': label, 'short': short, 'type': ntype})
                if prev_id is not None:
                    edges.append({'from': prev_id, 'to': nid, 'label': ''})
                prev_id = nid
            entry = nodes[0]['short'] if nodes else f'chain-{idx}'
            chains.append({'id': f'c{idx}', 'entry': entry, 'nodes': nodes, 'edges': edges})
        return chains

    def safe_json_loads(s: str):
        if s is None:
            return None
        try:
            return json.loads(s)
        except Exception:
            try:
                fixed = s.replace('""', '"')
                return json.loads(fixed)
            except Exception:
                return None

    def load_projects_from_db():
        projects = []
        try:
            conn = get_connect()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT file_hash, filename, language, analysis_result, status FROM results WHERE analysis_result IS NOT NULL")
            rows = cur.fetchall()
            for row in rows:
                filename = row['filename']
                language = row['language']
                analysis_result = row['analysis_result']
                name = os.path.splitext(filename)[0]

                chains = []
                data = safe_json_loads(analysis_result)
                if language == 'PHP' and data:
                    chains = parse_php_gc_stacks(data)
                # TODO: Java 可在此扩展
                if chains:
                    projects.append({
                        'id': f"{language.lower()}-{name}",
                        'name': name,
                        'language': language,
                        'chains': chains
                    })
            cur.close()
            conn.close()
        except Exception as e:
            # 打印错误但不阻断页面
            print('load_projects_from_db error:', e)
        return projects

    projects = load_projects_from_db()
    # 如果没有解析到任何项目，传 None 以启用前端示例数据
    return render_template('result.html', projects=(projects if projects else None))

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
   if request.method == "POST":
        lang = request.form.get("language", "")
        uploaded = request.files.get("file")
        if not lang:
            flash("请选择语言类型（Java 或 PHP）")
            return redirect(url_for("analyze"))
        if not uploaded or uploaded.filename == "":
            flash("请先选择要上传的文件")
            return redirect(url_for("analyze"))
        
        file_hash = get_file_hash(uploaded)
        analyzed = is_analyzed(file_hash)

        if analyzed:
            if analyzed['status'] == 'completed':
                return redirect(url_for('result', file_hash=file_hash)) # TODO
            flash(f"文件 {filename} 正在分析中，请稍后查看结果")
            return redirect(url_for('analyze'))

        filename = secure_filename(uploaded.filename)
        ext = ext_of(filename)
        allowed = ALLOWED_EXT.get(lang, set())
        db_start_analyze(file_hash, filename, lang, "pending")

        if ext not in allowed:
            flash(f"文件类型不允许：{filename}（期望 {', '.join(sorted(allowed))}）")
            return redirect(url_for("analyze"))

        if lang == "Java":
            save_path = os.path.join(JAVA_DIR, filename)
            save_file(uploaded, save_path)

        if lang == "PHP":
            save_path = os.path.join(PHP_DIR, filename)
            save_file(uploaded, save_path)
            extract_dest = os.path.join(PHP_DIR, file_hash)
            os.makedirs(extract_dest, exist_ok=True)

            if ext == ".zip":
                ok, err = try_extract_zip(save_path, extract_dest)
            else:
                ok, err = try_extract_tar(save_path, extract_dest)
            
            os.remove(save_path)
        
        analysis_thread = threading.Thread(
            target=gc_scan,
            args=(save_path, extract_dest, lang, file_hash, filename),
            daemon=True
        )
        analysis_thread.start()

        flash(f"{filename} 已提交分析，正在处理中...")
        return redirect(url_for('analyze'))

   recent_records = get_several_results()
   return render_template("analyze.html", recent_records=recent_records)

if __name__ == '__main__':
    app.run(debug=True)