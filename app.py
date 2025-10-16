from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from utils import *
from database import *
import threading
import os
import re
import subprocess
import json

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
    # 从上传目录中加载分析结果（如果存在），期望文件名 chains.txt
    def parse_gadget_chain_text(text: str):
        """将链文本解析为前端可用的 chains 数组。
        格式示例（链之间以空行分隔，末尾 !!! 表示危险汇聚点）：

        <Class: Ret method(Signature)>->[idx,...]
        <Class: Ret method(Signature)> !!!
        """
        chains = []
        if not text:
            return chains

        blocks = re.split(r"\n\s*\n+", text.strip())
        for bi, block in enumerate(blocks, start=1):
            lines = [ln for ln in (block.strip().splitlines()) if ln.strip()]
            if not lines:
                continue

            nodes = []
            edges = []
            prev_id = None
            for i, raw in enumerate(lines):
                line = raw.strip()
                # 形如：<...>->[... ] 或 <...> !!! 或 <...>
                # 提取签名、索引与是否为终点
                has_bang = line.endswith('!!!')
                # 去除 !!!
                if has_bang:
                    line = line[:-3].rstrip()

                m = re.match(r"^<([^>]+)>(?:\s*->\s*(\[[^\]]*\]))?\s*$", line)
                if not m:
                    # 不符合预期格式，跳过该行
                    continue

                signature = m.group(1).strip()
                idx_list = (m.group(2) or '').strip()

                node_id = f"n{i}"
                # 节点类型：首个为 entry；末尾带 !!! 为 sink；其余为 gadget
                ntype = 'entry' if i == 0 else ('sink' if has_bang else 'gadget')
                # 提取简短方法名，格式：Class: Ret method(Signature)
                short = None
                try:
                    mm = re.match(r"^[^:]+:\s*[^\s]+\s+([^\(]+)\(", signature)
                    if mm:
                        short = mm.group(1).strip()
                except Exception:
                    short = None
                nodes.append({
                    'id': node_id,
                    'label': signature,   # 完整签名（用于 hover/详情）
                    'short': short,       # 简短方法名（用于节点上显示）
                    'type': ntype
                })

                if prev_id is not None:
                    label = ''
                    if idx_list:
                        label = idx_list
                    edges.append({'from': prev_id, 'to': node_id, 'label': label})
                prev_id = node_id

            # 以第一行的方法名作为链入口名（entry）
            entry_name = None
            if nodes:
                # 优先使用短方法名作为入口显示，其次使用冒号后的文本
                entry_name = nodes[0].get('short') or nodes[0]['label'].split(':', 1)[-1].strip()
            else:
                entry_name = f"chain-{bi}"
            chains.append({
                'id': f'c{bi}',
                'entry': entry_name,
                'nodes': nodes,
                'edges': edges
            })
        return chains

    def load_projects_from_uploads():
        projects = []
        for lang, d in (("Java", JAVA_DIR), ("PHP", PHP_DIR)):
            if not os.path.isdir(d):
                continue
            try:
                for fn in sorted(os.listdir(d)):
                    fp = os.path.join(d, fn)
                    if not os.path.isfile(fp):
                        continue
                    name, ext = os.path.splitext(fn)
                    if ext.lower() != '.txt':
                        continue
                    content = None
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        content = None
                    if not content:
                        continue
                    chains = parse_gadget_chain_text(content)
                    if chains:
                        projects.append({
                            'id': f'{lang.lower()}-{name}',
                            'name': name,            # 使用文件名作为项目名（例如 c3p0）
                            'language': lang,
                            'chains': chains
                        })
            except Exception:
                pass
        return projects

    projects = load_projects_from_uploads()
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

   return render_template("analyze.html")

if __name__ == '__main__':
    app.run(debug=True)