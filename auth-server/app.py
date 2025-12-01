import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import jwt
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

DB_USER = "academic_user"
DB_PASSWORD = "academic_user@USTB2025"
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "academic"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

app = Flask(__name__)


# Demo-only secrets/backing store (in-memory for simplicity)
JWT_SECRET = "dev-secret-signing-key"
ACCESS_EXPIRES_SECONDS = 300
REFRESH_EXPIRES_SECONDS = 3600
LOGIN_PORTAL = "https://auth.localhost:4173/auth.html"

CLIENTS = {
    "academic-app": {
        "name": "教务信息站点",
        "client_secret": "academic-secret",
        "redirect_uris": [
            "https://academic.localhost:4174/academic.html#callback",
            "https://academic.localhost:5001/session/callback",
        ],
        "scopes": ["courses.read", "grades.read"],
    },
    "cloud-app": {
        "name": "云盘站点",
        "client_secret": "cloud-secret",
        "redirect_uris": [
            "https://cloud.localhost:4176/cloud.html#callback",
            "https://cloud.localhost:5002/session/callback",
        ],
        "scopes": ["files.read", "files.write"],
    },
}

AUTH_CODES = {}
SESSIONS = {}
REFRESH_TOKENS = {}
CERT_FINGERPRINTS = {}  # username -> fingerprint (仅用于 mTLS 校验，不存数据库)


def get_db_session():
    return SessionLocal()


def _create_user(username: str, password: str, role: str):
    if role not in ("student", "teacher"):
        raise ValueError("invalid role")
    pwd_hash = generate_password_hash(password)
    with get_db_session() as db:
        result = db.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)"),
            {"u": username, "p": pwd_hash, "r": role},
        )
        db.commit()
        return result.lastrowid


def _ensure_profile_for_role(user_id: int, username: str, role: str):
    """Create placeholder student/teacher profile so后续接口可用。"""
    with get_db_session() as db:
        if role == "student":
            db.execute(
                text(
                    """
                    INSERT IGNORE INTO students (user_id, name, student_no, gender, hometown, grade, college, major)
                    VALUES (:uid, :name, :stu_no, '', '', '', '', '')
                    """
                ),
                {"uid": user_id, "name": username, "stu_no": username},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT IGNORE INTO teachers (user_id, name, employee_no, title, department)
                    VALUES (:uid, :name, :emp_no, '', '')
                    """
                ),
                {"uid": user_id, "name": username, "emp_no": username},
            )
        db.commit()


def _get_user(username: str):
    with get_db_session() as db:
        row = db.execute(
            text("SELECT id, username, password_hash, role FROM users WHERE username = :u LIMIT 1"),
            {"u": username},
        ).mappings().first()
        return row


def _fingerprint_from_headers():
    """Extract client certificate fingerprint from request headers (added by TLS terminator)."""
    fp = request.headers.get("X-Client-Cert-Fingerprint")
    if fp:
        return fp.lower()
    pem = request.headers.get("X-Client-Cert")
    if pem:
        return hashlib.sha256(pem.encode("utf-8")).hexdigest()
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
def add_cors(resp):
    return _cors(resp)


@app.route("/<path:_any>", methods=["OPTIONS"])
def options_passthrough(_any):
    """Handle CORS preflight."""
    return _cors(jsonify({}))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "student")
    cert_fp = data.get("cert_fingerprint") or _fingerprint_from_headers()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    try:
        user_id = _create_user(username, password, role)
        _ensure_profile_for_role(user_id, username, role)
    except ValueError:
        return jsonify({"error": "invalid role, must be student or teacher"}), 400
    except IntegrityError:
        return jsonify({"error": "user exists"}), 409
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500
    CERT_FINGERPRINTS[username] = cert_fp
    return (
        jsonify({"message": "registered", "username": username, "role": role, "cert_fingerprint": cert_fp}),
        201,
    )


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "missing credentials"}), 400
    user_row = _get_user(username)
    if not user_row or not check_password_hash(user_row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    request_fp = _fingerprint_from_headers()
    # Enforce mTLS if user bound to a certificate
    bound_fp = CERT_FINGERPRINTS.get(username)
    if bound_fp and bound_fp != request_fp:
        return jsonify({"error": "client certificate mismatch"}), 401

    session_token = str(uuid.uuid4())
    SESSIONS[session_token] = {
        "username": username,
        "role": user_row["role"],
        "issued_at": time.time(),
        "fingerprint": request_fp,
    }
    resp = jsonify({"session_token": session_token, "username": username})
    # HttpOnly cookie for browser-based SSO; requires HTTPS + SameSite=None for cross-site
    resp.set_cookie(
        "sso_session",
        session_token,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=3600,
        domain=request.host.split(":")[0],
    )
    return resp


@app.route("/auth/authorize", methods=["GET"])
def authorize():
    session_token = request.headers.get("X-Session-Token") or request.cookies.get("sso_session")
    client_id = request.args.get("client_id")
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state", "")
    response_type = request.args.get("response_type", "code")
    if response_type != "code":
        return jsonify({"error": "unsupported response_type"}), 400
    session = SESSIONS.get(session_token)
    if not session:
        # If not logged in, redirect to login portal with next parameter
        next_url = quote_plus(request.url)
        return "", 302, {"Location": f"{LOGIN_PORTAL}?next={next_url}"}
    client = CLIENTS.get(client_id)
    if not client or redirect_uri not in client.get("redirect_uris", []):
        return jsonify({"error": "invalid client"}), 400

    code = str(uuid.uuid4())
    AUTH_CODES[code] = {
        "username": session["username"],
        "role": session.get("role"),
        "client_id": client_id,
        "expires_at": time.time() + 300,
        "fingerprint": session.get("fingerprint"),
    }
    redirect = f"{redirect_uri}?code={code}&state={state}"
    return "", 302, {"Location": redirect}


def _issue_tokens(username, client_id, fingerprint=None):
    # datetime.utcnow().timestamp()  
    # .timestamp() 会将没有时区信息的UTC时间当作本地时间来处理，导致时区问题，所以改用下面的写法
    now = datetime.now(timezone.utc)
    exp_ts = int((now + timedelta(seconds=ACCESS_EXPIRES_SECONDS)).timestamp())
    access_payload = {
        "sub": username,
        "client_id": client_id,
        "iat": int(now.timestamp()),
        "exp": exp_ts,
    }
    if fingerprint:
        access_payload["fp"] = fingerprint
    # 可将角色嵌入令牌，供下游做细粒度授权（可选）
    user_row = _get_user(username)
    if user_row and user_row.get("role"):
        access_payload["role"] = user_row["role"]
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")

    refresh_token = str(uuid.uuid4())
    REFRESH_TOKENS[refresh_token] = {
        "username": username,
        "client_id": client_id,
        "exp": time.time() + REFRESH_EXPIRES_SECONDS,
        "fingerprint": fingerprint,
    }
    return access_token, refresh_token, exp_ts


@app.route("/auth/token", methods=["POST"])
def token():
    data = request.get_json() or {}
    grant_type = data.get("grant_type", "authorization_code")
    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    client = CLIENTS.get(client_id)
    if not client or client["client_secret"] != client_secret:
        return jsonify({"error": "invalid client credentials"}), 401

    if grant_type == "authorization_code":
        code = data.get("code")
        if not code or code not in AUTH_CODES:
            return jsonify({"error": "invalid code"}), 400
        code_data = AUTH_CODES.pop(code)
        if code_data["client_id"] != client_id or code_data["expires_at"] < time.time():
            return jsonify({"error": "code expired or client mismatch"}), 400
        access_token, refresh_token, expires_at = _issue_tokens(
            code_data["username"], client_id, code_data.get("fingerprint")
        )
        return jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_EXPIRES_SECONDS,
                "expires_at": expires_at,
                "username": code_data["username"],
            }
        )

    if grant_type == "refresh_token":
        rt = data.get("refresh_token")
        stored = REFRESH_TOKENS.get(rt)
        if not stored or stored["exp"] < time.time():
            return jsonify({"error": "invalid refresh_token"}), 401
        access_token, refresh_token, expires_at = _issue_tokens(
            stored["username"], stored["client_id"], stored.get("fingerprint")
        )
        return jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_EXPIRES_SECONDS,
                "expires_at": expires_at,
                "username": stored["username"],
            }
        )

    return jsonify({"error": "unsupported grant_type"}), 400


@app.route("/auth/validate", methods=["POST"])
def validate():
    auth_header = request.headers.get("Authorization", "")
    fingerprint = _fingerprint_from_headers()
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "missing token"}), 401
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "invalid token"}), 401

    # Optional mTLS binding
    if payload.get("fp") and fingerprint != payload.get("fp"):
        return jsonify({"error": "client certificate mismatch"}), 401
    resp_data = {"active": True, "username": payload["sub"], "client_id": payload["client_id"]}
    if payload.get("role"):
        resp_data["role"] = payload["role"]
    return jsonify(resp_data)


@app.route("/auth/session", methods=["GET"])
def session_status():
    session_token = request.cookies.get("sso_session")
    session = SESSIONS.get(session_token)
    if not session:
        return jsonify({"active": False}), 401
    return jsonify({"active": True, "username": session["username"]})


@app.route("/ca/issue", methods=["POST"])
def ca_issue():
    data = request.get_json() or {}
    subject = data.get("subject", "CN=demo-user")
    return jsonify(
        {
            "message": "Use scripts in certs/ to issue certificates with the local CA.",
            "subject": subject,
            "ca_cert_path": "../certs/ca.crt",
            "note": "Actual signing should happen via openssl; this endpoint is informational only.",
        }
    )


@app.route("/certs", methods=["GET"])
def certs():
    """List users with stored certificate fingerprints for admin UI."""
    return jsonify({u: {"cert_fingerprint": d.get("cert_fingerprint")} for u, d in USERS.items()})


if __name__ == "__main__":
    app.run(debug=True, port=5000, ssl_context=("certs/auth-server.crt", "certs/auth-server.key"))
