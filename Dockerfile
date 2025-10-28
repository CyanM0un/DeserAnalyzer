FROM python:3.11-slim

# 手动创建 sources.list 文件并使用国内镜像
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main" > /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main" >> /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian-security bullseye-security main" >> /etc/apt/sources.list

# 分步执行 APT 操作，避免内存不足
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates
RUN apt-get install -y --no-install-recommends openjdk-17-jre-headless

# 清理 APT 缓存减少镜像大小
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 设置工作目录
WORKDIR /app
    
# 设置pip国内镜像源
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV PIP_DEFAULT_TIMEOUT=100
    
# 复制依赖文件并安装（分步复制以利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 确保 jadx 可执行
RUN chmod +x tools/java_decompile/bin/jadx || true

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
