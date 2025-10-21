import os
import zipfile
import tarfile
from hashlib import md5
import yaml
import subprocess
import sys

def ext_of(filename: str) -> str:
    fn = filename.lower()
    return os.path.splitext(fn)[1]

def save_file(fileobj, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fileobj.save(save_path)
    return save_path

def try_extract_zip(zip_path, dest_dir):
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(dest_dir)
        return True, None
    except Exception as e:
        return False, str(e)

def try_extract_tar(tar_path, dest_dir):
    try:
        with tarfile.open(tar_path, 'r:*') as tf:
            tf.extractall(dest_dir)
        return True, None
    except Exception as e:
        return False, str(e)

def get_file_hash(file):
    hasher = md5()
    while chunk := file.read(4096):
        hasher.update(chunk)
    file.seek(0)  # 重置文件指针，以便后续保存
    return hasher.hexdigest()

def generate_yaml(base_yaml, target, new_yaml):
    with open(base_yaml, 'r') as f:
        base_config = yaml.safe_load(f)

    target = target + "/"

    base_config['appClassPath'].append(target)

    with open(new_yaml, 'w', encoding='utf-8') as nf:
        yaml.dump(base_config, nf, default_flow_style=False, sort_keys=False)

def decompile_java(save_path):
    """
    若找到 .jar 文件则使用 jadx 反编译
    反编译结果保存在 save_path/decompiled/ 下
    """
    jar_files = []
    for root, _, files in os.walk(save_path):
        for file in files:
            if file.endswith('.jar'):
                jar_files.append(os.path.join(root, file))

    if not jar_files:
        return
    
    output_dir = os.path.join(save_path, "decompiled")
    os.makedirs(output_dir, exist_ok=True)

    for jar in jar_files:
        # 'jar' is already an absolute path from os.walk
        jar_path = jar
        jar_output = os.path.join(output_dir, os.path.splitext(os.path.basename(jar))[0])
        os.makedirs(jar_output, exist_ok=True)

        tool_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "tools", "java_decompile", "bin")
        # Choose the correct launcher per platform
        if os.name == 'nt':
            run_cmd = ["cmd", "/c", "jadx.bat", "-d", jar_output, jar_path]
        else:
            run_cmd = ["./jadx", "-d", jar_output, jar_path]
            # Try to ensure executable permission (best-effort; ignore failures)
            try:
                jadx_path = os.path.join(tool_dir, "jadx")
                if os.path.exists(jadx_path):
                    os.chmod(jadx_path, os.stat(jadx_path).st_mode | 0o111)
            except Exception:
                pass

        with subprocess.Popen(run_cmd, cwd=tool_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
            for line in proc.stdout:
                print(line, end='')
                sys.stdout.flush()