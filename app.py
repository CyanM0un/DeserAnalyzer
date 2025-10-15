from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from utils import *

UPLOAD_FOLDER = './flask_app/uploads'
JAVA_DIR = os.path.join(UPLOAD_FOLDER, "java")
PHP_DIR = os.path.join(UPLOAD_FOLDER, "php")
ALLOWED_EXT = {
    "Java": {".jar"},
    "PHP": {".zip", ".tar", ".tar.gz",}
}

app = Flask(__name__, static_url_path='/assets',
            static_folder='./flask_app/assets', 
            template_folder='./flask_app/templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "GCSCAN"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/index.html')
def index_html():
    return render_template('index.html')

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

        filename = secure_filename(uploaded.filename)
        ext = ext_of(filename)
        allowed = ALLOWED_EXT.get(lang, set())

        if ext not in allowed:
            flash(f"文件类型不允许：{filename}（期望 {', '.join(sorted(allowed))}）")
            return redirect(url_for("analyze"))

        if lang == "Java":
            save_path = os.path.join(JAVA_DIR, filename)
            save_file(uploaded, save_path)
            flash(f"Java JAR 已上传：{filename}")
            return redirect(url_for("analyze"))

        if lang == "PHP":
            save_path = os.path.join(PHP_DIR, filename)
            save_file(uploaded, save_path)
            extract_dest = os.path.join(PHP_DIR)
            os.makedirs(extract_dest, exist_ok=True)

            if ext == ".zip":
                ok, err = try_extract_zip(save_path, extract_dest)
            else:
                ok, err = try_extract_tar(save_path, extract_dest)

            if not ok:
                flash(f"解压失败：{err}")
                return redirect(url_for("analyze"))
            flash(f"PHP 项目上传并解压成功")
            return redirect(url_for("analyze"))

   return render_template("analyze.html")

if __name__ == '__main__':
    app.run(debug=True)