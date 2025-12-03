import hashlib
import time
import uuid
import os
import subprocess
import json
import urllib.parse

from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import jwt
from flask import Flask, jsonify, request, send_file, redirect
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

# ================= 配置部分 =================
DB_USER = os.environ.get("DB_USER", "academic_user")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "academic")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "academic_user@USTB2025")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

app = Flask(__name__)

# JWT 配置
JWT_SECRET = "dev-secret-signing-key"  # 暂时采用简单的字符串，方便调试
ACCESS_EXPIRES_SECONDS = 300
REFRESH_EXPIRES_SECONDS = 3600

ERROR_PAGE = "https://auth.localhost:4173/error.html"
LOGIN_PORTAL = "https://auth.localhost:4173/auth.html"
CONSENT_PORTAL = "https://auth.localhost:4173/consent.html"

# ================= 数据模型 =================
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)

class Certificate(Base):
    __tablename__ = 'certificates'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100))
    serial_number = Column(String(64), unique=True, nullable=False)
    fingerprint = Column(String(64), nullable=False, index=True)
    status = Column(String(20), default='valid') # 'valid' or 'revoked'
    issued_at = Column(DateTime, default=datetime.utcnow)

class OAuthClient(Base):
    __tablename__ = 'oauth_clients'
    client_id = Column(String(40), primary_key=True)
    client_secret = Column(String(80), nullable=False)
    name = Column(String(80), nullable=False)
    redirect_uris = Column(Text, nullable=False)
    scopes = Column(Text, nullable=False)

    def get_redirect_uris(self):
        return json.loads(self.redirect_uris)

    def get_scopes(self):
        try:
            return json.loads(self.scopes)
        except:
            return []

def get_db():
    return SessionLocal()

# 内存缓存 (仅用于 OAuth 临时流程)
SESSIONS = {}
AUTH_CODES = {}
REFRESH_TOKENS = {} # 生产环境建议也存库，演示环境暂存内存

# ================= 辅助函数 =================
def _fingerprint_from_headers():
    """Extract client certificate fingerprint from request headers (added by TLS terminator)."""
    fp = request.headers.get("X-Client-Cert-Fingerprint")
    if fp: return fp.lower()
    return None

def _cors(resp):
    origin = request.headers.get("Origin")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Session-Token,X-Client-Cert,X-Client-Cert-Fingerprint"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp

@app.after_request
def add_cors(resp): return _cors(resp)

# ================= 核心路由 =================

def init_db():
    """启动自动初始化：建表 + 预置完整数据"""
    print("[db_init] 正在检查数据库状态...")
    
    # 1. 自动建表 (如果表不存在)
    # 这会创建 users, certificates, oauth_clients 三张表
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        # ==================== 初始化 OAuth 客户端 ====================
        # 检查是否已有数据
        if not session.query(OAuthClient).filter_by(client_id="academic-app").first():
            print("[db_init] 正在写入默认 OAuth 客户端数据...")
            
            # 注意：这里的 JSON 字符串必须是完整的，不能有省略号
            clients = [
                OAuthClient(
                    client_id="academic-app",
                    client_secret="academic-secret",
                    name="教务信息站点",
                    # 关键修复：确保这里是完整的 JSON 数组字符串
                    redirect_uris='["https://academic.localhost:4174/academic.html#callback", "https://academic.localhost:5001/session/callback"]',
                    scopes='["courses.read", "grades.read"]'
                ),
                OAuthClient(
                    client_id="cloud-app",
                    client_secret="cloud-secret",
                    name="云盘站点",
                    redirect_uris='["https://cloud.localhost:4176/cloud.html#callback", "https://cloud.localhost:5002/session/callback"]',
                    scopes='["files.read", "files.write"]'
                )
            ]
            session.add_all(clients)
            print("[db_init] 默认客户端 (教务/云盘) 已写入")

        # ==================== 初始化默认用户 ====================
        print("⏳ 正在检查默认用户数据...")
        
        # 定义要预置的用户列表
        default_pwd_hash = generate_password_hash("password123")
        default_users = [
            {"username": "alice", "role": "student"},
            {"username": "bob", "role": "student"},
            {"username": "teacher", "role": "teacher"}
        ]

        for u_data in default_users:
            # 逐个检查，谁不在就补谁
            if not session.query(User).filter_by(username=u_data["username"]).first():
                print(f"   + 添加用户: {u_data['username']}")
                new_user = User(
                    username=u_data["username"], 
                    password_hash=default_pwd_hash, 
                    role=u_data["role"]
                )
                session.add(new_user)
            else:
                print(f"   - 用户已存在: {u_data['username']}")

        # 提交所有更改
        session.commit()
        print("[db_init] 数据库初始化完成！系统已就绪。")

    except Exception as e:
        session.rollback()
        print(f"[db_init] 初始化失败: {str(e)}")
    finally:
        session.close()

# 登陆
@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    session = get_db()
    user = session.query(User).filter_by(username=username).first()
    
    # 1. 验证密码 (哈希比对)
    if not user:
        session.close()
        return jsonify({"error": "no userser found\nplease check your username"}), 401

    if not check_password_hash(user.password_hash, password):
        session.close()
        return jsonify({"error": "wrong password"}), 401

    # 2. 验证证书 (双向认证逻辑 Task 3/4)
    request_fp = _fingerprint_from_headers()
    if request_fp:
        # 查找该指纹是否存在且属于该用户
        cert = session.query(Certificate).filter_by(fingerprint=request_fp).first()
        if cert:
            if cert.user_id != user.id:
                session.close()
                return jsonify({"error": "Certificate does not belong to this user"}), 403
            if cert.status == 'revoked':
                session.close()
                return jsonify({"error": "Certificate has been REVOKED"}), 403
        else:
            # 指纹存在但数据库没记录（可能是未登记的证书），根据策略可以选择放行或拦截
            # 这里为了演示简单，如果没找到证书记录，暂时放行（弱校验）
            # 实际工程中，应该选择白名单策略
            # session.close()
            # return jsonify({"error": "Unknown certificate! Please register first."}), 403
            pass

    session.close()

    session_token = str(uuid.uuid4())
    SESSIONS[session_token] = {
        "username": username,
        "role": user.role,
        "issued_at": time.time(),
        "fingerprint": request_fp
    }
    
    resp = jsonify({"session_token": session_token, "username": username, "role": user.role})
    resp.set_cookie("sso_session", session_token, httponly=True, secure=True, samesite="None", max_age=3600)
    return resp

# 登出
@app.route("/auth/logout", methods=["POST"])
def session_logout():
    session_token = request.cookies.get("sso_session")
    if session_token in SESSIONS:
        SESSIONS.pop(session_token, None)
    resp = jsonify({"message": "sso logged out"})
    # 使用与登录时相同的属性删除 cookie，确保跨站注销生效
    resp.set_cookie(
        "sso_session",
        "",
        expires=0,
        httponly=True,
        secure=True,
        samesite="None",
        domain=request.host.split(":")[0],
    )
    return resp
    
#注册
@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "student")
    
    if not username or not password:
        return jsonify({"error": "missing fields"}), 400
        
    session = get_db()
    if session.query(User).filter_by(username=username).first():
        session.close()
        return jsonify({"error": "user exists"}), 409
        
    new_user = User(username=username, password_hash=generate_password_hash(password), role=role)
    session.add(new_user)
    session.commit()
    session.close()
    
    return jsonify({"message": "registered"}), 201

# Task 3: 证书生成接口
@app.route("/ca/issue", methods=["POST"])
def ca_issue():
    # 1. 鉴权：需要登录
    session_token = request.cookies.get("sso_session")
    sso_data = SESSIONS.get(session_token)
    if not sso_data: return jsonify({"error": "Unauthorized"}), 401
    
    username = sso_data["username"]
    
    # 2. 路径配置 (使用绝对路径)
    # 获取当前文件 app.py 的上一级目录 (项目根目录)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    certs_dir = os.path.join(base_dir, "certs")
    script_path = os.path.join(certs_dir, "create_client.sh")
    
    try:
        # 3. 调用 Shell 脚本生成 .key 和 .crt
        # 注意：脚本里虽然没生成 p12，但生成了 key 和 crt，这正是我们需要的
        subprocess.run(
            ["bash", script_path, username], 
            cwd=certs_dir, 
            check=True, 
            capture_output=True # 防止脚本输出干扰 Flask
        )
        
        # 定义文件路径
        key_path = os.path.join(certs_dir, f"{username}.key")
        crt_path = os.path.join(certs_dir, f"{username}.crt")
        p12_path = os.path.join(certs_dir, f"{username}.p12")

        # 4. [新增] Python 补救措施：手动调用 OpenSSL 生成 .p12 文件
        # 因为 Shell 脚本没做这步，我们在 Python 里做
        # -passout pass:password123 设置导出密码，防止浏览器导入时报错
        if not os.path.exists(p12_path):
            subprocess.run(
                [
                    "openssl", "pkcs12", "-export",
                    "-inkey", f"{username}.key",
                    "-in", f"{username}.crt",
                    "-name", username,
                    "-out", f"{username}.p12",
                    "-passout", "pass:password123" 
                ],
                cwd=certs_dir,
                check=True
            )

        # 5. 读取指纹 (用于存数据库)
        res = subprocess.run(
            ["openssl", "x509", "-noout", "-fingerprint", "-sha256", "-in", crt_path],
            capture_output=True, text=True, check=True
        )
        # 解析输出: SHA256 Fingerprint=AA:BB...
        fp_str = res.stdout.strip().split("=")[1].replace(":", "").lower()
        
        # 6. 读取序列号 (用于存数据库)
        res_serial = subprocess.run(
            ["openssl", "x509", "-noout", "-serial", "-in", crt_path],
            capture_output=True, text=True, check=True
        )
        serial = res_serial.stdout.strip().split("=")[1]
        
        # 7. 存入数据库
        session = get_db()
        user = session.query(User).filter_by(username=username).first()
        
        # 检查是否已存在，不存在则插入
        if not session.query(Certificate).filter_by(serial_number=serial).first():
            new_cert = Certificate(
                user_id=user.id,
                name=f"{username} Personal Cert",
                serial_number=serial,
                fingerprint=fp_str,
                status='valid'
            )
            session.add(new_cert)
            session.commit()
        session.close()
        
        # 8. 返回文件下载
        return send_file(p12_path, as_attachment=True, mimetype="application/x-pkcs12", download_name=f"{username}.p12")
        
    except Exception as e:
        # 打印详细错误方便调试
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Issue failed: {str(e)}", "path": certs_dir}), 500

# Task 3: 证书列表接口
@app.route("/certs", methods=["GET"])
def list_certs():
    session_token = request.cookies.get("sso_session")
    sso_data = SESSIONS.get(session_token)
    if not sso_data: return jsonify({"error": "Unauthorized"}), 401
    
    username = sso_data["username"]
    session = get_db()
    user = session.query(User).filter_by(username=username).first()
    certs = certs = session.query(Certificate).filter_by(user_id=user.id, status='valid').all()
    
    data = [{
        "id": c.id,
        "name": c.name,
        "serial": c.serial_number,
        "fingerprint": c.fingerprint,
        "status": c.status,
        "issued_at": c.issued_at.isoformat()
    } for c in certs]
    session.close()
    return jsonify(data)

# Task 3: 证书撤销接口
@app.route("/api/cert/revoke", methods=["POST"])
def revoke_cert():
    session_token = request.cookies.get("sso_session")
    sso_data = SESSIONS.get(session_token)
    if not sso_data: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    cert_id = data.get("id")
    
    session = get_db()
    user = session.query(User).filter_by(username=sso_data["username"]).first()
    cert = session.query(Certificate).filter_by(id=cert_id, user_id=user.id).first()
    
    if cert:
        cert.status = 'revoked'
        session.commit()
        session.close()
        return jsonify({"message": "Revoked"})
    
    session.close()
    return jsonify({"error": "Not found"}), 404

# ================= OAuth 流程 (适配 DB) =================

# 客户端认证，用户请求code
@app.route("/auth/authorize", methods=["GET"])
def authorize():
    # 1. 基础参数获取
    session_token = request.headers.get("X-Session-Token") or request.cookies.get("sso_session")
    client_id = request.args.get("client_id")
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state", "")
    
    # 2. 检查登录 (未登录则去登录页)
    session_data = SESSIONS.get(session_token)
    if not session_data:
        next_url = quote_plus(request.url)
        return "", 302, {"Location": f"{LOGIN_PORTAL}?next={next_url}"}
        
    # 3. 检查客户端合法性
    db = get_db()
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    db.close()
    
    if not client: 
        return redirect(f"{FRONT_URL}?error={quote('非法的应用ID (invalid client)')}")
    
    # 4. 检查回调地址
    valid_uris = client.get_redirect_uris()
    if redirect_uri not in valid_uris:
        return redirect(f"{FRONT_URL}?error={quote('非法的回调地址 (invalid redirect_uri)')}")

    # === 改动重点在这里 ===
    # 5. 不再直接发 Code，而是跳转到确认页面
    # 把参数传给前端页面去展示
    params = {
        "client_id": client_id,
        "client_name": client.name,
        "redirect_uri": redirect_uri,
        "scope": client.scopes, # 把权限范围传过去
        "state": state
    }
    query_string = urllib.parse.urlencode(params)
    
    # 跳转到 consent.html
    return "", 302, {"Location": f"{CONSENT_PORTAL}?{query_string}"}

@app.route("/auth/approve", methods=["POST"])
def approve_consent():
    # 1. 验证用户登录
    session_token = request.cookies.get("sso_session")
    session_data = SESSIONS.get(session_token)
    if not session_data: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    
    # 2. 获取参数 (前端传回来的)
    client_id = data.get("client_id")
    redirect_uri = data.get("redirect_uri")
    state = data.get("state", "")
    allow = data.get("allow")
    
    if not allow:
        return jsonify({"error": "access_denied"}), 400

    # 3. 再次简单校验客户端 (防止伪造请求)
    db = get_db()
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    db.close()
    
    if not client: return jsonify({"error": "invalid client"}), 400
    valid_uris = client.get_redirect_uris()
    if redirect_uri not in valid_uris:
        return jsonify({"error": "invalid redirect_uri"}), 400

    # 4. 生成授权码 (真正的发证时刻)
    code = str(uuid.uuid4())
    AUTH_CODES[code] = {
        "username": session_data["username"],
        "client_id": client_id,
        "expires_at": time.time() + 300,
        "fingerprint": session_data.get("fingerprint"),
    }
    
    # 5. 返回跳转地址给前端，让前端 JS 执行跳转
    # 最终地址：https://academic.../callback?code=...&state=...
    final_redirect = f"{redirect_uri}?code={code}&state={state}"
    return jsonify({"redirect": final_redirect})

# 处理访问票据的申请
@app.route("/auth/token", methods=["POST"])
def token():
    data = request.get_json() or {}
    grant_type = data.get("grant_type")
    client_id = data.get("client_id")
    client_secret = data.get("client_secret")

    db = get_db()
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    db.close()
    
    if not client or client.client_secret != client_secret:
        return jsonify({"error": "invalid client credentials"}), 401

    client_scopes = client.get_scopes()
    
    if grant_type == "authorization_code":
        code = data.get("code")
        code_data = AUTH_CODES.pop(code, None)
        if not code_data or code_data["expires_at"] < time.time():
            return jsonify({"error": "invalid code"}), 400
            
        return _issue_tokens(code_data["username"], client_id, code_data.get("fingerprint"), client_scopes)
        
    if grant_type == "refresh_token":
        rt = data.get("refresh_token")
        stored = REFRESH_TOKENS.get(rt)
        if not stored or stored["exp"] < time.time():
            return jsonify({"error": "invalid refresh_token"}), 401
        saved_scope = stored.get("scope") or client_scopes
        return _issue_tokens(stored["username"], client_id, stored.get("fingerprint"), saved_scope)

    return jsonify({"error": "unsupported grant_type"}), 400

# 生成一个票据(access_token) ，并生成更新这个票据的票据(refresh_token)
def _issue_tokens(username, client_id, fingerprint=None, scopes=None):
    # 保证令牌内包含角色，便于下游展示权限
    db = get_db()
    user = db.query(User).filter_by(username=username).first()
    role = user.role if user else None
    db.close()

    now = datetime.now(timezone.utc)
    exp_ts = int((now + timedelta(seconds=ACCESS_EXPIRES_SECONDS)).timestamp())
    payload = {
        "sub": username,
        "client_id": client_id,
        "iat": int(now.timestamp()),
        "exp": exp_ts,
        "scope": scopes or [],
    }
    if fingerprint:
        payload["fp"] = fingerprint
    if role:
        payload["role"] = role
    
    access_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    refresh_token = str(uuid.uuid4())
    REFRESH_TOKENS[refresh_token] = {
        "username": username,
        "client_id": client_id,
        "exp": time.time() + REFRESH_EXPIRES_SECONDS,
        "fingerprint": fingerprint,
        "scope": scopes or [],
        "role": role,
    }
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": ACCESS_EXPIRES_SECONDS,
        "username": username,
        "role": role,
        "scope": scopes or []
    })

# 验证票据是否有效
@app.route("/auth/validate", methods=["POST"])
def validate():
    auth_header = request.headers.get("Authorization", "")
    fingerprint = _fingerprint_from_headers()
    if not auth_header.startswith("Bearer "): return jsonify({"error": "missing token"}), 401
    
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception: return jsonify({"error": "invalid token"}), 401

    # 双向认证指纹校验 (Task 4/Task 3)
    if payload.get("fp") and fingerprint != payload.get("fp"):
        return jsonify({"error": "client certificate mismatch"}), 401
        
    # 如果绑定了证书，还需要检查证书是否被撤销
    if payload.get("fp"):
        session = get_db()
        cert = session.query(Certificate).filter_by(fingerprint=payload.get("fp")).first()
        session.close()
        if cert and cert.status == 'revoked':
            return jsonify({"error": "Certificate REVOKED"}), 401

    return jsonify({
        "active": True,
        "username": payload["sub"],
        "client_id": payload["client_id"],
        "scope": payload.get("scope", []),
        "role": payload.get("role")
    })

@app.route("/auth/session", methods=["GET"])
def session_status():
    session_token = request.cookies.get("sso_session")
    session = SESSIONS.get(session_token)
    if not session: return jsonify({"active": False}), 401
    return jsonify({"active": True, "username": session["username"], "role": session.get("role")})

# 相当于ping，确认此服务器是否正在工作
@app.route("/health", methods=["GET"])
def health(): return jsonify({"status": "ok"})

try:
    print("[init_db] 正在启动自动初始化...")
    init_db()
except Exception as e:
    print(f"[init_db] 初始化警告: {e}")

if __name__ == "__main__":
    # 确保 certs 目录存在
    if not os.path.exists("certs"): os.makedirs("certs")
    app.run(debug=True, port=5000, ssl_context=("certs/auth-server.crt", "certs/auth-server.key"))
