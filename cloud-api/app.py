import os
from datetime import datetime

import requests
from flask import Flask, jsonify, request

AUTH_SERVER = os.environ.get("AUTH_SERVER", "https://localhost:5000")
CLIENT_ID = "cloud-app"
CLIENT_SECRET = "cloud-secret"
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "certs/ca.crt")

FILES = [
    {"name": "通告.txt", "size": "2KB", "uploaded_at": "2024-06-01"},
]

app = Flask(__name__)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Client-Cert,X-Client-Cert-Fingerprint"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "cloud-api ok"})


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


@app.route("/files", methods=["GET"])
def list_files():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    return jsonify({"user": data["username"], "files": FILES})


@app.route("/files", methods=["POST"])
def upload_file():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    payload = request.get_json() or {}
    name = payload.get("name", f"upload-{len(FILES)+1}.txt")
    size = payload.get("size", "1KB")
    FILES.append({"name": name, "size": size, "uploaded_at": datetime.utcnow().strftime("%Y-%m-%d")})
    return jsonify({"message": "uploaded", "files": FILES, "user": data["username"]}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5002, ssl_context=("certs/cloud-api.crt", "certs/cloud-api.key"))
