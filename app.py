from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from utils import *
from database import *
import threading
import os
import subprocess
import json
import shutil
import sys
import sqlite3
import re
import requests
from dotenv import load_dotenv

# 以当前文件位置为根目录，避免相对路径问题
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(ROOT_DIR, 'flask_app', 'uploads')
JAVA_DIR = os.path.join(UPLOAD_FOLDER, "java")
PHP_DIR = os.path.join(UPLOAD_FOLDER, "php")

# 确保上传目录存在
os.makedirs(JAVA_DIR, exist_ok=True)
os.makedirs(PHP_DIR, exist_ok=True)

ALLOWED_EXT = {
    "Java": {".jar", ".zip", ".tar", ".tar.gz"},
    "PHP": {".zip", ".tar", ".tar.gz",}
}

app = Flask(__name__, static_url_path='/assets',
            static_folder=os.path.join(ROOT_DIR, 'flask_app', 'assets'), 
            template_folder=os.path.join(ROOT_DIR, 'flask_app', 'templates'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "GCSCAN"

# 加载根目录的 .env（若存在），以便读取 AI_BASE_URL/AI_MODEL/AI_API_KEY 等配置
try:
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
except Exception:
    pass

def get_gc_php(gc_file, proj_root: str, file_hash: str):
    """读取 PFortifier 的 pop_chains.json，并将绝对路径标准化为
    以仓库为根的相对路径：/flask_app/uploads/php/<hash>/...

    proj_root 形如：ROOT_DIR/flask_app/uploads/php/<hash>
    """
    gcs = []
    anchor = f"/flask_app/uploads/php/{file_hash}/"
    proj_root_norm = os.path.abspath(proj_root).replace('\\', '/').rstrip('/') + '/'

    def norm_one_path(p: str):
        if not p:
            return p
        s = str(p).replace('\\', '/')
        # 如果路径里包含仓库内的锚点，直接截取
        i = s.find(anchor)
        if i != -1:
            return s[i:]
        # 如果是本机绝对路径，并且包含解压根目录，转换为仓库相对
        if proj_root_norm and proj_root_norm in s:
            suffix = s.split(proj_root_norm, 1)[1].lstrip('/')
            return anchor + suffix
        # 如果只有 uploads/php/<hash> 片段，也补上 /flask_app 前缀
        pat2 = f"/uploads/php/{file_hash}/"
        j = s.find(pat2)
        if j != -1:
            return "/flask_app" + s[j:]
        return s

    with open(gc_file, "r", encoding="utf-8") as f:
        contents = f.readlines()

    for content in contents:  # 一行一个 JSON
        try:
            temp = json.loads(content)
        except Exception:
            continue

        gc = {}
        gc_stack = temp.get('funcStack')
        call_stack = temp.get('callStack')

        gc["gc_stack"] = gc_stack

        # 规范化文件定位堆栈：[[path, line], ...]
        new_fp = []
        if isinstance(call_stack, list):
            for it in call_stack:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    rp = norm_one_path(it[0])
                    try:
                        ln = int(it[1])
                    except Exception:
                        ln = it[1]
                    new_fp.append([rp, ln])
                else:
                    new_fp.append(it)
        gc["filepos_stack"] = new_fp

        gcs.append(gc)

    return gcs

def gc_scan_php(target, hash, filename):
    tool_dir = os.path.join(ROOT_DIR, "tools", "php", "PFortifier")
    run_cmd = ["python", "Main.py"]
    os.environ['PHP_PROG_ROOT'] = target

    with subprocess.Popen(run_cmd, cwd=tool_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        for line in proc.stdout:
            print(line, end='')
            sys.stdout.flush()
    
    if proc.returncode != 0:
        print(f"命令执行失败")

    results_dir = os.path.join(tool_dir, 'result')
    for result_dir in os.listdir(results_dir):
        if hash in result_dir: # result
            gc_file = os.path.join(results_dir, result_dir, "pop_chains.json")
            # 将 callStack 里的路径规范为 /flask_app/uploads/php/<hash>/... 形式
            gcs = get_gc_php(gc_file, proj_root=os.path.join(PHP_DIR, hash), file_hash=hash)
    
    # 数据库导入
    if gcs is not None:
        gcs_str = json.dumps(gcs)
        db_finish_analyze(hash, gcs_str)
        print(f"{filename} finished analysis")

def gc_scan_java(target, hash, file_name):
    print(target)
    tool_dir = os.path.join(ROOT_DIR, "tools", "java")
    new_config = os.path.join(tool_dir, "java-benchmarks/JDV/target.yml")
    generate_yaml(os.path.join(tool_dir, "java-benchmarks/JDV/base.yml"), target, new_config)
    run_cmd = ["java", "-Xss512m", "-Xmx8G", "-jar", "flash.jar", "--options-file", "java-benchmarks/JDV/target.yml"]

    with subprocess.Popen(run_cmd, cwd=tool_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        for line in proc.stdout:
            print(line, end='')
            sys.stdout.flush()

    os.remove(new_config)

    if proc.returncode != 0:
        print(f"命令执行失败")

    gc_file = os.path.join(tool_dir, "output", "chains.json")
    with open(gc_file, "r") as f:
        gcs = json.load(f)

    gcs_str = json.dumps(gcs)
    db_finish_analyze(hash, gcs_str)
    print(f"{file_name} finished analysis")

def gc_scan(project_path, lang, hash, file_name):
    if lang == "PHP":
        gc_scan_php(project_path, hash, file_name)
    elif lang == "Java":
        gc_scan_java(project_path, hash, file_name)

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

    def parse_java_gc(data):
        """容错解析 Java 分析结果，输出与前端一致的 chains 结构。"""
        def short_from_label(label: str):
            if label.startswith('<') and ':' in label and '(' in label and '>' in label:
                try:
                    inner = label[1:label.rfind('>')]
                    part = inner.split(':', 1)[1]
                    before_paren = part.split('(', 1)[0]
                    tokens = before_paren.strip().split()
                    if tokens:
                        return tokens[-1]
                except Exception:
                    pass
            if '#' in label:
                return label.split('#', 1)[1]
            if '::' in label:
                return label.split('::', 1)[1]
            m = re.search(r"([A-Za-z_$][A-Za-z0-9_$<>]*)\s*(?:\(|$)", label)
            return m.group(1) if m else label

        def make_chain_from_labels(labels, idx_base):
            nodes, edges = [], []
            prev = None
            for i, lab in enumerate(labels):
                label = str(lab)
                short = short_from_label(label)
                ntype = 'entry' if i == 0 else ('sink' if i == len(labels) - 1 else 'gadget')
                nid = f"n{idx_base}_{i}"
                nodes.append({'id': nid, 'label': label, 'short': short, 'type': ntype})
                if prev is not None:
                    edges.append({'from': prev, 'to': nid, 'label': ''})
                prev = nid
            entry = nodes[0]['short'] if nodes else f'chain-{idx_base}'
            return {'id': f'c{idx_base}', 'entry': entry, 'nodes': nodes, 'edges': edges}

        chains = []
        if data is None:
            return chains
        try:
            if isinstance(data, dict) and isinstance(data.get('chains'), list):
                raw = data['chains']
            else:
                raw = data if isinstance(data, list) else []

            for idx, ch in enumerate(raw, start=1):
                if isinstance(ch, dict) and isinstance(ch.get('nodes'), list):
                    norm_nodes = []
                    for i, n in enumerate(ch['nodes']):
                        label = n.get('label') or n.get('name') if isinstance(n, dict) else str(n)
                        label = label or ''
                        short = short_from_label(label)
                        ntype = 'entry' if i == 0 else ('sink' if i == len(ch['nodes']) - 1 else 'gadget')
                        nid = n.get('id') if isinstance(n, dict) and n.get('id') else f"n{idx}_{i}"
                        norm_nodes.append({'id': nid, 'label': label, 'short': short, 'type': ntype})
                    norm_edges = []
                    if isinstance(ch.get('edges'), list) and ch['edges']:
                        for e in ch['edges']:
                            if isinstance(e, dict) and e.get('from') and e.get('to'):
                                norm_edges.append({'from': e['from'], 'to': e['to'], 'label': e.get('label', '')})
                    else:
                        for i in range(1, len(norm_nodes)):
                            norm_edges.append({'from': norm_nodes[i-1]['id'], 'to': norm_nodes[i]['id'], 'label': ''})
                    entry = norm_nodes[0]['short'] if norm_nodes else f'chain-{idx}'
                    chains.append({'id': f'c{idx}', 'entry': entry, 'nodes': norm_nodes, 'edges': norm_edges})
                elif isinstance(ch, dict) and isinstance(ch.get('path'), list):
                    chains.append(make_chain_from_labels(ch['path'], idx))
                elif isinstance(ch, dict) and isinstance(ch.get('funcStack'), list):
                    chains.append(make_chain_from_labels(ch['funcStack'], idx))
                elif isinstance(ch, dict) and isinstance(ch.get('gc_stack'), list):
                    chains.append(make_chain_from_labels(ch['gc_stack'], idx))
                elif isinstance(ch, list):
                    chains.append(make_chain_from_labels(ch, idx))
                else:
                    continue
        except Exception as e:
            print('parse_java_gc error:', e)
        return chains

    def safe_json_loads(s: str):
        if s is None:
            return None
        if isinstance(s, (list, dict)):
            return s
        if not isinstance(s, str):
            s = str(s)
        try:
            return json.loads(s)
        except Exception:
            pass
        # 兼容形如："23\t<hash>\t<file>\tJava\t[ ... ]" 的行，只提取最后的 JSON 片段
        try:
            lbr = min([i for i in [s.find('['), s.find('{')] if i != -1]) if ('[' in s or '{' in s) else -1
        except Exception:
            lbr = -1
        if lbr != -1:
            candidate = s[lbr:].strip().rstrip(';')
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    fixed = candidate.replace('""', '"')
                    return json.loads(fixed)
                except Exception:
                    return None
        return None

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
                file_hash = row['file_hash']

                chains = []
                data = safe_json_loads(analysis_result)
                if language == 'PHP' and data:
                    chains = parse_php_gc_stacks(data)
                elif language == 'Java' and data is not None:
                    chains = parse_java_gc(data)
                # 始终加入项目，便于右侧统计与审计按钮可用
                projects.append({
                    'id': f"{language.lower()}-{name}",
                    'name': name,
                    'language': language,
                    'chains': chains or [],
                    'file_hash': file_hash,
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

# ===== 在线审计支持 =====
def _safe_rel_join(root, given_path):
    if not given_path:
        return None
    root_abs = os.path.abspath(root)
    if os.path.isabs(given_path):
        cand_abs = os.path.abspath(os.path.normpath(given_path))
    else:
        cand_abs = os.path.abspath(os.path.normpath(os.path.join(root_abs, given_path)))
    try:
        if os.path.commonpath([cand_abs, root_abs]) != root_abs:
            return None
    except Exception:
        return None
    return cand_abs

def _resolve_audit_Java_file(proj_root, raw_path, file_hash):
    def norm(p: str) -> str:
        return str(p).replace('\\', '/').rstrip('/')

    ret = None
    decompile_dir = os.path.join(proj_root, "decompiled")

    # Normalize incoming path and drop inner-class suffix like Foo$1.java
    raw_norm = norm(raw_path).split('$', 1)[0]

    # Look up inside project decompiled folder first
    for root, dirs, files in os.walk(decompile_dir):
        for file in files:
            if not file.endswith(".java"):
                continue
            full = os.path.join(root, file)
            if raw_norm in norm(full):
                ret = full
                break
        if ret:
            break

    if ret is None:
        jdk_dir = os.path.join(ROOT_DIR, "tools", "java_decompile", "jdk")
        if not os.path.exists(jdk_dir):
            os.makedirs(jdk_dir, exist_ok=True)

            jar_path = os.path.join(
                ROOT_DIR, "tools", "java", "java-benchmarks", "JREs", "jre1.8", "rt.jar"
            )

            tool_dir = os.path.join(
                os.path.abspath(os.path.dirname(__file__)), "tools", "java_decompile", "bin"
            )

            # Choose the correct jadx launcher per platform
            if os.name == 'nt':
                run_cmd = ["cmd", "/c", "jadx.bat", "-d", jdk_dir, jar_path]
            else:
                run_cmd = ["./jadx", "-d", jdk_dir, jar_path]

            with subprocess.Popen(
                run_cmd, cwd=tool_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            ) as proc:
                for line in proc.stdout:
                    print(line, end='')
                    sys.stdout.flush()

        for root, dirs, files in os.walk(jdk_dir):
            for file in files:
                if not file.endswith(".java"):
                    continue
                full = os.path.join(root, file)
                if raw_norm in norm(full):
                    ret = full
                    break
            if ret:
                break

    return ret

def _resolve_audit_file(proj_root: str, raw_path: str, file_hash: str, lang):
    """Resolve a file path coming from analyzer into a path under proj_root.

    The analyzer may record absolute paths from a different machine root
    (e.g. /mnt/d/Work/Major/Complete/.../flask_app/uploads/php/<hash>/...).
    We try to robustly map those to the current uploads directory by:
    - If the absolute path exists locally and contains the hash, use it.
    - Otherwise, if the path contains '/<hash>/' (or '\\<hash>\\'), take the
      suffix after the hash directory and join with proj_root.
    - Otherwise, fall back to treating it as a relative path under proj_root
      with traversal protection.
    """
    if not raw_path:
        return None
    if lang == "Java":
        return _resolve_audit_Java_file(proj_root, raw_path, file_hash)
    # Normalize separators for searching
    p = str(raw_path).replace('\\', '/').strip()
    try:
        # Case 1: absolute and exists locally
        if os.path.isabs(p):
            if os.path.isfile(p):
                # extra safety: ensure the file belongs to this project hash if provided
                if file_hash and (f"/{file_hash}/" in p or f"\\{file_hash}\\" in raw_path):
                    return p
            # '/flask_app/...' 是以仓库为根的伪绝对路径，拼上 ROOT_DIR
            if p.startswith('/flask_app/'):
                cand = os.path.abspath(os.path.join(ROOT_DIR, p.lstrip('/')))
                if os.path.isfile(cand):
                    return cand
            # Case 2: map by <hash> anchor
            if file_hash:
                marker = f"/{file_hash}/"
                pos = p.find(marker)
                if pos != -1:
                    suffix = p.split(marker, 1)[1]
                    cand = os.path.abspath(os.path.join(proj_root, suffix))
                    if os.path.isfile(cand):
                        return cand
        # Case 3: treat as relative under project
        cand = _safe_rel_join(proj_root, p)
        if cand and os.path.isfile(cand):
            return cand
    except Exception:
        pass
    return None

def _extract_function_block(file_path, line_no, lang='PHP', max_scan=400):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return None
    n = len(lines)
    idx = max(1, min(int(line_no or 1), n))
    i0 = idx - 1
    if str(lang).upper() == 'PHP':
        sig_re = re.compile(r"\bfunction\s+&?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    else:
        sig_re = re.compile(r'^(\s*(public|private|protected)\s+)?(static\s+)?[A-Za-z0-9_\<\>\[\]\.?]+\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(')
    start = None
    func_name = None
    for up in range(i0, max(-1, i0 - max_scan), -1):
        m = sig_re.search(lines[up])
        if m:
            start = up
            try:
                func_name = m.group(1) if str(lang).upper() == 'PHP' else m.group(4)
            except Exception:
                func_name = None
            break
    if start is None:
        s = max(0, i0 - 40); e = min(n, i0 + 40)
        return {'func_name': None, 'start_line': s+1, 'end_line': e, 'code_lines': lines[s:e]}
    brace_open_line = None
    for j in range(start, min(n, start + 20)):
        if '{' in lines[j]:
            brace_open_line = j
            break
    if brace_open_line is None:
        s = max(0, start - 2); e = min(n, start + 10)
        return {'func_name': func_name, 'start_line': s+1, 'end_line': e, 'code_lines': lines[s:e]}
    depth = 0
    end = None
    for k in range(brace_open_line, min(n, brace_open_line + max_scan)):
        depth += lines[k].count('{')
        depth -= lines[k].count('}')
        if depth == 0 and k > brace_open_line:
            end = k
            break
    if end is None:
        end = min(n - 1, brace_open_line + 200)
    s = max(0, start)
    e = min(n, end + 1)
    return {'func_name': func_name, 'start_line': s+1, 'end_line': e, 'code_lines': lines[s:e]}

# ===== AI 辅助：构造审计上下文供后端调用大模型 =====
def _build_audit_context_for_ai(file_hash: str, idx: int = 0):
    """根据 file_hash 与链索引，复用审计逻辑组装上下文（meta + steps + 代码片段）。
    返回 (meta, steps)
    """
    try:
        conn = get_connect(); conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT filename, language, analysis_result FROM results WHERE file_hash = ?", (file_hash,))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row:
            return None, []
        language = row['language']
        name = os.path.splitext(row['filename'])[0]
        data = json.loads(row['analysis_result']) if row['analysis_result'] else None
        raw_list = data if isinstance(data, list) else (data.get('chains') if isinstance(data, dict) else [])
        if not raw_list:
            return {'project': name, 'language': language, 'chain_index': 0, 'length': 0, 'entry': '', 'sink': ''}, []
        idx = max(0, min(idx, len(raw_list) - 1))
        ch = raw_list[idx]
        if isinstance(ch, dict):
            stack = ch.get('gc_stack') or ch.get('funcStack') or ch.get('path') or ch.get('nodes')
            if isinstance(stack, list) and stack and isinstance(stack[0], dict):
                stack = [ (n.get('label') or n.get('name') or str(n)) for n in stack ]
            filepos = ch.get('filepos_stack') if isinstance(ch.get('filepos_stack'), list) else None
        elif isinstance(ch, list):
            stack = ch; filepos = None
        else:
            stack = None; filepos = None
        lang_dir = PHP_DIR if (language == 'PHP') else JAVA_DIR
        proj_root = os.path.join(lang_dir, file_hash)
        steps = []
        for i, label in enumerate(stack or [], start=1):
            raw_path = None; line_no = None
            if filepos and i-1 < len(filepos) and isinstance(filepos[i-1], (list, tuple)):
                try:
                    raw_path = filepos[i-1][0]
                    line_no = int(filepos[i-1][1])
                except Exception:
                    pass
            abs_path = _resolve_audit_file(proj_root, raw_path, file_hash, language) if raw_path else None
            display_rel = None; file_name = None
            if abs_path:
                try:
                    display_rel = os.path.relpath(abs_path, proj_root)
                except Exception:
                    display_rel = raw_path
                # 与前端显示一致：隐藏 decompiled/
                try:
                    if language == 'Java' and display_rel:
                        rel_norm = str(display_rel).replace('\\', '/')
                        if rel_norm.startswith('decompiled/'):
                            display_rel = rel_norm[len('decompiled/') :]
                        elif rel_norm.startswith('/decompiled/'):
                            display_rel = rel_norm[len('/decompiled/') :]
                except Exception:
                    pass
                try:
                    file_name = os.path.basename(abs_path)
                except Exception:
                    file_name = None
            else:
                display_rel = raw_path
                try:
                    file_name = os.path.basename(raw_path) if raw_path else None
                except Exception:
                    file_name = None
            snippet = None
            if abs_path and os.path.isfile(abs_path) and line_no:
                snippet = _extract_function_block(abs_path, line_no, lang=language)
            code_text = None
            if snippet and snippet.get('code_lines'):
                try:
                    code_text = ''.join(snippet['code_lines'])
                except Exception:
                    code_text = None
            steps.append({
                'index': i,
                'label': str(label),
                'rel_path': display_rel,
                'file_name': file_name,
                'line': line_no,
                'func_name': snippet.get('func_name') if snippet else None,
                'code': code_text
            })
        meta = {
            'project': name,
            'language': language,
            'chain_index': (idx + 1),
            'length': len(stack or []),
            'entry': str(stack[0]) if stack else '',
            'sink': str(stack[-1]) if stack else ''
        }
        return meta, steps
    except Exception:
        return None, []

def _format_ai_context_text(meta, steps):
    if not meta:
        return '无可用审计上下文'
    lines = []
    lines.append(f"项目: {meta.get('project')} | 语言: {meta.get('language')} | 链: {meta.get('chain_index')}/{meta.get('length')}")
    lines.append(f"Entry: {meta.get('entry')}")
    lines.append(f"Sink: {meta.get('sink')}")
    for s in steps[:20]:  # 限制最多20步，避免提示过长
        code_info = ''
        if s.get('code'):
            # 截断代码，避免过大
            snippet = s['code']
            if len(snippet) > 2000:
                snippet = snippet[:2000] + '\n...<truncated>\n'
            code_info = f"\n代码片段(函数: {s.get('func_name') or '未知'}):\n" + snippet
        lines.append(f"步骤{s['index']}: {s.get('label')} | 文件: {s.get('rel_path')} | 行: {s.get('line')}" + code_info)
    return "\n".join(lines)

def _call_openai_compatible(base_url, api_key, model, messages, temperature=0.2, max_tokens=1200):
    url = base_url.rstrip('/') + '/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = { 'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get('choices', [{}])[0].get('message', {}).get('content', '')

@app.route('/audit')
def audit():
    file_hash = request.args.get('hash')
    idx = request.args.get('idx', type=int, default=0)
    lang = request.args.get('lang', default=None)
    if not file_hash:
        return redirect(url_for('result'))
    try:
        conn = get_connect(); conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT filename, language, analysis_result FROM results WHERE file_hash = ?", (file_hash,))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row:
            return render_template('audit.html', meta={'project':'未知','language':lang or '未知','chain_index':0,'length':0,'entry':'','sink':''}, steps=[])
        language = lang or row['language']
        name = os.path.splitext(row['filename'])[0]
        data = json.loads(row['analysis_result']) if row['analysis_result'] else None
        raw_list = data if isinstance(data, list) else (data.get('chains') if isinstance(data, dict) else [])
        if not raw_list:
            return render_template('audit.html', meta={'project': name, 'language': language, 'chain_index': 0, 'length': 0, 'entry': '', 'sink': ''}, steps=[])
        idx = max(0, min(idx, len(raw_list) - 1))
        ch = raw_list[idx]
        if isinstance(ch, dict):
            stack = ch.get('gc_stack') or ch.get('funcStack') or ch.get('path') or ch.get('nodes')
            if isinstance(stack, list) and stack and isinstance(stack[0], dict):
                stack = [ (n.get('label') or n.get('name') or str(n)) for n in stack ]
            filepos = ch.get('filepos_stack') if isinstance(ch.get('filepos_stack'), list) else None
        elif isinstance(ch, list):
            stack = ch; filepos = None
        else:
            stack = None; filepos = None
        if not isinstance(stack, list):
            return render_template('audit.html', meta={'project': name, 'language': language, 'chain_index': idx+1, 'length': 0, 'entry': '', 'sink': ''}, steps=[])
        lang_dir = PHP_DIR if (language == 'PHP') else JAVA_DIR
        proj_root = os.path.join(lang_dir, file_hash)
        steps = []
        for i, label in enumerate(stack, start=1):
            raw_path = None; line_no = None
            if filepos and i-1 < len(filepos) and isinstance(filepos[i-1], (list, tuple)):
                try:
                    raw_path = filepos[i-1][0]
                    line_no = int(filepos[i-1][1])
                except Exception:
                    pass
            # Prefer robust resolver that can handle absolute paths from other machines
            abs_path = _resolve_audit_file(proj_root, raw_path, file_hash, language) if raw_path else None
            display_rel = None
            file_name = None
            if abs_path:
                try:
                    display_rel = os.path.relpath(abs_path, proj_root)
                except Exception:
                    display_rel = raw_path
                # For Java, hide leading 'decompiled/' folder in display only
                try:
                    if language == 'Java' and display_rel:
                        rel_norm = str(display_rel).replace('\\', '/')
                        if rel_norm.startswith('decompiled/'):
                            display_rel = rel_norm[len('decompiled/'):]
                        elif rel_norm.startswith('/decompiled/'):
                            display_rel = rel_norm[len('/decompiled/'):]
                except Exception:
                    pass
                try:
                    file_name = os.path.basename(abs_path)
                except Exception:
                    file_name = None
            else:
                display_rel = raw_path
                # Also handle the case where raw_path already has a leading '/decompiled/'
                try:
                    if language == 'Java' and display_rel:
                        rel_norm = str(display_rel).replace('\\', '/')
                        if rel_norm.startswith('decompiled/'):
                            display_rel = rel_norm[len('decompiled/'):]
                        elif rel_norm.startswith('/decompiled/'):
                            display_rel = rel_norm[len('/decompiled/'):]
                except Exception:
                    pass
                try:
                    file_name = os.path.basename(raw_path) if raw_path else None
                except Exception:
                    file_name = None
            snippet = None
            if abs_path and os.path.isfile(abs_path) and line_no:
                snippet = _extract_function_block(abs_path, line_no, lang=language)
            steps.append({
                'index': i,
                'label': str(label),
                'rel_path': display_rel,
                'file_name': file_name,
                'line': line_no,
                'found': bool(snippet),
                'func_name': snippet.get('func_name') if snippet else None,
                'start_line': snippet.get('start_line') if snippet else None,
                'end_line': snippet.get('end_line') if snippet else None,
                'code_lines': snippet.get('code_lines') if snippet else None,
            })
        meta = {
            'project': name,
            'language': language,
            'chain_index': idx + 1,
            'length': len(stack),
            'entry': str(stack[0]) if stack else '',
            'sink': str(stack[-1]) if stack else ''
        }
        return render_template('audit.html', meta=meta, steps=steps)
    except Exception as e:
        print('audit error:', e)
        return render_template('audit.html', meta={'project':'错误','language':lang or '未知','chain_index':0,'length':0,'entry':'','sink':''}, steps=[])

# === AI 后端接口：读取前端页面对应的数据并调用大模型 ===
@app.route('/api/ai/audit', methods=['POST'])
def api_ai_audit():
    try:
        payload = request.get_json(silent=True) or {}
        file_hash = payload.get('hash') or request.args.get('hash')
        idx = int(payload.get('idx') or request.args.get('idx') or 0)
        question = (payload.get('question') or '').strip()
        if not file_hash:
            return jsonify({'error': 'missing hash'}), 400
        meta, steps = _build_audit_context_for_ai(file_hash, idx)
        ctx = _format_ai_context_text(meta, steps)

        # 读取环境变量配置，默认使用硅基流动 DeepSeek 兼容接口
        base_url = os.environ.get('AI_BASE_URL', 'https://api.siliconflow.cn/v1')
        api_key = os.environ.get('AI_API_KEY', '')
        model = os.environ.get('AI_MODEL', 'deepseek-ai/DeepSeek-V3.2-Exp')
        if not api_key:
            return jsonify({
                'error': 'AI 服务未配置',
                'detail': '服务器未设置 AI_API_KEY 环境变量，请在后端设置后重启服务。',
                'fix': 'export AI_API_KEY=xxxx （可选：AI_BASE_URL、AI_MODEL）'
            }), 503

        sys_prompt = (
            "你是专业的反序列化漏洞审计助手。以下是后端收集到的审计上下文（包含链路与相关代码片段）。\n"
            "请基于这些信息进行回答，严格区分事实与推断，如信息不足请直言。\n"
        ) + ctx
        messages = [
            { 'role': 'system', 'content': sys_prompt },
            { 'role': 'user', 'content': question or '请基于当前上下文给出你的分析与修复建议。' }
        ]
        answer = _call_openai_compatible(base_url, api_key, model, messages)
        return jsonify({'answer': answer, 'meta': meta}), 200
    except requests.HTTPError as e:
        try:
            err_json = e.response.json()
        except Exception:
            err_json = None
        return jsonify({'error': f'AI HTTP {e.response.status_code}', 'detail': err_json}), 502
    except Exception as e:
        return jsonify({'error': 'server error', 'detail': str(e)}), 500

@app.route('/api/ai/health', methods=['GET'])
def api_ai_health():
    return jsonify({
        'AI_BASE_URL': os.environ.get('AI_BASE_URL', 'https://api.siliconflow.cn/v1'),
        'AI_MODEL': os.environ.get('AI_MODEL', 'deepseek-ai/DeepSeek-V3.2-Exp'),
        'AI_API_KEY_configured': bool(os.environ.get('AI_API_KEY'))
    })

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
        filename = secure_filename(uploaded.filename)

        if analyzed:
            if analyzed['status'] == 'completed':
                return redirect(url_for('result', file_hash=file_hash)) # TODO
            flash(f"文件 {filename} 正在分析中，请稍后查看结果")
            return redirect(url_for('analyze'))

        ext = ext_of(filename)
        allowed = ALLOWED_EXT.get(lang, set())
        db_start_analyze(file_hash, filename, lang, "pending")

        if ext not in allowed:
            flash(f"文件类型不允许：{filename}（期望 {', '.join(sorted(allowed))}）")
            return redirect(url_for("analyze"))

        if lang == "Java":
            save_path = os.path.join(JAVA_DIR, filename)
            extract_dest = os.path.join(JAVA_DIR, file_hash)
        elif lang == "PHP":
            save_path = os.path.join(PHP_DIR, filename)
            extract_dest = os.path.join(PHP_DIR, file_hash)

        save_file(uploaded, save_path)
        os.makedirs(extract_dest, exist_ok=True)

        if ext == ".zip":
            try_extract_zip(save_path, extract_dest)
            os.remove(save_path)
        elif ext == ".tar" or ext == ".tar.gz":
            try_extract_tar(save_path, extract_dest)
            os.remove(save_path)
        elif ext == ".jar":
            shutil.move(save_path, extract_dest)
        
        decompile_java(extract_dest)
        
        analysis_thread = threading.Thread(
            target=gc_scan,
            args=(extract_dest, lang, file_hash, filename),
            daemon=True
        )
        analysis_thread.start()

        flash(f"{filename} 已提交分析，正在处理中...")
        return redirect(url_for('analyze'))

   limited_records = get_limited_results()
   return render_template("analyze.html", limited_records=limited_records)

if __name__ == '__main__':
    app.run(debug=True)