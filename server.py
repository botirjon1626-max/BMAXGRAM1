from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename
import os
import random
import uuid
from datetime import datetime

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "BMAXGRAM_TEST_SECRET_2026"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
UPLOAD_DIR = os.path.join(PUBLIC_DIR, "uploads")

os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# TEST DATABASE
# ============================================================

users = {}
contacts = {}
groups = {}
messages = {}

verification_codes = {}


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.utcnow().isoformat()


def current_phone():
    return session.get("phone")


def require_login():
    phone = current_phone()

    if not phone:
        return None

    return phone


def clean_phone(phone):
    if not phone:
        return ""

    return str(phone).strip()


def make_user(phone):
    if phone not in users:
        users[phone] = {
            "phone": phone,
            "name": phone,
            "bio": "",
            "avatar": "",
            "created_at": now()
        }

    return users[phone]


def contact_exists(owner, phone):
    return any(
        c["phone"] == phone
        for c in contacts.get(owner, [])
    )


def save_upload(file):

    if not file:
        return ""

    filename = secure_filename(
        file.filename or "file"
    )

    if not filename:
        filename = "file"

    extension = os.path.splitext(filename)[1]

    filename = (
        str(uuid.uuid4())
        + extension
    )

    path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    file.save(path)

    return "/uploads/" + filename


# ============================================================
# STATIC WEBSITE
# ============================================================

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


# ============================================================
# RANDOM LOGIN CODE
# ============================================================

@app.route(
    "/api/request_code",
    methods=["POST"]
)
def request_code():

    data = request.get_json(
        silent=True
    ) or {}

    phone = clean_phone(
        data.get("phone")
    )

    if not phone:
        return jsonify({
            "message":
            "Telefon raqam kiriting"
        }), 400

    # RANDOM 6 XONALI KOD
    code = str(
        random.randint(
            100000,
            999999
        )
    )

    verification_codes[phone] = code

    # Test rejimida SMS yuborilmaydi.
    # Kod saytga qaytariladi.
    return jsonify({
        "success": True,
        "code": code
    })


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
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

    if not phone:
        return jsonify({
            "message":
            "Telefon raqam kiriting"
        }), 400

    if not code:
        return jsonify({
            "message":
            "Kod kiriting"
        }), 400

    saved_code = verification_codes.get(
        phone
    )

    if saved_code != code:

        return jsonify({
            "message":
            "Kod noto'g'ri"
        }), 401

    make_user(phone)

    session["phone"] = phone

    # Bir marta ishlatiladigan kod
    verification_codes.pop(
        phone,
        None
    )

    return jsonify({
        "success": True,
        "phone": phone
    })


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True
    })


# ============================================================
# PROFILE
# ============================================================

@app.route(
    "/api/profile",
    methods=["GET", "POST"]
)
def profile():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    user = make_user(phone)

    if request.method == "GET":

        return jsonify({
            "user": user
        })


    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            user["name"]
        )
    ).strip()

    bio = str(
        data.get(
            "bio",
            user["bio"]
        )
    ).strip()

    avatar = data.get(
        "avatar",
        user["avatar"]
    )

    user["name"] = (
        name
        if name
        else phone
    )

    user["bio"] = bio

    if avatar:
        user["avatar"] = avatar

    return jsonify({
        "success": True,
        "user": user
    })


# ============================================================
# CONTACTS - GET
# ============================================================

@app.route(
    "/api/contacts",
    methods=["GET"]
)
def get_contacts():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    result = []

    for contact in contacts.get(
        phone,
        []
    ):

        target = users.get(
            contact["phone"]
        )

        item = dict(contact)

        if target:

            item["avatar"] = target.get(
                "avatar",
                ""
            )

            if not item.get("name"):
                item["name"] = target.get(
                    "name",
                    contact["phone"]
                )

        result.append(item)

    return jsonify(result)


# ============================================================
# CONTACTS - ADD
# ============================================================

@app.route(
    "/api/contacts",
    methods=["POST"]
)
def add_contact():

    owner = require_login()

    if not owner:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    phone = clean_phone(
        data.get("phone")
    )

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    if not phone:

        return jsonify({
            "message":
            "Telefon raqam kiriting"
        }), 400

    if phone == owner:

        return jsonify({
            "message":
            "O'zingizni kontaktga qo'sha olmaysiz"
        }), 400

    if phone not in users:

        return jsonify({
            "message":
            "Bu raqam bilan foydalanuvchi topilmadi. Avval u BMAXGRAM'ga kirishi kerak."
        }), 404

    if contact_exists(
        owner,
        phone
    ):

        return jsonify({
            "message":
            "Bu kontakt allaqachon mavjud"
        }), 400

    if owner not in contacts:

        contacts[owner] = []

    target = users[phone]

    contacts[owner].append({
        "phone": phone,
        "name":
            name
            or target.get(
                "name",
                phone
            ),
        "avatar":
            target.get(
                "avatar",
                ""
            )
    })

    return jsonify({
        "success": True
    })


# ============================================================
# GROUPS - GET
# ============================================================

@app.route(
    "/api/groups",
    methods=["GET"]
)
def get_groups():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    result = []

    for group in groups.values():

        if phone not in group["members"]:

            continue

        result.append({
            "id": group["id"],
            "name": group["name"],
            "avatar": group.get(
                "avatar",
                ""
            ),
            "member_count":
                len(group["members"])
        })

    return jsonify(result)


# ============================================================
# CREATE GROUP
# ============================================================

@app.route(
    "/api/groups",
    methods=["POST"]
)
def create_group():

    owner = require_login()

    if not owner:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    avatar = data.get(
        "avatar",
        ""
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

    if not isinstance(
        members,
        list
    ):

        members = []

    valid_members = []

    for phone in members:

        phone = clean_phone(
            phone
        )

        if (
            phone
            and phone in users
            and phone != owner
        ):

            if phone not in valid_members:

                valid_members.append(
                    phone
                )

    if owner not in valid_members:

        valid_members.insert(
            0,
            owner
        )

    group_id = len(groups) + 1

    while group_id in groups:
        group_id += 1

    groups[group_id] = {
        "id": group_id,
        "name": name,
        "avatar": avatar,
        "owner": owner,
        "members": valid_members,
        "created_at": now()
    }

    return jsonify({
        "success": True,
        "group": groups[group_id]
    })


# ============================================================
# GROUP INFO
# ============================================================

@app.route(
    "/api/groups/<int:group_id>",
    methods=["GET"]
)
def group_info(group_id):

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    group = groups.get(
        group_id
    )

    if not group:

        return jsonify({
            "message":
            "Guruh topilmadi"
        }), 404

    if phone not in group["members"]:

        return jsonify({
            "message":
            "Siz bu guruh a'zosi emassiz"
        }), 403

    member_list = []

    for member_phone in group["members"]:

        user = make_user(
            member_phone
        )

        role = (
            "admin"
            if member_phone ==
            group["owner"]
            else "member"
        )

        member_list.append({
            "phone":
                user["phone"],
            "name":
                user["name"],
            "avatar":
                user["avatar"],
            "role":
                role
        })

    return jsonify({
        "group": group,
        "members": member_list
    })


# ============================================================
# ADD GROUP MEMBER
# ============================================================

@app.route(
    "/api/groups/<int:group_id>/members",
    methods=["POST"]
)
def add_group_member(group_id):

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    group = groups.get(
        group_id
    )

    if not group:

        return jsonify({
            "message":
            "Guruh topilmadi"
        }), 404

    if phone not in group["members"]:

        return jsonify({
            "message":
            "Siz guruh a'zosi emassiz"
        }), 403

    # Hozircha guruhdagi barcha a'zolarga
    # odam qo'shishga ruxsat beriladi.

    data = request.get_json(
        silent=True
    ) or {}

    new_phone = clean_phone(
        data.get("phone")
    )

    if not new_phone:

        return jsonify({
            "message":
            "Telefon raqam kiriting"
        }), 400

    if new_phone not in users:

        return jsonify({
            "message":
            "Bu foydalanuvchi BMAXGRAM'da ro'yxatdan o'tmagan"
        }), 404

    if new_phone in group["members"]:

        return jsonify({
            "message":
            "Bu odam allaqachon guruhda"
        }), 400

    group["members"].append(
        new_phone
    )

    return jsonify({
        "success": True,
        "message":
            "Odam guruhga qo'shildi"
    })


# ============================================================
# MESSAGES
# ============================================================

def private_key(a, b):

    return (
        "private:"
        + ":".join(
            sorted([
                a,
                b
            ])
        )
    )


def group_key(group_id):

    return (
        "group:"
        + str(group_id)
    )


@app.route(
    "/api/messages",
    methods=["GET"]
)
def get_messages():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    receiver = clean_phone(
        request.args.get(
            "receiver"
        )
    )

    chat_type = request.args.get(
        "chat_type",
        "private"
    )

    if not receiver:

        return jsonify([])


    if chat_type == "group":

        try:
            group_id = int(
                receiver
            )
        except:

            return jsonify({
                "message":
                "Noto'g'ri guruh"
            }), 400

        group = groups.get(
            group_id
        )

        if not group:

            return jsonify({
                "message":
                "Guruh topilmadi"
            }), 404

        if phone not in group["members"]:

            return jsonify({
                "message":
                "Guruh a'zosi emassiz"
            }), 403

        key = group_key(
            group_id
        )

    else:

        if receiver not in users:

            return jsonify([])

        key = private_key(
            phone,
            receiver
        )


    return jsonify(
        messages.get(
            key,
            []
        )
    )


# ============================================================
# SEND TEXT MESSAGE
# ============================================================

@app.route(
    "/api/messages",
    methods=["POST"]
)
def send_message():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    receiver = clean_phone(
        data.get(
            "receiver"
        )
    )

    chat_type = data.get(
        "chat_type",
        "private"
    )

    text = str(
        data.get(
            "text",
            ""
        )
    ).strip()

    if not text:

        return jsonify({
            "message":
            "Xabar bo'sh"
        }), 400


    if chat_type == "group":

        try:
            group_id = int(
                receiver
            )
        except:

            return jsonify({
                "message":
                "Noto'g'ri guruh"
            }), 400

        group = groups.get(
            group_id
        )

        if not group:

            return jsonify({
                "message":
                "Guruh topilmadi"
            }), 404

        if phone not in group["members"]:

            return jsonify({
                "message":
                "Guruh a'zosi emassiz"
            }), 403

        key = group_key(
            group_id
        )

    else:

        if receiver not in users:

            return jsonify({
                "message":
                "Foydalanuvchi topilmadi"
            }), 404

        key = private_key(
            phone,
            receiver
        )


    user = make_user(
        phone
    )

    message = {
        "id": str(
            uuid.uuid4()
        ),
        "sender": phone,
        "sender_name":
            user["name"],
        "receiver":
            receiver,
        "chat_type":
            chat_type,
        "text":
            text,
        "audio":
            "",
        "created_at":
            now()
    }

    if key not in messages:

        messages[key] = []

    messages[key].append(
        message
    )

    return jsonify({
        "success": True,
        "message": message
    })


# ============================================================
# VOICE MESSAGE
# ============================================================

@app.route(
    "/api/voice",
    methods=["POST"]
)
def send_voice():

    phone = require_login()

    if not phone:

        return jsonify({
            "message":
            "Avval tizimga kiring"
        }), 401

    receiver = clean_phone(
        request.form.get(
            "receiver"
        )
    )

    chat_type = request.form.get(
        "chat_type",
        "private"
    )

    audio = request.files.get(
        "audio"
    )

    if not receiver:

        return jsonify({
            "message":
            "Qabul qiluvchi ko'rsatilmagan"
        }), 400

    if not audio:

        return jsonify({
            "message":
            "Ovoz fayli topilmadi"
        }), 400


    if chat_type == "group":

        try:
            group_id = int(
                receiver
            )
        except:

            return jsonify({
                "message":
                "Noto'g'ri guruh"
            }), 400

        group = groups.get(
            group_id
        )

        if not group:

            return jsonify({
                "message":
                "Guruh topilmadi"
            }), 404

        if phone not in group["members"]:

            return jsonify({
                "message":
                "Guruh a'zosi emassiz"
            }), 403

        key = group_key(
            group_id
        )

    else:

        if receiver not in users:

            return jsonify({
                "message":
                "Foydalanuvchi topilmadi"
            }), 404

        key = private_key(
            phone,
            receiver
        )


    audio_url = save_upload(
        audio
    )

    user = make_user(
        phone
    )

    message = {
        "id": str(
            uuid.uuid4()
        ),
        "sender": phone,
        "sender_name":
            user["name"],
        "receiver":
            receiver,
        "chat_type":
            chat_type,
        "text":
            "",
        "audio":
            audio_url,
        "created_at":
            now()
    }

    if key not in messages:

        messages[key] = []

    messages[key].append(
        message
    )

    return jsonify({
        "success": True,
        "message": message
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/api/health"
)
def health():

    return jsonify({
        "status":
            "ok",
        "name":
            "BMAXGRAM",
        "users":
            len(users),
        "groups":
            len(groups)
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "message":
            "API manzili topilmadi"
        }), 404

    return (
        "BMAXGRAM sahifasi topilmadi",
        404
    )


@app.errorhandler(500)
def server_error(error):

    return jsonify({
        "message":
        "Serverda ichki xatolik yuz berdi"
    }), 500


# ============================================================
# RUN
# ============================================================

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