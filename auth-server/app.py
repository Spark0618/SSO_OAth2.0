import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask, jsonify, request

app = Flask(__name__)


# Demo-only secrets/backing store (in-memory for simplicity)
JWT_SECRET = "dev-secret-signing-key"
ACCESS_EXPIRES_SECONDS = 300
REFRESH_EXPIRES_SECONDS = 3600

CLIENTS = {
    "academic-app": {
        "name": "教务信息站点",
        "client_secret": "academic-secret",
        "redirect_uri": "https://localhost:4173/academic.html#callback",
        "scopes": ["courses.read", "grades.read"],
    },
    "cloud-app": {
        "name": "云盘站点",
        "client_secret": "cloud-secret",
        "redirect_uri": "https://localhost:4173/cloud.html#callback",
        "scopes": ["files.read", "files.write"],
    },
}

USERS = {
    "alice": {
        "password": "password123",
        "cert_fingerprint": None,
    },
    "bob": {
        "password": "password123",
        "cert_fingerprint": None,
    },
}

AUTH_CODES = {}
SESSIONS = {}
REFRESH_TOKENS = {}


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
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Session-Token,X-Client-Cert,X-Client-Cert-Fingerprint"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.after_request
def add_cors(resp):
    return _cors(resp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    cert_fp = data.get("cert_fingerprint") or _fingerprint_from_headers()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if username in USERS:
        return jsonify({"error": "user exists"}), 409
    USERS[username] = {"password": password, "cert_fingerprint": cert_fp}
    return jsonify({"message": "registered", "username": username, "cert_fingerprint": cert_fp}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "missing credentials"}), 400
    user = USERS.get(username)
    if not user or user["password"] != password:
        return jsonify({"error": "invalid credentials"}), 401

    request_fp = _fingerprint_from_headers()
    # Enforce mTLS if user bound to a certificate
    if user.get("cert_fingerprint") and user["cert_fingerprint"] != request_fp:
        return jsonify({"error": "client certificate mismatch"}), 401

    session_token = str(uuid.uuid4())
    SESSIONS[session_token] = {"username": username, "issued_at": time.time(), "fingerprint": request_fp}
    return jsonify({"session_token": session_token, "username": username})


@app.route("/auth/authorize", methods=["GET"])
def authorize():
    session_token = request.headers.get("X-Session-Token")
    client_id = request.args.get("client_id")
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state", "")
    response_type = request.args.get("response_type", "code")
    if response_type != "code":
        return jsonify({"error": "unsupported response_type"}), 400
    session = SESSIONS.get(session_token)
    if not session:
        return jsonify({"error": "invalid session"}), 401
    client = CLIENTS.get(client_id)
    if not client or client["redirect_uri"] != redirect_uri:
        return jsonify({"error": "invalid client"}), 400

    code = str(uuid.uuid4())
    AUTH_CODES[code] = {
        "username": session["username"],
        "client_id": client_id,
        "expires_at": time.time() + 300,
        "fingerprint": session.get("fingerprint"),
    }
    redirect = f"{redirect_uri}?code={code}&state={state}"
    return jsonify({"redirect_uri": redirect, "code": code, "client": client["name"]})


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
    return jsonify({"active": True, "username": payload["sub"], "client_id": payload["client_id"]})


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
