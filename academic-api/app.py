import os

import requests
from flask import Flask, jsonify, request

AUTH_SERVER = os.environ.get("AUTH_SERVER", "https://localhost:5000")
CLIENT_ID = "academic-app"
CLIENT_SECRET = "academic-secret"
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "certs/ca.crt")

COURSES = [
    {"code": "CS101", "title": "Introduction to Computer Science"},
    {"code": "MATH201", "title": "Discrete Mathematics"},
    {"code": "NET300", "title": "Network Security"},
]
GRADES = {"CS101": "A", "MATH201": "B+", "NET300": "A-"}

app = Flask(__name__)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Client-Cert,X-Client-Cert-Fingerprint"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "academic-api ok"})


def _validate_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, ("missing bearer token", 401)
    headers = {"Authorization": auth_header}
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


@app.route("/exchange", methods=["POST"])
def exchange():
    data = request.get_json() or {}
    code = data.get("code")
    if not code:
        return jsonify({"error": "code required"}), 400
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
        return jsonify({"error": f"auth server error: {exc}"}), 502
    return jsonify(resp.json()), resp.status_code


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
