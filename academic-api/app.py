import os
import time
import urllib.parse

import requests
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

AUTH_SERVER = os.environ.get("AUTH_SERVER", "https://auth.localhost:5000")
CLIENT_ID = "academic-app"
CLIENT_SECRET = "academic-secret"
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "certs/ca.crt")
FRONT_URL = os.environ.get("FRONT_URL", "https://academic.localhost:4174/academic.html")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "https://academic.localhost:5001/session/callback")
AUTH_PORTAL = os.environ.get("AUTH_PORTAL", "https://auth.localhost:4173/auth.html")

DB_USER = os.environ.get("DB_USER", "academic_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "academic_user@USTB2025")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "academic")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{urllib.parse.quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _ensure_course_schedule_columns():
    """Ensure courses table has day/slot/location columns for timetable."""
    alter_statements = [
        "ALTER TABLE courses ADD COLUMN day TINYINT NULL",
        "ALTER TABLE courses ADD COLUMN slot TINYINT NULL",
        "ALTER TABLE courses ADD COLUMN location VARCHAR(100) NULL",
    ]
    checks = ["day", "slot", "location"]
    try:
        with engine.begin() as conn:
            for col, stmt in zip(checks, alter_statements):
                exists = conn.execute(
                    text(
                        "SELECT COUNT(*) AS cnt FROM information_schema.columns "
                        "WHERE table_schema=:db AND table_name='courses' AND column_name=:col"
                    ),
                    {"db": DB_NAME, "col": col},
                ).scalar_one()
                if not exists:
                    conn.execute(text(stmt))
    except OperationalError:
        # If schema querying itself fails, swallow to avoid crashing; runtime errors will surface later.
        pass


_ensure_course_schedule_columns()

# 若数据库未提供课表信息，用默认值补齐 day/slot/location/desc，保证前端不改即可显示
SCHEDULE_DEFAULTS = {
    "CS101": {"day": 1, "slot": 1, "location": "一教101", "desc": "C 语言入门与程序设计思想，含上机实验。"},
    "MATH201": {"day": 1, "slot": 2, "location": "一教102", "desc": "微积分与级数，打好数学分析基础。"},
    "NET300": {"day": 2, "slot": 3, "location": "实验楼305", "desc": "TCP/IP 协议栈、路由与网络安全基础。"},
    "AI210": {"day": 3, "slot": 4, "location": "二教202", "desc": "AI 发展概览、搜索、机器学习与应用案例。"},
    "OS220": {"day": 4, "slot": 2, "location": "二教201", "desc": "进程线程、内存管理、文件系统与同步机制。"},
    "DS150": {"day": 5, "slot": 5, "location": "一教201", "desc": "链表、树、图及基本算法分析。"},
}

# 兜底 profile 字段（当前从数据库读取，缺字段时使用空字符串）
PROFILE_FALLBACK = {
    "personal": {"name": "", "student_id": ""},
    "enrollment": {"grade": "", "college": "", "major": "", "progress": ""},
}

SESSIONS = {}

app = Flask(__name__)


def get_db_session():
    return SessionLocal()


def _fetch_user(session, username):
    return session.execute(
        text("SELECT id, role FROM users WHERE username = :u LIMIT 1"),
        {"u": username},
    ).mappings().first()


def _student_profile(session, user_id):
    return session.execute(
        text(
            """
            SELECT name, student_no, gender, hometown, grade, college, major
            FROM students WHERE user_id = :uid
            """
        ),
        {"uid": user_id},
    ).mappings().first()


def _teacher_profile(session, user_id):
    return session.execute(
        text(
            """
            SELECT name, employee_no, title, department
            FROM teachers WHERE user_id = :uid
            """
        ),
        {"uid": user_id},
    ).mappings().first()


def _student_courses(session, user_id):
    rows = session.execute(
        text(
            """
            SELECT c.code, c.title, c.description, c.day, c.slot, c.location, e.grade
            FROM enrollments e
            JOIN students s ON s.id = e.student_id
            JOIN courses c ON c.id = e.course_id
            WHERE s.user_id = :uid
            ORDER BY c.code
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    return rows


def _ensure_teacher_profile(session, user_row, username: str):
    teacher_row = session.execute(
        text("SELECT id FROM teachers WHERE user_id=:uid"),
        {"uid": user_row["id"]},
    ).mappings().first()
    if teacher_row:
        return teacher_row["id"]
    # 若教师档案不存在则创建占位，避免管理页面无法使用
    session.execute(
        text(
            """
            INSERT INTO teachers (user_id, name, employee_no, title, department)
            VALUES (:uid, :name, :emp, :title, :dept)
            """
        ),
        {
            "uid": user_row["id"],
            "name": username,
            "emp": username,
            "title": "",
            "dept": "",
        },
    )
    session.commit()
    return session.execute(
        text("SELECT id FROM teachers WHERE user_id=:uid"),
        {"uid": user_row["id"]},
    ).mappings().first()["id"]


def _teacher_courses(session, user_id):
    rows = session.execute(
        text(
            """
            SELECT c.code, c.title, c.description, c.day, c.slot, c.location
            FROM courses c
            JOIN teachers t ON t.id = c.teacher_id
            WHERE t.user_id = :uid
            ORDER BY c.code
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    return rows


def _with_schedule_defaults(course_row):
    defaults = SCHEDULE_DEFAULTS.get(course_row.get("code"), {})
    # 如果没有默认课表信息，给一个占位时间，避免前端表格缺少列
    day_fallback = defaults.get("day") or course_row.get("day") or 1
    slot_fallback = defaults.get("slot") or course_row.get("slot") or 1
    return {
        "code": course_row.get("code"),
        "title": course_row.get("title"),
        "desc": course_row.get("description") or defaults.get("desc"),
        "day": day_fallback,
        "slot": slot_fallback,
        "location": course_row.get("location") or defaults.get("location") or "待排",
    }


def _all_students(session, keyword=None):
    params = {}
    sql = "SELECT name, student_no, gender, hometown, grade, college, major FROM students"
    if keyword:
        params["kw"] = f"%{keyword}%"
        sql += " WHERE name LIKE :kw OR student_no LIKE :kw"
    sql += " ORDER BY student_no"
    rows = session.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _course_students(session, course_code):
    rows = session.execute(
        text(
            """
            SELECT s.name, s.student_no, e.grade
            FROM enrollments e
            JOIN students s ON s.id = e.student_id
            JOIN courses c ON c.id = e.course_id
            WHERE c.code = :code
            ORDER BY s.student_no
            """
        ),
        {"code": course_code},
    ).mappings().all()
    return [dict(r) for r in rows]


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
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS,PUT,DELETE"
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
    role = data.get("role")
    if username and not sess.get("username"):
        sess["username"] = username
        SESSIONS[session_id] = sess
    if role and not sess.get("role"):
        sess["role"] = role
        SESSIONS[session_id] = sess
    return jsonify({"logged_in": True, "username": username, "role": sess.get("role") or role, "login_at": sess.get("login_at")})


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
    username = data.get("username")
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row:
                return jsonify({"error": "user not found in DB"}), 404
            if user_row["role"] == "student":
                rows = _student_courses(session, user_row["id"])
            else:
                rows = _teacher_courses(session, user_row["id"])
            courses_payload = [_with_schedule_defaults(r) for r in rows]
            return jsonify({"user": username, "courses": courses_payload})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/grades", methods=["GET"])
def grades():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row:
                return jsonify({"error": "user not found in DB"}), 404
            if user_row["role"] == "student":
                rows = _student_courses(session, user_row["id"])
                grade_map = {row["code"]: row.get("grade") or "" for row in rows}
            else:
                rows = _teacher_courses(session, user_row["id"])
                grade_map = {row["code"]: "教师端请前往管理页面"} if rows else {}
            return jsonify({"user": username, "grades": grade_map})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/profile", methods=["GET"])
def profile():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row:
                return jsonify({"error": "user not found in DB"}), 404
            if user_row["role"] == "student":
                prof = _student_profile(session, user_row["id"])
                if not prof:
                    return jsonify({"error": "student profile not found"}), 404
                payload = {
                    "personal": {
                        "name": prof["name"],
                        "student_id": prof["student_no"],
                    },
                    "enrollment": {
                        "grade": prof.get("grade") or "",
                        "college": prof.get("college") or "",
                        "major": prof.get("major") or "",
                        "progress": "",
                    },
                }
            else:
                prof = _teacher_profile(session, user_row["id"])
                if not prof:
                    return jsonify({"error": "teacher profile not found"}), 404
                payload = {
                    "personal": {
                        "name": prof["name"],
                        "student_id": prof["employee_no"],
                    },
                    "enrollment": {
                        "grade": prof.get("title") or "",
                        "college": prof.get("department") or "",
                        "major": "教师",
                        "progress": "",
                    },
                }
            return jsonify({"user": username, "profile": payload})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/profile", methods=["PUT"])
def update_profile():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    payload = request.get_json() or {}
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row:
                return jsonify({"error": "user not found in DB"}), 404
            if user_row["role"] == "student":
                session.execute(
                    text(
                        """
                        UPDATE students
                        SET name=:name, student_no=:stu_no, gender=:gender, hometown=:hometown, grade=:grade, college=:college, major=:major
                        WHERE user_id=:uid
                        """
                    ),
                    {
                        "name": payload.get("name") or "",
                        "stu_no": payload.get("student_id") or "",
                        "gender": payload.get("gender") or "",
                        "hometown": payload.get("hometown") or "",
                        "grade": payload.get("grade") or "",
                        "college": payload.get("college") or "",
                        "major": payload.get("major") or "",
                        "uid": user_row["id"],
                    },
                )
            else:
                session.execute(
                    text(
                        """
                        UPDATE teachers
                        SET name=:name, employee_no=:emp_no, title=:title, department=:department
                        WHERE user_id=:uid
                        """
                    ),
                    {
                        "name": payload.get("name") or "",
                        "emp_no": payload.get("student_id") or "",
                        "title": payload.get("title") or "",
                        "department": payload.get("department") or "",
                        "uid": user_row["id"],
                    },
                )
            session.commit()
            return jsonify({"message": "profile updated"})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/profile/password", methods=["POST"])
def change_password():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    body = request.get_json() or {}
    old_pw = body.get("old_password")
    new_pw = body.get("new_password")
    if not old_pw or not new_pw:
        return jsonify({"error": "missing password fields"}), 400
    try:
        with get_db_session() as session:
            row = session.execute(
                text("SELECT id, password_hash FROM users WHERE username=:u LIMIT 1"),
                {"u": username},
            ).mappings().first()
            if not row:
                return jsonify({"error": "user not found"}), 404
            if not check_password_hash(row["password_hash"], old_pw):
                return jsonify({"error": "invalid old password"}), 400
            new_hash = generate_password_hash(new_pw)
            session.execute(
                text("UPDATE users SET password_hash=:ph WHERE id=:uid"),
                {"ph": new_hash, "uid": row["id"]},
            )
            session.commit()
            return jsonify({"message": "password updated"})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/courses/manage", methods=["GET", "POST"])
def courses_manage():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    if request.method == "GET":
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row or user_row["role"] != "teacher":
                return jsonify({"error": "forbidden"}), 403
            _ensure_teacher_profile(session, user_row, username)
            rows = _teacher_courses(session, user_row["id"])
            return jsonify({"user": username, "courses": rows})

    # POST: create course
    body = request.get_json() or {}
    code_val = body.get("code")
    title = body.get("title")
    desc = body.get("desc") or ""
    if not code_val or not title:
        return jsonify({"error": "missing code/title"}), 400
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row or user_row["role"] != "teacher":
                return jsonify({"error": "forbidden"}), 403
            teacher_id = _ensure_teacher_profile(session, user_row, username)
            session.execute(
                text("INSERT INTO courses (code, title, teacher_id, description) VALUES (:c,:t,:tid,:d)"),
                {"c": code_val, "t": title, "tid": teacher_id, "d": desc},
            )
            session.commit()
            return jsonify({"message": "created", "code": code_val})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


@app.route("/courses/<code>/students", methods=["GET"])
def course_students(code):
    data, err = _validate_token()
    if err:
        msg, code_status = err
        return jsonify({"error": msg}), code_status
    username = data.get("username")
    with get_db_session() as session:
        user_row = _fetch_user(session, username)
        if not user_row or user_row["role"] != "teacher":
            return jsonify({"error": "forbidden"}), 403
        # ensure course belongs to teacher
        own = session.execute(
            text("SELECT 1 FROM courses c JOIN teachers t ON t.id=c.teacher_id WHERE c.code=:c AND t.user_id=:u"),
            {"c": code, "u": user_row["id"]},
        ).first()
        if not own:
            return jsonify({"error": "course not found"}), 404
        rows = _course_students(session, code)
        return jsonify({"user": username, "course": code, "students": rows})


@app.route("/students", methods=["GET"])
def list_students():
    data, err = _validate_token()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code
    username = data.get("username")
    kw = request.args.get("q")
    try:
        with get_db_session() as session:
            user_row = _fetch_user(session, username)
            if not user_row or user_row["role"] != "teacher":
                return jsonify({"error": "forbidden"}), 403
            rows = _all_students(session, kw)
            return jsonify({"students": rows})
    except SQLAlchemyError as exc:
        return jsonify({"error": f"db error: {exc}"}), 500
    except Exception as exc:  # 防止返回 HTML
        return jsonify({"error": f"unexpected error: {exc}"}), 500


@app.route("/courses/<code>/students", methods=["POST", "DELETE"])
def modify_course_students(code):
    data, err = _validate_token()
    if err:
        msg, code_status = err
        return jsonify({"error": msg}), code_status
    username = data.get("username")
    body = request.get_json() or {}
    student_no = body.get("student_no")
    if not student_no:
        return jsonify({"error": "missing student_no"}), 400
    with get_db_session() as session:
        user_row = _fetch_user(session, username)
        if not user_row or user_row["role"] != "teacher":
            return jsonify({"error": "forbidden"}), 403
        course_row = session.execute(
            text("SELECT c.id FROM courses c JOIN teachers t ON t.id=c.teacher_id WHERE c.code=:c AND t.user_id=:u"),
            {"c": code, "u": user_row["id"]},
        ).mappings().first()
        if not course_row:
            return jsonify({"error": "course not found"}), 404
        student_row = session.execute(
            text("SELECT id FROM students WHERE student_no=:sn"),
            {"sn": student_no},
        ).mappings().first()
        if not student_row:
            return jsonify({"error": "student not found"}), 404
        if request.method == "POST":
            session.execute(
                text("INSERT IGNORE INTO enrollments (course_id, student_id, grade) VALUES (:cid,:sid,'')"),
                {"cid": course_row["id"], "sid": student_row["id"]},
            )
        else:
            session.execute(
                text("DELETE FROM enrollments WHERE course_id=:cid AND student_id=:sid"),
                {"cid": course_row["id"], "sid": student_row["id"]},
            )
        session.commit()
        return jsonify({"message": "updated"})


@app.route("/courses/<code>/grade", methods=["POST"])
def update_grade(code):
    data, err = _validate_token()
    if err:
        msg, code_status = err
        return jsonify({"error": msg}), code_status
    username = data.get("username")
    body = request.get_json() or {}
    student_no = body.get("student_no")
    grade = body.get("grade")
    if not student_no:
        return jsonify({"error": "missing student_no"}), 400
    with get_db_session() as session:
        user_row = _fetch_user(session, username)
        if not user_row or user_row["role"] != "teacher":
            return jsonify({"error": "forbidden"}), 403
        course_row = session.execute(
            text("SELECT c.id FROM courses c JOIN teachers t ON t.id=c.teacher_id WHERE c.code=:c AND t.user_id=:u"),
            {"c": code, "u": user_row["id"]},
        ).mappings().first()
        if not course_row:
            return jsonify({"error": "course not found"}), 404
        student_row = session.execute(
            text("SELECT id FROM students WHERE student_no=:sn"),
            {"sn": student_no},
        ).mappings().first()
        if not student_row:
            return jsonify({"error": "student not found"}), 404
        session.execute(
            text("UPDATE enrollments SET grade=:g WHERE course_id=:cid AND student_id=:sid"),
            {"g": grade or "", "cid": course_row["id"], "sid": student_row["id"]},
        )
        session.commit()
        return jsonify({"message": "grade updated"})


@app.route("/courses/<code>/schedule", methods=["POST"])
def update_schedule(code):
    data, err = _validate_token()
    if err:
        msg, code_status = err
        return jsonify({"error": msg}), code_status
    username = data.get("username")
    body = request.get_json() or {}
    try:
        day = int(body.get("day"))
        slot = int(body.get("slot"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid day/slot"}), 400
    if not (1 <= day <= 7 and 1 <= slot <= 12):
        return jsonify({"error": "day must be 1-7, slot must be 1-12"}), 400
    location = body.get("location") or None
    with get_db_session() as session:
        user_row = _fetch_user(session, username)
        if not user_row or user_row["role"] != "teacher":
            return jsonify({"error": "forbidden"}), 403
        course_row = session.execute(
            text("SELECT c.id FROM courses c JOIN teachers t ON t.id=c.teacher_id WHERE c.code=:c AND t.user_id=:u"),
            {"c": code, "u": user_row["id"]},
        ).mappings().first()
        if not course_row:
            return jsonify({"error": "course not found"}), 404
        session.execute(
            text("UPDATE courses SET day=:d, slot=:s, location=COALESCE(:loc, location) WHERE id=:cid"),
            {"d": day, "s": slot, "loc": location, "cid": course_row["id"]},
        )
        session.commit()
        return jsonify({"message": "schedule updated", "code": code, "day": day, "slot": slot, "location": location})

if __name__ == "__main__":
    app.run(debug=True, port=5001, ssl_context=("certs/academic-api.crt", "certs/academic-api.key"))
