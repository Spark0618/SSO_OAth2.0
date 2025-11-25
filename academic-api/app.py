import os
import time

import requests
from flask import Flask, jsonify, request

AUTH_SERVER = os.environ.get("AUTH_SERVER", "https://auth.localhost:5000")
CLIENT_ID = "academic-app"
CLIENT_SECRET = "academic-secret"
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "certs/ca.crt")
FRONT_URL = os.environ.get("FRONT_URL", "https://academic.localhost:4174/academic.html")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "https://academic.localhost:5001/session/callback")
AUTH_PORTAL = os.environ.get("AUTH_PORTAL", "https://auth.localhost:4173/auth.html")

COURSES = [
    {"code": "CS101", "title": "程序设计基础", "day": 1, "slot": 1, "location": "一教101", "desc": "C 语言入门与程序设计思想，含上机实验。"},
    {"code": "MATH201", "title": "高等数学", "day": 1, "slot": 2, "location": "一教102", "desc": "微积分与级数，打好数学分析基础。"},
    {"code": "NET300", "title": "计算机网络", "day": 2, "slot": 3, "location": "实验楼305", "desc": "TCP/IP 协议栈、路由与网络安全基础。"},
    {"code": "AI210", "title": "人工智能导论", "day": 3, "slot": 4, "location": "二教202", "desc": "AI 发展概览、搜索、机器学习与应用案例。"},
    {"code": "OS220", "title": "操作系统", "day": 4, "slot": 2, "location": "二教201", "desc": "进程线程、内存管理、文件系统与同步机制。"},
    {"code": "DS150", "title": "数据结构", "day": 5, "slot": 5, "location": "一教201", "desc": "链表、树、图及基本算法分析。"},
]
GRADES = {"CS101": "A", "MATH201": "B+", "NET300": "A-", "AI210": "A", "OS220": "B+", "DS150": "A-"}

PROFILE = {
    "personal": {"name": "张伟", "student_id": "2021123456", "gender": "男", "hometown": "北京"},
    "enrollment": {"grade": "2021级", "college": "计算机与通信工程学院", "major": "计算机科学与技术", "progress": "已修满 85/120 学分"},
}

SESSIONS = {}

app = Flask(__name__)


@app.after_request
def cors(resp):
    origin = request.headers.get("Origin")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Client-Cert,X-Client-Cert-Fingerprint"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "academic-api ok"})


def _exchange_code(code):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    resp = requests.post(
        f"{AUTH_SERVER}/auth/token",
        json=payload,
        timeout=3,
        verify=CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else False,
    )
    if resp.status_code != 200:
        return None, resp.json()
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "exp": int(time.time()) + data.get("expires_in", 300),
        "username": data.get("username"),
    }, None


@app.route("/session/login", methods=["GET"])
def session_login():
    auth_url = (
        f"{AUTH_SERVER}/auth/authorize"
        f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={CALLBACK_URL}&state=academic"
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
    token_data["login_at"] = time.time()
    SESSIONS[session_id] = token_data
    resp = jsonify({"message": "login success"})
    resp.set_cookie(
        "academic_session",
        session_id,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=3600,
        domain=request.host.split(":")[0],
    )
    # Redirect back to front page for UX
    resp.status_code = 302
    resp.headers["Location"] = FRONT_URL
    return resp


@app.route("/session/status", methods=["GET"])
def session_status():
    session_id = request.cookies.get("academic_session")
    sess = SESSIONS.get(session_id)
    if not sess:
        return jsonify({"logged_in": False}), 401
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"logged_in": False, "error": msg}), code
    username = data.get("username") or data.get("user") or sess.get("username")
    if username and not sess.get("username"):
        sess["username"] = username
        SESSIONS[session_id] = sess
    return jsonify({"logged_in": True, "username": username, "login_at": sess.get("login_at")})


@app.route("/session/logout", methods=["POST"])
def session_logout():
    session_id = request.cookies.get("academic_session")
    if session_id in SESSIONS:
        SESSIONS.pop(session_id, None)
    resp = jsonify({"message": "logged out"})
    resp.set_cookie("academic_session", "", expires=0, domain=request.host.split(":")[0])
    return resp


def _refresh(refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    resp = requests.post(
        f"{AUTH_SERVER}/auth/token",
        json=payload,
        timeout=3,
        verify=CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else False,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "exp": int(time.time()) + data.get("expires_in", 300),
    }


def _validate_token():
    session_id = request.cookies.get("academic_session")
    sess = SESSIONS.get(session_id)
    if not sess:
        return None, ("unauthorized", 401)
    # Refresh if token expired
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


@app.route("/courses", methods=["GET"])
def courses():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    return jsonify({"user": data["username"], "courses": COURSES})


@app.route("/grades", methods=["GET"])
def grades():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    return jsonify({"user": data["username"], "grades": GRADES})


@app.route("/profile", methods=["GET"])
def profile():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    return jsonify({"user": data["username"], "profile": PROFILE})


if __name__ == "__main__":
    app.run(debug=True, port=5001, ssl_context=("certs/academic-api.crt", "certs/academic-api.key"))
