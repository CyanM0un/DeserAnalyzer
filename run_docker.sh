#!/bin/bash

set -e

echo "开始构建 Docker 镜像..."
docker build -t app .

# 检查是否已有同名容器在运行，如果有则停止并删除
if [ "$(docker ps -aq -f name=app)" ]; then
    echo "发现已存在的 app 容器，正在停止并删除..."
    docker stop app >/dev/null 2>&1 || true
    docker rm app >/dev/null 2>&1 || true
fi

echo "启动 Docker 容器（带目录映射）..."
docker run \
    --name app \
    -p 5000:5000 \
    -v "$(pwd):/app" \
    app

echo "部署完成！"