from flask import Flask, request, jsonify, session, send_from_directory
import sqlite3
import os
import random
import uuid
from datetime import datetime

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "BMAXGRAM_SECRET_KEY"
)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_PATH = os.path.join(
    BASE_DIR,
    "bmaxgram.db"
)

STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)

UPLOAD_DIR = os.path.join(
    STATIC_DIR,
    "uploads"
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

os.makedirs(
    STATIC_DIR,
    exist_ok=True
)


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def init_db():

    conn = db()

    conn.executescript("""
    
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        bio TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_phone TEXT NOT NULL,
        contact_phone TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(owner_phone, contact_phone)
    );

    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        avatar TEXT DEFAULT '',
        owner_phone TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        role TEXT DEFAULT 'member',
        UNIQUE(group_id, phone),
        FOREIGN KEY(group_id)
            REFERENCES groups(id)
            ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_type TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        sender_phone TEXT NOT NULL,
        text TEXT DEFAULT '',
        audio TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.utcnow().isoformat()


def get_phone():

    return session.get(
        "phone"
    )


def logged():

    phone = get_phone()

    if not phone:
        return None

    return phone


def user_exists(phone):

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    conn.close()

    return row


def make_user(phone):

    row = user_exists(
        phone
    )

    if row:
        return dict(row)

    conn = db()

    conn.execute(
        """
        INSERT INTO users
        (phone, name, created_at)
        VALUES (?, ?, ?)
        """,
        (
            phone,
            phone,
            now()
        )
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    conn.close()

    return dict(row)


def json_error(message, code=400):

    return jsonify({
        "success": False,
        "message": message
    }), code


# =========================================================
# WEBSITE
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        STATIC_DIR,
        "index.html"
    )


@app.route("/uploads/<path:name>")
def uploads(name):

    return send_from_directory(
        UPLOAD_DIR,
        name
    )


# =========================================================
# REQUEST RANDOM CODE
# =========================================================

@app.route(
    "/api/request_code",
    methods=["POST"]
)
def request_code():

    data = request.get_json(
        silent=True
    ) or {}

    phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()

    if not phone:
        return json_error(
            "Telefon raqam kiriting"
        )

    code = str(
        random.randint(
            100000,
            999999
        )
    )

    session[
        "verification_phone"
    ] = phone

    session[
        "verification_code"
    ] = code

    # TEST REJIMI
    # SMS yuborilmaydi.
    # Kod frontendga qaytariladi.

    return jsonify({
        "success": True,
        "code": code,
        "message":
            "Test kodi yaratildi"
    })


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    data = request.get_json(
        silent=True
    ) or {}

    phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()

    code = str(
        data.get(
            "code",
            ""
        )
    ).strip()

    if not phone:
        return json_error(
            "Telefon raqam kiriting"
        )

    saved_phone = session.get(
        "verification_phone"
    )

    saved_code = session.get(
        "verification_code"
    )

    if (
        saved_phone != phone
        or saved_code != code
    ):

        return json_error(
            "Tasdiqlash kodi noto'g'ri",
            401
        )

    make_user(
        phone
    )

    session["phone"] = phone

    session.pop(
        "verification_phone",
        None
    )

    session.pop(
        "verification_code",
        None
    )

    return jsonify({
        "success": True,
        "user":
            make_user(phone)
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True
    })


# =========================================================
# CURRENT USER
# =========================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
def me():

    phone = logged()

    if not phone:
        return json_error(
            "Tizimga kirmagansiz",
            401
        )

    return jsonify({
        "success": True,
        "user":
            make_user(phone)
    })


# =========================================================
# PROFILE
# =========================================================

@app.route(
    "/api/profile",
    methods=["POST"]
)
def profile():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    bio = str(
        data.get(
            "bio",
            ""
        )
    ).strip()

    avatar = str(
        data.get(
            "avatar",
            ""
        )
    ).strip()

    if not name:
        name = phone

    conn = db()

    conn.execute(
        """
        UPDATE users
        SET name = ?,
            bio = ?,
            avatar = ?
        WHERE phone = ?
        """,
        (
            name,
            bio,
            avatar,
            phone
        )
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "user":
            dict(row)
    })


# =========================================================
# CONTACTS
# =========================================================

@app.route(
    "/api/contacts",
    methods=["GET"]
)
def contacts():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    conn = db()

    rows = conn.execute(
        """
        SELECT
            c.contact_phone AS phone,
            c.contact_name AS name,
            u.avatar AS avatar,
            u.bio AS bio
        FROM contacts c
        LEFT JOIN users u
        ON u.phone = c.contact_phone
        WHERE c.owner_phone = ?
        ORDER BY c.id DESC
        """,
        (phone,)
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# =========================================================
# ADD CONTACT
# =========================================================

@app.route(
    "/api/contacts",
    methods=["POST"]
)
def add_contact():

    owner = logged()

    if not owner:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    if not phone:
        return json_error(
            "Kontakt raqamini kiriting"
        )

    if phone == owner:
        return json_error(
            "O'zingizni kontaktga qo'sha olmaysiz"
        )

    target = user_exists(
        phone
    )

    if not target:

        return json_error(
            "Bu raqam bilan BMAXGRAM foydalanuvchisi topilmadi"
        )

    if not name:
        name = target["name"]

    conn = db()

    try:

        conn.execute(
            """
            INSERT INTO contacts
            (
                owner_phone,
                contact_phone,
                contact_name,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                owner,
                phone,
                name,
                now()
            )
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return json_error(
            "Bu kontakt allaqachon mavjud"
        )

    conn.close()

    return jsonify({
        "success": True,
        "message":
            "Kontakt saqlandi"
    })


# =========================================================
# GROUP LIST
# =========================================================

@app.route(
    "/api/groups",
    methods=["GET"]
)
def groups_list():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    conn = db()

    rows = conn.execute(
        """
        SELECT
            g.id,
            g.name,
            g.avatar,
            g.owner_phone,
            g.created_at,
            COUNT(gm2.id) AS member_count
        FROM groups g
        JOIN group_members gm
            ON gm.group_id = g.id
        LEFT JOIN group_members gm2
            ON gm2.group_id = g.id
        WHERE gm.phone = ?
        GROUP BY g.id
        ORDER BY g.id DESC
        """,
        (phone,)
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# =========================================================
# CREATE GROUP
# =========================================================

@app.route(
    "/api/groups",
    methods=["POST"]
)
def create_group():

    owner = logged()

    if not owner:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    avatar = str(
        data.get(
            "avatar",
            ""
        )
    ).strip()

    members = data.get(
        "members",
        []
    )

    if not name:
        return json_error(
            "Guruh nomini kiriting"
        )

    if not isinstance(
        members,
        list
    ):
        members = []

    members = [
        str(x).strip()
        for x in members
        if str(x).strip()
    ]

    members = list(
        dict.fromkeys(
            members
        )
    )

    if owner not in members:
        members.insert(
            0,
            owner
        )

    valid = []

    for phone in members:

        if user_exists(
            phone
        ):
            valid.append(
                phone
            )

    conn = db()

    cur = conn.execute(
        """
        INSERT INTO groups
        (
            name,
            avatar,
            owner_phone,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            avatar,
            owner,
            now()
        )
    )

    group_id = cur.lastrowid

    for phone in valid:

        role = (
            "admin"
            if phone == owner
            else "member"
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO
            group_members
            (group_id, phone, role)
            VALUES (?, ?, ?)
            """,
            (
                group_id,
                phone,
                role
            )
        )

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM groups
        WHERE id = ?
        """,
        (group_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "group":
            dict(row)
    })


# =========================================================
# GROUP INFO
# =========================================================

@app.route(
    "/api/groups/<int:group_id>",
    methods=["GET"]
)
def group_info(group_id):

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    conn = db()

    group = conn.execute(
        """
        SELECT *
        FROM groups
        WHERE id = ?
        """,
        (group_id,)
    ).fetchone()

    if not group:

        conn.close()

        return json_error(
            "Guruh topilmadi",
            404
        )

    member = conn.execute(
        """
        SELECT *
        FROM group_members
        WHERE group_id = ?
        AND phone = ?
        """,
        (
            group_id,
            phone
        )
    ).fetchone()

    if not member:

        conn.close()

        return json_error(
            "Siz bu guruh a'zosi emassiz",
            403
        )

    rows = conn.execute(
        """
        SELECT
            u.phone,
            u.name,
            u.avatar,
            gm.role
        FROM group_members gm
        JOIN users u
            ON u.phone = gm.phone
        WHERE gm.group_id = ?
        ORDER BY gm.id
        """,
        (group_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "group":
            dict(group),
        "members": [
            dict(x)
            for x in rows
        ]
    })


# =========================================================
# ADD GROUP MEMBER
# =========================================================

@app.route(
    "/api/groups/<int:group_id>/members",
    methods=["POST"]
)
def add_member(group_id):

    owner = logged()

    if not owner:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    new_phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()

    if not new_phone:
        return json_error(
            "Kontakt raqamini kiriting"
        )

    conn = db()

    group = conn.execute(
        """
        SELECT *
        FROM groups
        WHERE id = ?
        """,
        (group_id,)
    ).fetchone()

    if not group:

        conn.close()

        return json_error(
            "Guruh topilmadi",
            404
        )

    # Faqat guruh a'zosi qo'sha oladi
    member = conn.execute(
        """
        SELECT *
        FROM group_members
        WHERE group_id = ?
        AND phone = ?
        """,
        (
            group_id,
            owner
        )
    ).fetchone()

    if not member:

        conn.close()

        return json_error(
            "Siz guruh a'zosi emassiz",
            403
        )

    if not user_exists(
        new_phone
    ):

        conn.close()

        return json_error(
            "Bu odam BMAXGRAM'da ro'yxatdan o'tmagan"
        )

    try:

        conn.execute(
            """
            INSERT INTO group_members
            (group_id, phone, role)
            VALUES (?, ?, 'member')
            """,
            (
                group_id,
                new_phone
            )
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return json_error(
            "Bu odam allaqachon guruhda"
        )

    conn.close()

    return jsonify({
        "success": True,
        "message":
            "Odam guruhga qo'shildi"
    })


# =========================================================
# SEND TEXT MESSAGE
# =========================================================

@app.route(
    "/api/messages",
    methods=["POST"]
)
def send_message():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    data = request.get_json(
        silent=True
    ) or {}

    chat_type = str(
        data.get(
            "chat_type",
            "private"
        )
    )

    chat_id = str(
        data.get(
            "chat_id",
            ""
        )
    ).strip()

    text = str(
        data.get(
            "text",
            ""
        )
    ).strip()

    if not chat_id:
        return json_error(
            "Chat tanlanmagan"
        )

    if not text:
        return json_error(
            "Xabar bo'sh"
        )

    conn = db()

    if chat_type == "group":

        try:
            gid = int(
                chat_id
            )
        except:

            conn.close()

            return json_error(
                "Guruh ID noto'g'ri"
            )

        member = conn.execute(
            """
            SELECT *
            FROM group_members
            WHERE group_id = ?
            AND phone = ?
            """,
            (
                gid,
                phone
            )
        ).fetchone()

        if not member:

            conn.close()

            return json_error(
                "Guruh a'zosi emassiz",
                403
            )

    else:

        if not user_exists(
            chat_id
        ):

            conn.close()

            return json_error(
                "Foydalanuvchi topilmadi",
                404
            )

    conn.execute(
        """
        INSERT INTO messages
        (
            chat_type,
            chat_id,
            sender_phone,
            text,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            chat_type,
            chat_id,
            phone,
            text,
            now()
        )
    )

    conn.commit()

    message_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    row = conn.execute(
        """
        SELECT
            m.*,
            u.name AS sender_name,
            u.avatar AS sender_avatar
        FROM messages m
        LEFT JOIN users u
            ON u.phone = m.sender_phone
        WHERE m.id = ?
        """,
        (message_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "message":
            dict(row)
    })


# =========================================================
# GET MESSAGES
# =========================================================

@app.route(
    "/api/messages",
    methods=["GET"]
)
def get_messages():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    chat_type = request.args.get(
        "chat_type",
        "private"
    )

    chat_id = str(
        request.args.get(
            "chat_id",
            ""
        )
    ).strip()

    if not chat_id:
        return jsonify([])

    conn = db()

    if chat_type == "group":

        try:
            gid = int(
                chat_id
            )
        except:

            conn.close()

            return jsonify([])

        member = conn.execute(
            """
            SELECT *
            FROM group_members
            WHERE group_id = ?
            AND phone = ?
            """,
            (
                gid,
                phone
            )
        ).fetchone()

        if not member:

            conn.close()

            return jsonify([])

        rows = conn.execute(
            """
            SELECT
                m.*,
                u.name AS sender_name,
                u.avatar AS sender_avatar
            FROM messages m
            LEFT JOIN users u
                ON u.phone = m.sender_phone
            WHERE m.chat_type = 'group'
            AND m.chat_id = ?
            ORDER BY m.id ASC
            """,
            (chat_id,)
        ).fetchall()

    else:

        rows = conn.execute(
            """
            SELECT
                m.*,
                u.name AS sender_name,
                u.avatar AS sender_avatar
            FROM messages m
            LEFT JOIN users u
                ON u.phone = m.sender_phone
            WHERE m.chat_type = 'private'
            AND (
                (
                    m.sender_phone = ?
                    AND m.chat_id = ?
                )
                OR
                (
                    m.sender_phone = ?
                    AND m.chat_id = ?
                )
            )
            ORDER BY m.id ASC
            """,
            (
                phone,
                chat_id,
                chat_id,
                phone
            )
        ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# =========================================================
# VOICE MESSAGE
# =========================================================

@app.route(
    "/api/voice",
    methods=["POST"]
)
def send_voice():

    phone = logged()

    if not phone:
        return json_error(
            "Avval tizimga kiring",
            401
        )

    chat_type = str(
        request.form.get(
            "chat_type",
            "private"
        )
    )

    chat_id = str(
        request.form.get(
            "chat_id",
            ""
        )
    ).strip()

    audio = request.files.get(
        "audio"
    )

    if not chat_id:
        return json_error(
            "Chat tanlanmagan"
        )

    if not audio:
        return json_error(
            "Ovoz fayli yuborilmadi"
        )

    conn = db()

    if chat_type == "group":

        member = conn.execute(
            """
            SELECT *
            FROM group_members
            WHERE group_id = ?
            AND phone = ?
            """,
            (
                chat_id,
                phone
            )
        ).fetchone()

        if not member:

            conn.close()

            return json_error(
                "Guruh a'zosi emassiz",
                403
            )

    else:

        if not user_exists(
            chat_id
        ):

            conn.close()

            return json_error(
                "Foydalanuvchi topilmadi",
                404
            )

    ext = os.path.splitext(
        audio.filename or ""
    )[1]

    if not ext:
        ext = ".webm"

    filename = (
        str(uuid.uuid4())
        + ext
    )

    filepath = os.path.join(
        UPLOAD_DIR,
        filename
    )

    audio.save(
        filepath
    )

    audio_url = (
        "/uploads/"
        + filename
    )

    conn.execute(
        """
        INSERT INTO messages
        (
            chat_type,
            chat_id,
            sender_phone,
            text,
            audio,
            created_at
        )
        VALUES (?, ?, ?, '', ?, ?)
        """,
        (
            chat_type,
            chat_id,
            phone,
            audio_url,
            now()
        )
    )

    conn.commit()

    message_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    row = conn.execute(
        """
        SELECT
            m.*,
            u.name AS sender_name,
            u.avatar AS sender_avatar
        FROM messages m
        LEFT JOIN users u
            ON u.phone = m.sender_phone
        WHERE m.id = ?
        """,
        (message_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "message":
            dict(row)
    })


# =========================================================
# HEALTH
# =========================================================

@app.route(
    "/api/health"
)
def health():

    return jsonify({
        "success": True,
        "app": "BMAXGRAM",
        "database": "SQLite",
        "status": "online"
    })


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )