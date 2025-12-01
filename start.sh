#!/bin/bash

# ================= 配置部分 =================
# 定义颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 确保脚本在出错时继续执行清理，但在关键步骤出错时提示
set -e

# 捕获退出信号 (Ctrl+C)，自动杀死所有子进程
trap 'echo -e "\n${RED}正在停止所有服务...${NC}"; kill $(jobs -p); exit' SIGINT SIGTERM EXIT

echo -e "${BLUE}=== SSO OAuth 2.0 项目一键启动脚本 ===${NC}"

# 1. 检查 Python 环境
echo -e "${GREEN}[1/5] 检查环境...${NC}"
if ! command -v flask &> /dev/null; then
    echo -e "${RED}错误: 未找到 flask 命令。请先激活您的 conda 环境 (sso_env)。${NC}"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 2. 检查并生成证书
echo -e "${GREEN}[2/5] 检查证书...${NC}"
chmod +x certs/*.sh
if [[ ! -f "certs/ca.crt" ]]; then
    echo "未找到证书，正在自动生成..."
    cd certs
    ./create_ca.sh > /dev/null 2>&1
    ./create_server.sh auth-server > /dev/null 2>&1
    ./create_server.sh academic-api > /dev/null 2>&1
    ./create_server.sh cloud-api > /dev/null 2>&1
    # 生成一个默认的客户端证书供测试
    ./create_client.sh alice > /dev/null 2>&1
    cd ..
    echo "证书生成完毕。"
else
    echo "证书已存在，跳过生成。"
fi

# 3. 启动后端服务 (Flask API)
echo -e "${GREEN}[3/5] 启动后端服务...${NC}"

# Auth Server (Port 5000)
export FLASK_APP=auth-server/app.py
flask run --cert=certs/auth-server.crt --key=certs/auth-server.key -p 5000 > logs/auth-backend.log 2>&1 &
echo -e "  -> Auth Server 运行在: ${BLUE}https://auth.localhost:5000${NC}"

# Academic API (Port 5001)
export FLASK_APP=academic-api/app.py
flask run --cert=certs/academic-api.crt --key=certs/academic-api.key -p 5001 > logs/academic-backend.log 2>&1 &
echo -e "  -> Academic API 运行在: ${BLUE}https://academic.localhost:5001${NC}"

# Cloud API (Port 5002)
export FLASK_APP=cloud-api/app.py
flask run --cert=certs/cloud-api.crt --key=certs/cloud-api.key -p 5002 > logs/cloud-backend.log 2>&1 &
echo -e "  -> Cloud API 运行在:    ${BLUE}https://cloud.localhost:5002${NC}"

# 4. 启动前端静态服务器
echo -e "${GREEN}[4/5] 启动前端静态服务器...${NC}"

# Auth Portal (Port 4173)
cd frontends/auth
python ../https_server.py --ssl-cert ../../certs/auth-server.crt --ssl-key ../../certs/auth-server.key --port 4173 > ../../logs/auth-frontend.log 2>&1 &
echo -e "  -> 认证门户入口: ${BLUE}https://auth.localhost:4173/auth.html${NC}"
cd ../..

# Academic Frontend (Port 4174)
cd frontends/academic
python ../https_server.py --ssl-cert ../../certs/academic-api.crt --ssl-key ../../certs/academic-api.key --port 4174 > ../../logs/academic-frontend.log 2>&1 &
echo -e "  -> 教务系统入口: ${BLUE}https://academic.localhost:4174/academic.html${NC}"
cd ../..

# Cloud Frontend (Port 4176)
cd frontends/cloud
python ../https_server.py --ssl-cert ../../certs/cloud-api.crt --ssl-key ../../certs/cloud-api.key --port 4176 > ../../logs/cloud-frontend.log 2>&1 &
echo -e "  -> 云盘系统入口: ${BLUE}https://cloud.localhost:4176/cloud.html${NC}"
cd ../..

# 5. 等待
echo -e "${GREEN}[5/5] 所有服务已启动!${NC}"
echo -e "-----------------------------------------------------"
echo -e "日志文件保存在 logs/ 目录下。"
echo -e "请按 ${RED}Ctrl+C${NC} 停止所有服务并退出。"
echo -e "-----------------------------------------------------"

# 挂起脚本，等待信号
wait