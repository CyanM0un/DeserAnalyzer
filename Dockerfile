FROM python:3.11
    
# 设置工作目录
RUN mkdir /app
WORKDIR /app
    
# 设置pip国内镜像源以加速依赖下载
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com
    
# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
    
# 声明容器运行时监听的端口
EXPOSE 5000

# 使用gunicorn
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
