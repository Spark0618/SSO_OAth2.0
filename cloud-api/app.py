import os
import time
import uuid
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

AUTH_SERVER = os.environ.get("AUTH_SERVER", "https://auth.localhost:5000")
CLIENT_ID = "cloud-app"
CLIENT_SECRET = "cloud-secret"
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "certs/ca.crt")
FRONT_URL = os.environ.get("FRONT_URL", "https://cloud.localhost:4176/cloud.html")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "https://cloud.localhost:5002/session/callback")
AUTH_PORTAL = os.environ.get("AUTH_PORTAL", "https://auth.localhost:4173/auth.html")

# 真实文件存储目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # app.py 所在目录
DEFAULT_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 示例文件列表：带 owner / 分享 / 是否二进制
FILES = [
    {
        "id": "demo-1",
        "name": "通告.txt",
        "size": "2KB",
        "uploaded_at": "2024-06-01",
        "owner": "demo",
        "encrypted": False,          # 分享是否带密码
        "share_token": None,
        "share_password": None,
        "share_expires_at": None,
        "is_binary": False,          # 是否真实上传的二进制文件
        "storage_path": None,        # 真文件的磁盘路径
    }
]

SHARES = {}   # token -> 分享记录
SESSIONS = {} # session_id -> token 信息

app = Flask(__name__)


# ========= CORS =========
@app.after_request
def add_cors_headers(response):
    """添加CORS头部"""
    # 允许的来源列表
    allowed_origins = [
        "https://cloud.localhost:4176",
        "https://auth.localhost:4173",
        "https://auth.localhost:5000",
        "http://localhost:4176",
        "http://localhost:5000",
        "http://127.0.0.1:4176",
        "http://127.0.0.1:5000"
    ]
    
    origin = request.headers.get('Origin')
    
    if origin and origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    elif origin and origin.endswith('.localhost:4176'):
        # 允许所有localhost:4176的子域名
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        # 生产环境应该更严格，开发环境可以暂时使用*
        response.headers['Access-Control-Allow-Origin'] = '*'
    
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = (
        'Content-Type, Authorization, X-Session-Token, '
        'X-Client-Cert, X-Client-Cert-Fingerprint, '
        'Origin, Accept, X-Requested-With'
    )
    response.headers['Access-Control-Expose-Headers'] = (
        'Content-Length, Content-Range, Content-Disposition'
    )
    response.headers['Access-Control-Max-Age'] = '86400'  # 24小时
    
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "cloud-api ok"})


# ========= OAuth2 相关 =========
def _exchange_code(code):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    try:
        resp = requests.post(
            f"{AUTH_SERVER}/auth/token",
            json=payload,
            timeout=3,
            verify=CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else False,
        )
    except requests.RequestException as exc:
        # 网络错误 / SSL 错误（包括你之前遇到的 SSLError）都会到这
        return None, {
            "error": "auth server unreachable",
            "detail": str(exc),
        }

    # 尝试解析 JSON，失败就给个空字典
    try:
        data = resp.json()
    except ValueError:
        data = {}

    if resp.status_code != 200:
        # 不再抛异常，而是把错误当成“业务错误”传回去
        return None, data or {"error": f"auth server error", "status": resp.status_code}

    # 防止缺少字段导致 KeyError
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token or not refresh_token:
        return None, {
            "error": "invalid token response from auth server",
            "data": data,
        }

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "exp": int(time.time()) + data.get("expires_in", 300),
        "username": data.get("username"),
    }, None


def _refresh(refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    try:
        resp = requests.post(
            f"{AUTH_SERVER}/auth/token",
            json=payload,
            timeout=3,
            verify=CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else False,
        )
    except requests.RequestException:
        return None

    try:
        data = resp.json()
    except ValueError:
        return None

    if resp.status_code != 200:
        return None

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token or not refresh_token:
        return None

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "exp": int(time.time()) + data.get("expires_in", 300),
    }



def _validate_token():
    """从 cookie 取 cloud_session，校验并刷新 token。"""
    session_id = request.cookies.get("cloud_session")
    sess = SESSIONS.get(session_id)
    if not sess:
        return None, ("unauthorized", 401)

    # 过期自动刷新
    if sess["exp"] < time.time():
        refreshed = _refresh(sess["refresh_token"])
        if not refreshed:
            return None, ("session expired", 401)
        sess.update(refreshed)
        SESSIONS[session_id] = sess

    headers = {"Authorization": f"Bearer {sess['access_token']}"}
    fp = request.headers.get("X-Client-Cert-Fingerprint")
    if fp:
        headers["X-Client-Cert-Fingerprint"] = fp

    try:
        resp = requests.post(
            f"{AUTH_SERVER}/auth/validate",
            headers=headers,
            timeout=3,
            verify=CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else False,
        )
    except requests.exceptions.SSLError:
        return None, ("TLS validation failed (trust CA)", 502)
    except requests.RequestException as exc:
        return None, (f"auth server unreachable: {exc}", 502)

    if resp.status_code != 200:
        return None, (resp.json(), resp.status_code)
    return resp.json(), None


# ========= Session & 登录 =========
@app.route("/session/login", methods=["GET"])
def session_login():
    auth_url = (
        f"{AUTH_SERVER}/auth/authorize"
        f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={CALLBACK_URL}&state=cloud"
    )
    login_url = f"{AUTH_PORTAL}?next={requests.utils.quote(auth_url)}"
    return "", 302, {"Location": login_url}


@app.route("/session/callback", methods=["GET"])
def session_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "missing code"}), 400
    token_data, err = _exchange_code(code)
    if err:
        return jsonify({"error": err}), 401

    session_id = str(int(time.time())) + "-" + os.urandom(6).hex()
    SESSIONS[session_id] = token_data

    resp = jsonify({"message": "login success"})
    resp.set_cookie(
        "cloud_session",
        session_id,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=3600,
        domain=request.host.split(":")[0],
    )
    resp.status_code = 302
    resp.headers["Location"] = FRONT_URL
    return resp


@app.route("/session/status", methods=["GET"])
def session_status():
    session_id = request.cookies.get("cloud_session")
    if session_id in SESSIONS:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False}), 401


@app.route("/session/logout", methods=["POST"])
def session_logout():
    session_id = request.cookies.get("cloud_session")
    SESSIONS.pop(session_id, None)
    resp = jsonify({"message": "logged out"})
    resp.set_cookie(
        "cloud_session",
        "",
        expires=0,
        httponly=True,
        secure=True,
        samesite="None",
        domain=request.host.split(":")[0],
    )
    return resp


# ========= 文件列表 =========
@app.route("/files", methods=["GET"])
def list_files():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")

    user_files = []
    for f in FILES:
        if f.get("owner") == username:
            # 不把存储路径暴露给前端
            public = {k: v for k, v in f.items() if k != "storage_path"}
            user_files.append(public)
    return jsonify({"user": username, "files": user_files})


# ========= 模拟上传（只写元数据，保持原来的 demo） =========
@app.route("/files", methods=["POST"])
def upload_file_demo():
    """
    原来的“模拟上传”接口：
    接收 JSON {name, size}，只生成一条元数据记录。
    """
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")

    payload = request.get_json() or {}
    name = payload.get("name") or f"upload-{len(FILES)+1}.txt"
    size = payload.get("size") or "1KB"
    file_id = f"demo-{int(time.time())}-{len(FILES)+1}"

    new_file = {
        "id": file_id,
        "name": name,
        "size": size,
        "uploaded_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "owner": username,
        "encrypted": False,
        "share_token": None,
        "share_password": None,
        "share_expires_at": None,
        "is_binary": False,
        "storage_path": None,
    }
    FILES.append(new_file)

    user_files = [
        {k: v for k, v in f.items() if k != "storage_path"}
        for f in FILES
        if f.get("owner") == username
    ]
    return jsonify({"message": "uploaded", "files": user_files, "user": username}), 201


# ========= 真实文件上传 =========
@app.route("/files/upload", methods=["POST"])
def upload_file_real():
    """
    真实文件上传：
    - multipart/form-data，字段名：file
    - 将文件保存到 UPLOAD_DIR，并在 FILES 里记录
    """
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")

    if "file" not in request.files:
        return jsonify({"error": "missing file field"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    safe_name = secure_filename(file.filename)
    file_id = f"bin-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    storage_name = f"{file_id}-{safe_name}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)
    file.save(storage_path)

    size_bytes = os.path.getsize(storage_path)
    if size_bytes < 1024:
        size_str = f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes // 1024}KB"
    else:
        size_str = f"{size_bytes // (1024 * 1024)}MB"

    new_file = {
        "id": file_id,
        "name": safe_name,
        "size": size_str,
        "uploaded_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "owner": username,
        "encrypted": False,
        "share_token": None,
        "share_password": None,
        "share_expires_at": None,
        "is_binary": True,
        "storage_path": storage_path,
    }
    FILES.append(new_file)

    user_files = [
        {k: v for k, v in f.items() if k != "storage_path"}
        for f in FILES
        if f.get("owner") == username
    ]
    return jsonify(
        {"message": "file uploaded", "files": user_files, "user": username}
    ), 201


# ========= 真实文件下载 =========
@app.route("/files/download/<file_id>", methods=["GET"])
def download_file(file_id):
    """
    下载真实上传的文件：
    - 需要已登录
    - 只能下载自己上传的 is_binary=True 的文件
    """
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")

    target = next(
        (f for f in FILES if f.get("id") == file_id and f.get("owner") == username),
        None,
    )
    if not target:
        return jsonify({"error": "file not found"}), 404
    if not target.get("is_binary"):
        return jsonify({"error": "this file is not a real uploaded file"}), 400

    storage_path = target.get("storage_path")
    if not storage_path or not os.path.exists(storage_path):
        return jsonify({"error": "file missing on server"}), 410

    return send_file(storage_path, as_attachment=True, download_name=target["name"])


@app.route("/files/share", methods=["POST"])
def share_file():
    """
    为某个文件创建/更新分享链接：
    - 需要登录
    - 只能分享自己的文件
    """
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")

    payload = request.get_json() or {}
    file_id = payload.get("file_id") or payload.get("fileId")
    if not file_id:
        return jsonify({"error": "missing file_id"}), 400

    target = next(
        (f for f in FILES if f.get("id") == file_id and f.get("owner") == username),
        None,
    )
    if not target:
        return jsonify({"error": "file not found or no permission"}), 404

    expire_hours = int(payload.get("expire_hours") or payload.get("expireHours") or 24)
    if expire_hours <= 0:
        expire_hours = 24
    password = payload.get("password") or None

    token = uuid.uuid4().hex
    expire_at = datetime.utcnow() + timedelta(hours=expire_hours)
    created_at = datetime.utcnow()  # 分享创建时间

    # 更新文件记录中的分享信息
    target["share_token"] = token
    target["share_password"] = password
    target["share_expires_at"] = expire_at.isoformat() + "Z"
    target["encrypted"] = bool(password)

    # 保存到SHARES字典
    SHARES[token] = {
        "token": token,
        "file_id": target["id"],
        "owner": username,
        "password": password,
        "expires_at": expire_at,
        "created_at": created_at,  # 保存创建时间
    }

    print(f"✅ 创建分享成功:")
    print(f"  创建时间: {created_at}")
    print(f"  过期时间: {expire_at}")
    print(f"  有效期: {expire_hours}小时")

    # 生成前端分享链接
    frontend_base = "https://cloud.localhost:4176"
    if password:
        share_page_url = f"{frontend_base}/share.html?token={token}&password={password}"
    else:
        share_page_url = f"{frontend_base}/share.html?token={token}"
    
    # 直接下载链接
    direct_download_url = f"https://cloud.localhost:5002/share/{token}/download"
    if password:
        direct_download_url += f"?password={password}"
    
    return jsonify(
        {
            "message": "分享创建成功",
            "share_token": token,
            "share_page_url": share_page_url,
            "direct_download_url": direct_download_url,
            "created_at": created_at.isoformat() + "Z",  # 返回创建时间
            "expires_at": expire_at.isoformat() + "Z",   # 返回过期时间
            "expire_hours": expire_hours,                # 返回有效期（小时）
            "need_password": bool(password),
        }
    )

# ========= 添加全局OPTIONS请求处理器 =========
@app.route("/share/<token>", methods=["OPTIONS"])
def options_share(token):
    """处理/share/<token>的OPTIONS预检请求"""
    response = jsonify({})
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.route("/debug/shares", methods=["GET"])
def debug_shares():
    """调试端点：查看所有分享状态"""
    now = datetime.utcnow()
    shares_info = []
    
    for token, share in SHARES.items():
        file = next((f for f in FILES if f.get("id") == share["file_id"]), None)
        shares_info.append({
            "token": token,
            "file_id": share["file_id"],
            "file_name": file.get("name") if file else "未知",
            "owner": share.get("owner"),
            "has_password": bool(share.get("password")),
            "expires_at": share.get("expires_at").isoformat() if share.get("expires_at") else None,
            "is_expired": share.get("expires_at") < now if share.get("expires_at") else True,
            "created_at": share.get("created_at").isoformat() if share.get("created_at") else None
        })
    
    return jsonify({
        "total_shares": len(SHARES),
        "total_files": len(FILES),
        "current_time": now.isoformat(),
        "shares": shares_info
    })


@app.route("/debug/files", methods=["GET"])
def debug_files():
    """调试端点：查看所有文件"""
    files_info = []
    for f in FILES:
        files_info.append({
            "id": f.get("id"),
            "name": f.get("name"),
            "owner": f.get("owner"),
            "is_binary": f.get("is_binary"),
            "share_token": f.get("share_token"),
            "encrypted": f.get("encrypted"),
            "share_expires_at": f.get("share_expires_at")
        })
    
    return jsonify({
        "total_files": len(FILES),
        "files": files_info
    })



@app.route("/share/<token>", methods=["GET", "OPTIONS"])
def access_share(token):
    """
    分享访问接口（不需要登录）：
    - GET /share/<token>?password=xxx
    - 如果设置了密码，需要带对的密码
    """
    # 如果是OPTIONS请求，直接返回
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    
    print(f"🔍 处理分享请求: token={token}")
    
    share = SHARES.get(token)
    if not share:
        print(f"  ❌ 未找到分享记录: {token}")
        return jsonify({"error": "分享不存在或已失效"}), 404
    
    # 检查是否过期
    if share["expires_at"] < datetime.utcnow():
        print(f"  ❌ 分享已过期: {token}, 过期时间: {share['expires_at']}")
        # 清理过期分享
        SHARES.pop(token, None)
        return jsonify({"error": "分享已过期"}), 410
    
    # 验证密码
    pwd = request.args.get("password") or ""
    if share["password"] and pwd != share["password"]:
        print(f"  ❌ 密码错误: token={token}, 输入密码={pwd}, 正确密码={share['password']}")
        return jsonify({"error": "密码错误"}), 403
    
    # 查找对应的文件
    target = next((f for f in FILES if f.get("id") == share["file_id"]), None)
    if not target:
        print(f"  ❌ 文件不存在: file_id={share['file_id']}")
        return jsonify({"error": "文件不存在"}), 404
    
    print(f"  ✅ 分享验证通过: token={token}, 文件={target.get('name')}")
    
    public = {k: v for k, v in target.items() if k != "storage_path"}
    public["shared_via"] = token
    public["owner"] = share.get("owner", "unknown")
    
    # 添加分享创建时间和格式化
    # 分享创建时间（数据库中的created_at）
    if "created_at" in share:
        public["shared_created_at"] = share["created_at"].isoformat() + "Z"
    else:
        # 兼容旧数据，如果没有创建时间，使用当前时间
        public["shared_created_at"] = datetime.utcnow().isoformat() + "Z"
    
    # 分享过期时间
    public["share_expires_at"] = share["expires_at"].isoformat() + "Z"
    
    # 文件上传时间（保持不变）
    public["uploaded_at"] = target.get("uploaded_at", "")
    
    return jsonify(public)


@app.route("/share/<token>/download", methods=["GET"])
def download_share(token):
    """
    通过分享令牌下载文件：
    - 不需要登录
    - 需要验证分享令牌和密码（如果设置了密码）
    """
    share = SHARES.get(token)
    if not share:
        return jsonify({"error": "分享不存在或已失效"}), 404

    if share["expires_at"] < datetime.utcnow():
        return jsonify({"error": "分享已过期"}), 410

    # 验证密码（从查询参数获取）
    pwd = request.args.get("password") or ""
    if share["password"] and pwd != share["password"]:
        return jsonify({"error": "密码错误"}), 403

    target = next((f for f in FILES if f.get("id") == share["file_id"]), None)
    if not target:
        return jsonify({"error": "文件不存在"}), 404

    storage_path = target.get("storage_path")
    if not storage_path or not os.path.exists(storage_path):
        return jsonify({"error": "文件已从服务器删除"}), 410

    # 检查是否是二进制文件（真实文件）
    if not target.get("is_binary"):
        return jsonify({"error": "此文件不支持直接下载"}), 400

    return send_file(
        storage_path, 
        as_attachment=True, 
        download_name=target["name"]
    )


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5002,
        ssl_context=("certs/cloud-api.crt", "certs/cloud-api.key"),
    )