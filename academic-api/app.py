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
    {"code": "CS101", "title": "Introduction to Computer Science"},
    {"code": "MATH201", "title": "Discrete Mathematics"},
    {"code": "NET300", "title": "Network Security"},
]
GRADES = {"CS101": "A", "MATH201": "B+", "NET300": "A-"}

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
    return jsonify({"logged_in": True})


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


if __name__ == "__main__":
    app.run(debug=True, port=5001, ssl_context=("certs/academic-api.crt", "certs/academic-api.key"))
