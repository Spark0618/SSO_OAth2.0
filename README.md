SSO OAuth2.0 + 简易CA 演示
================================

该示例搭建 3 个前后端分离的站点（教务、云盘、统一认证），使用 OAuth2.0 授权码模式，并演示自建 CA、服务器/客户端证书、单向/双向 TLS 以及令牌管理流程。所有服务均可在本地不同端口运行，便于课堂演示。

目录结构
--------
- `auth-server/`：统一身份认证（授权服务器，Flask REST API）
- `academic-api/`：教务信息 API（资源服务器）
- `cloud-api/`：云盘 API（资源服务器）
- `frontends/`：Vue（CDN 方式）前端示例，分别对应教务、云盘、认证门户，附带简易https_server
- `certs/`：自建 CA 与服务/客户端证书示例脚本与占位

快速开始
--------
1) 安装 Python 依赖（推荐创建虚拟环境）：
```
pip install -r requirements.txt
```

2) 生成自建 CA 与服务器/客户端证书（放在 `certs/`，演示用开发证书，不建议生产）：
```
cd certs
./create_ca.sh             # 生成 ca.key / ca.crt
./create_server.sh auth-server   # 生成 auth-server.key / auth-server.crt，使用自建 CA 签发
./create_server.sh academic-api
./create_server.sh cloud-api
./create_client.sh alice   # 生成客户端证书 alice.key / alice.crt
```
> 前端浏览器需信任 `certs/ca.crt` 方可完成“单向认证”示例；若要演示双向认证，请将客户端证书导入浏览器 / curl，并在反向代理里启用 mTLS，把客户端证书信息转成 `X-Client-Cert` 头给后端验证。

3) 运行服务（每个新终端一个进程）：
```
# 认证服务器 (默认端口 5000)
FLASK_APP=auth-server/app.py flask run --cert=certs/auth-server.crt --key=certs/auth-server.key -p 5000

# 教务 API (默认端口 5001)
FLASK_APP=academic-api/app.py flask run --cert=certs/academic-api.crt --key=certs/academic-api.key -p 5001

# 云盘 API (默认端口 5002)
FLASK_APP=cloud-api/app.py flask run --cert=certs/cloud-api.crt --key=certs/cloud-api.key -p 5002
```
> Flask 内置 TLS 不支持双向认证，请在需要 mTLS 时用 Nginx/Traefik/Caddy 终止 TLS，并将客户端证书（PEM 或指纹）通过请求头转发给后端，后端会在 `request.headers["X-Client-Cert"]` 检查。

4) hosts 绑定并启动前端（模拟不同站点域名）：
- 在 hosts 添加：`127.0.0.1 auth.localhost academic.localhost cloud.localhost`
- 重新生成服务端证书（SAN 已含上述域名）：`cd certs && ./create_server.sh auth-server` 等
- 启动静态服务器（示例占用 3 个端口，分别映射不同站点）：
```
# 教务前端
cd frontends/academic && python ../https_server.py --ssl-cert ../../certs/academic-api.crt --ssl-key ../../certs/academic-api.key --port 4174
# 云盘前端
cd ../cloud && python ../https_server.py --ssl-cert ../../certs/cloud-api.crt --ssl-key ../../certs/cloud-api.key --port 4176
# 认证门户
cd ../auth && python ../https_server.py --ssl-cert ../../certs/auth-server.crt --ssl-key ../../certs/auth-server.key --port 4173
```
分别打开：
- 教务前端：`http://academic.localhost:4174/academic.html`
- 云盘前端：`http://cloud.localhost:4176/cloud.html`
- 认证门户：`http://auth.localhost:4173/auth.html`
后端 API/认证站点使用 `https://auth.localhost:5000`、`https://academic.localhost:5001`、`https://cloud.localhost:5002`；Cookie 以各自域隔离。

OAuth2.0 & SSO 流程（前端不持有访问令牌）
---------------------------------------
1. 统一认证站点 `/auth/login` 下发 HttpOnly `sso_session`（SameSite=None; Secure）。
2. 业务前端点击“前往登录”直接跳转后端 `/session/login`，后端 302 到认证门户（`AUTH_PORTAL`，默认 `frontends/auth/auth.html`），携带 `next=<authorize_url>`；登录成功后门户自动跳转到 `next`，再由认证站点签发授权码并回调 `/session/callback`。
3. 业务后端用授权码向认证站点换取 access/refresh token，并将其保存在后端内存；同时为该站点设置自己的 HttpOnly 会话 Cookie（如 `academic_session`、`cloud_session`）。
4. 业务前端后续请求只带站点的会话 Cookie（credentials: include），不暴露 access token 到浏览器。
5. 资源服务器在每次请求时调用认证站点 `/auth/validate` 验证访问令牌；过期时后端使用 refresh token 静默续期。

证书与 TLS 演示
---------------
- **单向认证**：前端需信任 `ca.crt`，通过 HTTPS 连接各站点，浏览器验证服务器证书链。
- **双向认证**：使用 `create_client.sh <user>` 为用户签发证书，导入浏览器/curl。由反向代理启用 `ssl_verify_client on;` 等配置，验证通过后把客户端证书（或 SHA256 指纹）转发给后端。后端会在登录/令牌验证时比对与用户绑定的指纹。
- **密钥协商**：使用 TLS 默认握手（ECDHE），脚本使用 OpenSSL 生成的证书+密钥。可用 `openssl s_client -connect localhost:5000` 观测握手。

接口概览
--------
统一认证 (`auth-server/app.py`)
- `POST /auth/register`：注册用户并可上传客户端证书指纹
- `POST /auth/login`：凭用户名密码（可选客户端证书指纹）换取 `session_token`
- `GET /auth/authorize`：校验 session -> 颁发授权码（Authorization Code）
- `POST /auth/token`：用授权码 + 客户端凭证交换访问令牌/刷新令牌
- `POST /auth/validate`：校验访问令牌（可比对客户端证书指纹）
- `POST /ca/issue`：示例接口，返回自建 CA 的颁发信息（不直接发文件）

教务 API (`academic-api/app.py`)
- `POST /exchange`：后台携带 `client_secret` 与认证站点换取访问令牌
- `GET /courses` / `GET /grades`：受保护资源，需 Bearer Token

云盘 API (`cloud-api/app.py`)
- `POST /exchange`：同上
- `GET /files`、`POST /files`：模拟文件列表/上传

前端
- `frontends/auth/auth.html`：登录/授权门户，演示 CA 信任提示
- `frontends/academic/academic.html`：教务站点，登录并查看课程/成绩
- `frontends/cloud/cloud.html`：云盘站点，登录并上传（模拟）文件

演示建议
--------
- 打开浏览器开发者工具观察重定向/令牌存储/认证失败响应。
- 使用 `curl -v --cert client.crt --key client.key https://localhost:5000/auth/validate` 演示 mTLS；若不提供客户端证书，代理会拒绝或后端比对失败。
- 修改 `auth-server/app.py` 中的 `CLIENTS`/`USERS` 可添加新的站点与用户。

安全说明
--------
此项目仅用于教学演示，未考虑生产安全性（明文密钥、内存存储、弱密码散列、缺少 CSRF、防重放等）。请勿直接用于公网环境。
