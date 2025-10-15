import os
import zipfile
import tarfile

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