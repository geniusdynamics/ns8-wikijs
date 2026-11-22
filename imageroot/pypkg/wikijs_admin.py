# SPDX-License-Identifier: GPL-3.0-or-later
"""Initial Wiki.js administrator account.

Wiki.js 3 has no setup wizard: it creates its first administrator from the
ADMIN_EMAIL and ADMIN_PASS environment variables when it initializes an empty
database (backend/models/users.ts, init()), or admin@example.com with the
password 12345678 when they are unset.

The credentials are kept in state/admin.env (mode 0600), which is never passed
to the container. The container gets state/admin-init.env instead, with the
administrator email and a random one-time password, so the real password is
not in the container configuration. Once Wiki.js is running, a changed email or
password is written to the root administrator account (settings "auth"
rootAdminUserId). The bcrypt hash is computed by the bcryptjs package of the Wiki.js
image, reading the password from stdin: it never appears in argv, SQL or logs.
"""
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

PATH = Path("admin.env")
PENDING = Path("admin.pending")
INIT = Path("admin-init.env")
MIN_LENGTH = 12
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class AdminError(ValueError):
    def __init__(self, field, key):
        super().__init__(key)
        self.field = field
        self.key = key


def read():
    values = {}
    try:
        for line in PATH.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key] = value
    except FileNotFoundError:
        pass
    return values


def email():
    return read().get("ADMIN_EMAIL", "")


def password_set():
    return bool(read().get("ADMIN_PASS"))


def validate(request):
    """Return (email, password) to store, or None when the request has no admin fields."""
    new_email = request.get("admin_email")
    new_password = request.get("admin_password") or ""
    if new_email is None and not new_password:
        return None
    current = read()
    address = (new_email if new_email is not None else current.get("ADMIN_EMAIL", "")).strip().lower()
    if not address and not new_password:
        return None
    if not EMAIL.fullmatch(address) or len(address) > 255:
        raise AdminError("admin_email", "admin_email_invalid")
    if new_password:
        if len(new_password) < MIN_LENGTH or len(new_password.encode()) > 72:
            raise AdminError("admin_password", "admin_password_length")
        if any(ord(c) < 32 or ord(c) == 127 for c in new_password):
            raise AdminError("admin_password", "admin_password_invalid")
    elif not current.get("ADMIN_PASS"):
        raise AdminError("admin_password", "admin_password_required")
    password = new_password or current["ADMIN_PASS"]
    if address == current.get("ADMIN_EMAIL") and password == current.get("ADMIN_PASS"):
        return None
    return address, password


def store(values):
    address, password = values
    tmp = PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(f"ADMIN_EMAIL={address}\nADMIN_PASS={password}\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)
    PENDING.touch()


def write_init():
    """Write the env file of the container: real email, random one-time password."""
    address = read().get("ADMIN_EMAIL", "")
    fd = os.open(INIT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        if address:
            stream.write(f"ADMIN_EMAIL={address}\nADMIN_PASS={secrets.token_urlsafe(32)}\n")
    os.chmod(INIT, 0o600)


def sql(statement):
    result = subprocess.run(["podman", "exec", "-i", "postgresql-app", "psql", "-XAt", "-v",
                             "ON_ERROR_STOP=1", "-U", "postgres", "-d", "wikijs"],
                            input=statement, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("Wiki.js database could not apply the administrator account")
    return result.stdout.strip()


def literal(value):
    return "'" + value.replace("'", "''") + "'"


HASH_SCRIPT = ("import bcrypt from 'bcryptjs';"
               "let s='';process.stdin.setEncoding('utf8');"
               "for await (const c of process.stdin) s+=c;"
               "process.stdout.write(await bcrypt.hash(s,12));")


def bcrypt_hash(password):
    result = subprocess.run(["podman", "exec", "-i", "-w", "/wiki/backend", "wikijs-app", "node",
                             "--input-type=module", "-e", HASH_SCRIPT],
                            input=password, text=True, capture_output=True)
    digest = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"\$2[aby]\$12\$[./A-Za-z0-9]{53}", digest):
        raise RuntimeError("Could not hash the Wiki.js administrator password")
    return digest


def apply():
    """Write the stored credentials to the root administrator. Wiki.js must be running."""
    if not PENDING.exists():
        return False
    values = read()
    if not values.get("ADMIN_EMAIL") or not values.get("ADMIN_PASS"):
        PENDING.unlink(missing_ok=True)
        return False
    local_id = sql("SELECT id FROM wiki.authentication WHERE module='local' ORDER BY id LIMIT 1;")
    admin_id = sql("SELECT value->>'rootAdminUserId' FROM wiki.settings WHERE key='auth';")
    if not local_id or not admin_id:
        raise RuntimeError("Wiki.js root administrator not found")
    digest = bcrypt_hash(values["ADMIN_PASS"])
    entry = json.dumps({"password": digest, "mustChangePwd": False})
    sql(f"""UPDATE wiki.users SET email={literal(values['ADMIN_EMAIL'])},
        auth=COALESCE(auth,'{{}}'::jsonb) || jsonb_build_object({literal(local_id)},
          COALESCE(auth->{literal(local_id)},'{{}}'::jsonb) || {literal(entry)}::jsonb),
        "updatedAt"=now()
        WHERE id={literal(admin_id)}::uuid;""")
    PENDING.unlink(missing_ok=True)
    return True
