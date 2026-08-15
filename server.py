import os
import sqlite3
import random
import re
import base64
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "BMAXGRAM_CHANGE_THIS_SECRET"
)

DB_FILE = os.environ.get(
    "DB_FILE",
    "bmaxgram.db"
)

PORT = int(
    os.environ.get(
        "PORT",
        "5000"
    )
)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PUBLIC_DIR = os.path.join(
    BASE_DIR,
    "public"
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    PUBLIC_DIR,
    exist_ok=True
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    db = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    db.row_factory = sqlite3.Row

    return db


def clean_phone(phone):

    if not phone:
        return ""

    phone = str(phone).strip()

    phone = re.sub(
        r"[^\d+]",
        "",
        phone
    )

    if phone.startswith("998"):

        phone = "+" + phone

    elif (
        not phone.startswith("+")
        and len(phone) == 9
    ):

        phone = "+998" + phone

    elif not phone.startswith("+"):

        phone = "+" + phone

    return phone


def init_db():

    db = get_db()

    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            phone TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            avatar TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_phone TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            contact_name TEXT DEFAULT '',
            UNIQUE(user_phone,contact_phone)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_members(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_phone TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            UNIQUE(group_id,user_phone)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            chat_type TEXT NOT NULL,
            text TEXT DEFAULT '',
            audio TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_codes(
            phone TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()

    db.close()


init_db()


# =========================================================
# AUTH
# =========================================================

def logged_user():

    return session.get(
        "phone"
    )


def require_login(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not logged_user():

            return jsonify({
                "message": "Kirish kerak"
            }), 401

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# FRONTEND
# =========================================================

@app.route("/")
def index():

    return send_from_directory(
        PUBLIC_DIR,
        "index.html"
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):

    return send_from_directory(
        UPLOAD_DIR,
        filename
    )


# =========================================================
# REQUEST CODE
# =========================================================

@app.post("/api/request_code")
def request_code():

    data = request.get_json(
        silent=True
    ) or {}

    phone = clean_phone(
        data.get("phone")
    )

    if not phone:

        return jsonify({
            "message": "Telefon raqam kiriting"
        }), 400

    code = str(
        random.randint(
            100000,
            999999
        )
    )

    db = get_db()

    db.execute("""
        INSERT INTO auth_codes(
            phone,
            code
        )
        VALUES(?,?)
        ON CONFLICT(phone)
        DO UPDATE SET code=excluded.code
    """, (
        phone,
        code
    ))

    db.execute("""
        INSERT INTO users(
            phone,
            name
        )
        VALUES(?,?)
        ON CONFLICT(phone)
        DO NOTHING
    """, (
        phone,
        phone
    ))

    db.commit()

    db.close()

    # Test rejimida kod frontendga qaytariladi.
    return jsonify({
        "status": "ok",
        "phone": phone,
        "code": code
    })


@app.post("/api/login")
def login():

    data = request.get_json(
        silent=True
    ) or {}

    phone = clean_phone(
        data.get("phone")
    )

    code = str(
        data.get("code", "")
    ).strip()

    if not phone or not code:

        return jsonify({
            "message": "Telefon va kod kerak"
        }), 400

    db = get_db()

    row = db.execute("""
        SELECT code
        FROM auth_codes
        WHERE phone=?
    """, (
        phone,
    )).fetchone()

    if not row:

        db.close()

        return jsonify({
            "message": "Kod topilmadi"
        }), 400

    if row["code"] != code:

        db.close()

        return jsonify({
            "message": "Kod noto'g'ri"
        }), 400

    db.execute("""
        INSERT INTO users(
            phone,
            name
        )
        VALUES(?,?)
        ON CONFLICT(phone)
        DO NOTHING
    """, (
        phone,
        phone
    ))

    db.commit()

    db.close()

    session["phone"] = phone

    return jsonify({
        "status": "ok",
        "phone": phone
    })


@app.post("/api/logout")
def logout():

    session.clear()

    return jsonify({
        "status": "ok"
    })


# =========================================================
# PROFILE
# =========================================================

@app.get("/api/profile")
@require_login
def profile_get():

    phone = logged_user()

    db = get_db()

    user = db.execute("""
        SELECT phone,name,bio,avatar
        FROM users
        WHERE phone=?
    """, (
        phone,
    )).fetchone()

    db.close()

    return jsonify({
        "user": dict(user)
    })


@app.post("/api/profile")
@require_login
def profile_save():

    phone = logged_user()

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get("name", "")
    ).strip()

    bio = str(
        data.get("bio", "")
    ).strip()

    avatar = str(
        data.get("avatar", "")
    )

    if len(name) > 100:

        name = name[:100]

    if len(bio) > 500:

        bio = bio[:500]

    db = get_db()

    db.execute("""
        UPDATE users
        SET name=?,
            bio=?,
            avatar=?
        WHERE phone=?
    """, (
        name,
        bio,
        avatar,
        phone
    ))

    db.commit()

    db.close()

    return jsonify({
        "status": "ok"
    })


# =========================================================
# CONTACTS
# =========================================================

@app.get("/api/contacts")
@require_login
def contacts_get():

    phone = logged_user()

    db = get_db()

    rows = db.execute("""
        SELECT
            c.id,
            c.contact_phone AS phone,
            c.contact_name AS name,
            u.avatar AS avatar,
            u.bio AS bio
        FROM contacts c
        LEFT JOIN users u
            ON u.phone=c.contact_phone
        WHERE c.user_phone=?
        ORDER BY c.id DESC
    """, (
        phone,
    )).fetchall()

    db.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.post("/api/contacts")
@require_login
def contacts_add():

    owner = logged_user()

    data = request.get_json(
        silent=True
    ) or {}

    contact_phone = clean_phone(
        data.get("phone")
    )

    contact_name = str(
        data.get("name", "")
    ).strip()

    if not contact_phone:

        return jsonify({
            "message": "Telefon raqam kerak"
        }), 400

    if not contact_name:

        contact_name = contact_phone

    db = get_db()

    user = db.execute("""
        SELECT phone
        FROM users
        WHERE phone=?
    """, (
        contact_phone,
    )).fetchone()

    if not user:

        db.close()

        return jsonify({
            "message":
            "Bu raqam bilan BMAXGRAM foydalanuvchisi topilmadi"
        }), 404

    try:

        db.execute("""
            INSERT INTO contacts(
                user_phone,
                contact_phone,
                contact_name
            )
            VALUES(?,?,?)
        """, (
            owner,
            contact_phone,
            contact_name
        ))

        db.commit()

    except sqlite3.IntegrityError:

        db.execute("""
            UPDATE contacts
            SET contact_name=?
            WHERE user_phone=?
              AND contact_phone=?
        """, (
            contact_name,
            owner,
            contact_phone
        ))

        db.commit()

    db.close()

    return jsonify({
        "status": "ok"
    })


# =========================================================
# GROUPS
# =========================================================

@app.get("/api/groups")
@require_login
def groups_get():

    phone = logged_user()

    db = get_db()

    rows = db.execute("""
        SELECT
            g.id,
            g.name,
            g.avatar,
            COUNT(gm2.user_phone) AS member_count
        FROM groups g
        INNER JOIN group_members gm
            ON gm.group_id=g.id
        LEFT JOIN group_members gm2
            ON gm2.group_id=g.id
        WHERE gm.user_phone=?
        GROUP BY g.id
        ORDER BY g.id DESC
    """, (
        phone,
    )).fetchall()

    db.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.post("/api/groups")
@require_login
def group_create():

    creator = logged_user()

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get("name", "")
    ).strip()

    avatar = str(
        data.get("avatar", "")
    )

    members = data.get(
        "members",
        []
    )

    if not name:

        return jsonify({
            "message":
            "Guruh nomini kiriting"
        }), 400

    db = get_db()

    try:

        cur = db.execute("""
            INSERT INTO groups(
                name,
                created_by,
                avatar
            )
            VALUES(?,?,?)
        """, (
            name,
            creator,
            avatar
        ))

        group_id = cur.lastrowid

    except sqlite3.IntegrityError:

        db.close()

        return jsonify({
            "message":
            "Bu guruh nomi mavjud"
        }), 400

    db.execute("""
        INSERT INTO group_members(
            group_id,
            user_phone,
            role
        )
        VALUES(?,?,?)
    """, (
        group_id,
        creator,
        "admin"
    ))

    for member in members:

        member = clean_phone(
            member
        )

        if not member or member == creator:
            continue

        exists = db.execute("""
            SELECT phone
            FROM users
            WHERE phone=?
        """, (
            member,
        )).fetchone()

        if exists:

            db.execute("""
                INSERT OR IGNORE INTO group_members(
                    group_id,
                    user_phone,
                    role
                )
                VALUES(?,?,?)
            """, (
                group_id,
                member,
                "member"
            ))

    db.commit()

    db.close()

    return jsonify({
        "status": "ok",
        "id": group_id
    })


@app.get("/api/groups/<int:group_id>")
@require_login
def group_info(group_id):

    phone = logged_user()

    db = get_db()

    group = db.execute("""
        SELECT *
        FROM groups
        WHERE id=?
    """, (
        group_id,
    )).fetchone()

    if not group:

        db.close()

        return jsonify({
            "message": "Guruh topilmadi"
        }), 404

    member = db.execute("""
        SELECT *
        FROM group_members
        WHERE group_id=?
          AND user_phone=?
    """, (
        group_id,
        phone
    )).fetchone()

    if not member:

        db.close()

        return jsonify({
            "message":
            "Siz bu guruh a'zosi emassiz"
        }), 403

    members = db.execute("""
        SELECT
            gm.user_phone AS phone,
            gm.role,
            COALESCE(
                u.name,
                gm.user_phone
            ) AS name,
            u.avatar
        FROM group_members gm
        LEFT JOIN users u
            ON u.phone=gm.user_phone
        WHERE gm.group_id=?
        ORDER BY gm.role DESC
    """, (
        group_id,
    )).fetchall()

    db.close()

    return jsonify({
        "group": dict(group),
        "members": [
            dict(row)
            for row in members
        ]
    })


@app.post("/api/groups/<int:group_id>/members")
@require_login
def group_add_member(group_id):

    owner = logged_user()

    data = request.get_json(
        silent=True
    ) or {}

    member_phone = clean_phone(
        data.get("phone")
    )

    db = get_db()

    group = db.execute("""
        SELECT *
        FROM groups
        WHERE id=?
    """, (
        group_id,
    )).fetchone()

    if not group:

        db.close()

        return jsonify({
            "message": "Guruh topilmadi"
        }), 404

    admin = db.execute("""
        SELECT role
        FROM group_members
        WHERE group_id=?
          AND user_phone=?
    """, (
        group_id,
        owner
    )).fetchone()

    if not admin:

        db.close()

        return jsonify({
            "message":
            "Guruh a'zosi emassiz"
        }), 403

    if admin["role"] != "admin":

        db.close()

        return jsonify({
            "message":
            "Faqat admin odam qo'sha oladi"
        }), 403

    user = db.execute("""
        SELECT phone
        FROM users
        WHERE phone=?
    """, (
        member_phone,
    )).fetchone()

    if not user:

        db.close()

        return jsonify({
            "message":
            "Foydalanuvchi topilmadi"
        }), 404

    db.execute("""
        INSERT OR IGNORE INTO group_members(
            group_id,
            user_phone,
            role
        )
        VALUES(?,?,?)
    """, (
        group_id,
        member_phone,
        "member"
    ))

    db.commit()

    db.close()

    return jsonify({
        "status": "ok"
    })


# =========================================================
# MESSAGES
# =========================================================

@app.get("/api/messages")
@require_login
def messages_get():

    me = logged_user()

    receiver = str(
        request.args.get(
            "receiver",
            ""
        )
    )

    chat_type = str(
        request.args.get(
            "chat_type",
            "private"
        )
    )

    after = int(
        request.args.get(
            "after",
            "0"
        )
    )

    db = get_db()

    if chat_type == "group":

        try:
            group_id = int(
                receiver
            )
        except ValueError:

            db.close()

            return jsonify([])

        member = db.execute("""
            SELECT id
            FROM group_members
            WHERE group_id=?
              AND user_phone=?
        """, (
            group_id,
            me
        )).fetchone()

        if not member:

            db.close()

            return jsonify({
                "message":
                "Guruhga a'zo emassiz"
            }), 403

        rows = db.execute("""
            SELECT
                m.id,
                m.sender,
                m.receiver,
                m.chat_type,
                m.text,
                m.audio,
                m.created_at,
                COALESCE(
                    u.name,
                    m.sender
                ) AS sender_name
            FROM messages m
            LEFT JOIN users u
                ON u.phone=m.sender
            WHERE m.chat_type='group'
              AND m.receiver=?
              AND m.id>?
            ORDER BY m.id ASC
            LIMIT 200
        """, (
            str(group_id),
            after
        )).fetchall()

    else:

        rows = db.execute("""
            SELECT
                m.id,
                m.sender,
                m.receiver,
                m.chat_type,
                m.text,
                m.audio,
                m.created_at,
                COALESCE(
                    u.name,
                    m.sender
                ) AS sender_name
            FROM messages m
            LEFT JOIN users u
                ON u.phone=m.sender
            WHERE m.chat_type='private'
              AND m.id>?
              AND (
                    (
                        m.sender=?
                        AND m.receiver=?
                    )
                    OR
                    (
                        m.sender=?
                        AND m.receiver=?
                    )
              )
            ORDER BY m.id ASC
            LIMIT 200
        """, (
            after,
            me,
            receiver,
            receiver,
            me
        )).fetchall()

    db.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.post("/api/messages")
@require_login
def message_send():

    sender = logged_user()

    data = request.get_json(
        silent=True
    ) or {}

    receiver = str(
        data.get(
            "receiver",
            ""
        )
    )

    chat_type = str(
        data.get(
            "chat_type",
            "private"
        )
    )

    text = str(
        data.get(
            "text",
            ""
        )
    ).strip()

    if not receiver or not text:

        return jsonify({
            "message":
            "Xabar bo'sh bo'lmasligi kerak"
        }), 400

    if len(text) > 5000:

        return jsonify({
            "message":
            "Xabar juda uzun"
        }), 400

    db = get_db()

    if chat_type == "group":

        member = db.execute("""
            SELECT id
            FROM group_members
            WHERE group_id=?
              AND user_phone=?
        """, (
            receiver,
            sender
        )).fetchone()

        if not member:

            db.close()

            return jsonify({
                "message":
                "Guruh a'zosi emassiz"
            }), 403

    else:

        receiver = clean_phone(
            receiver
        )

        exists = db.execute("""
            SELECT phone
            FROM users
            WHERE phone=?
        """, (
            receiver,
        )).fetchone()

        if not exists:

            db.close()

            return jsonify({
                "message":
                "Foydalanuvchi topilmadi"
            }), 404

    cur = db.execute("""
        INSERT INTO messages(
            sender,
            receiver,
            chat_type,
            text,
            audio
        )
        VALUES(?,?,?,?,?)
    """, (
        sender,
        receiver,
        chat_type,
        text,
        ""
    ))

    message_id = cur.lastrowid

    db.commit()

    db.close()

    return jsonify({
        "status": "ok",
        "id": message_id
    })


# =========================================================
# VOICE
# =========================================================

@app.post("/api/voice")
@require_login
def voice_send():

    sender = logged_user()

    receiver = str(
        request.form.get(
            "receiver",
            ""
        )
    )

    chat_type = str(
        request.form.get(
            "chat_type",
            "private"
        )
    )

    audio = request.files.get(
        "audio"
    )

    if not receiver or not audio:

        return jsonify({
            "message":
            "Ovoz fayli kerak"
        }), 400

    extension = ".webm"

    filename = (
        str(random.randint(
            100000,
            999999999
        ))
        + extension
    )

    path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    audio.save(
        path
    )

    audio_url = (
        "/uploads/" +
        filename
    )

    db = get_db()

    if chat_type == "group":

        member = db.execute("""
            SELECT id
            FROM group_members
            WHERE group_id=?
              AND user_phone=?
        """, (
            receiver,
            sender
        )).fetchone()

        if not member:

            db.close()

            try:
                os.remove(path)
            except Exception:
                pass

            return jsonify({
                "message":
                "Guruh a'zosi emassiz"
            }), 403

    else:

        receiver = clean_phone(
            receiver
        )

    cur = db.execute("""
        INSERT INTO messages(
            sender,
            receiver,
            chat_type,
            text,
            audio
        )
        VALUES(?,?,?,?,?)
    """, (
        sender,
        receiver,
        chat_type,
        "",
        audio_url
    ))

    message_id = cur.lastrowid

    db.commit()

    db.close()

    return jsonify({
        "status": "ok",
        "id": message_id,
        "audio": audio_url
    })


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health():

    return jsonify({
        "status": "ok",
        "app": "BMAXGRAM"
    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
