#!/bin/bash

# Minion 项目启动脚本
# 根据 startup 规则，需要启动 docker 和 qdrant

echo "🚀 启动 Minion 项目所需资源..."

# 1. 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，正在尝试安装..."
    
    # 更新包索引
    sudo apt-get update
    
    # 安装必要的包
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # 添加 Docker 的官方 GPG 密钥
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # 设置稳定版仓库
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 更新包索引
    sudo apt-get update
    
    # 安装 Docker Engine
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 启动 Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 将当前用户添加到 docker 组
    sudo usermod -aG docker $USER
    
    echo "✅ Docker 安装完成！"
else
    echo "✅ Docker 已安装"
fi

# 2. 检查 Qdrant 是否正在运行
if docker ps | grep -q qdrant; then
    echo "✅ Qdrant 服务已运行"
else
    echo "🔄 启动 Qdrant 服务..."
    
    # 创建 qdrant 存储目录
    mkdir -p ./qdrant_storage
    
    # 停止并移除可能存在的旧容器
    docker stop qdrant 2>/dev/null || true
    docker rm qdrant 2>/dev/null || true
    
    # 启动 Qdrant 容器
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v $(pwd)/qdrant_storage:/qdrant/storage:z \
        qdrant/qdrant
    
    echo "✅ Qdrant 服务启动成功！"
fi

# 3. 构建 Python 执行环境的 Docker 镜像
if ! docker images | grep -q intercode-python; then
    echo "🔄 构建 Python 执行环境..."
    docker build -t intercode-python -f docker/python.Dockerfile .
    echo "✅ Python 执行环境构建完成！"
else
    echo "✅ Python 执行环境已存在"
fi

# 4. 启动 Python 执行环境容器
if ! docker ps | grep -q intercode-python_ic_ctr; then
    echo "🔄 启动 Python 执行环境容器..."
    
    # 停止并移除可能存在的旧容器
    docker stop intercode-python_ic_ctr 2>/dev/null || true
    docker rm intercode-python_ic_ctr 2>/dev/null || true
    
    # 启动容器
    docker run -d \
        --name intercode-python_ic_ctr \
        -p 3006:3006 \
        intercode-python
    
    echo "✅ Python 执行环境容器启动成功！"
else
    echo "✅ Python 执行环境容器已运行"
fi

# 5. 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo "🔄 创建配置文件..."
    cp config/config.yaml.example config/config.yaml
    echo "✅ 配置文件创建完成！请编辑 config/config.yaml 和 config/.env 文件"
else
    echo "✅ 配置文件已存在"
fi

if [ ! -f "config/.env" ]; then
    echo "🔄 创建环境变量文件..."
    cp config/.env.example config/.env
    echo "✅ 环境变量文件创建完成！请编辑 config/.env 文件"
else
    echo "✅ 环境变量文件已存在"
fi

# 6. 检查服务状态
echo "🔍 检查服务状态..."
echo "Qdrant 服务状态:"
curl -s http://localhost:6333/health || echo "❌ Qdrant 服务未响应"

echo "Python 执行环境状态:"
curl -s http://localhost:3006/health || echo "❌ Python 执行环境未响应"

echo ""
echo "🎉 所有资源启动完成！"
echo "📋 服务列表:"
echo "  - Qdrant: http://localhost:6333"
echo "  - Python 执行环境: http://localhost:3006"
echo ""
echo "📝 接下来的步骤:"
echo "  1. 编辑 config/config.yaml 文件，配置你的 API 密钥"
echo "  2. 编辑 config/.env 文件，设置环境变量"
echo "  3. 运行 pip install -r requirements.txt 安装依赖"
echo "  4. 开始使用 Minion！"