"""Editing users from Admin > Settings. Ownfoil only lets you create and delete them.

Errors come back as codes; the page shows them in the visitor's language.
"""

import logging
import os

from flask import jsonify, request
from flask_login import login_required
from werkzeug.security import generate_password_hash

from auth import access_required, validate_password, validate_username
from db import User, db

logger = logging.getLogger("main")


def environment_users():
    """Users the container recreates from USER_ADMIN_* / USER_GUEST_* at every start, so an
    edit made here would be undone on the next restart."""
    return {os.environ.get(f"{prefix}_NAME") for prefix in ("USER_ADMIN", "USER_GUEST")} - {None, ""}


def failure(code, message=""):
    return jsonify({"success": False, "error": code, "message": message})


def install(app):
    @app.route("/api/user/update", methods=["POST"])
    @login_required
    @access_required("admin")
    def gamedock_update_user():
        data = request.get_json(silent=True) or {}
        user = db.session.get(User, data.get("user_id"))
        if user is None:
            return failure("not_found")
        if user.user in environment_users():
            return failure("environment_user")

        name = str(data.get("user", "")).strip()
        valid, message = validate_username(name)
        if not valid:
            return failure("invalid_username", message)
        if User.query.filter(User.user == name, User.id != user.id).first():
            return failure("user_exists")

        password = data.get("password") or ""
        if password:
            valid, message = validate_password(password)
            if not valid:
                return failure("invalid_password", message)

        admin = bool(data.get("admin_access"))
        if user.admin_access and not admin and User.query.filter_by(admin_access=True).count() <= 1:
            return failure("last_admin")

        user.user = name
        user.admin_access = admin
        # Admins always have shop and backup access, as when a user is created
        user.shop_access = admin or bool(data.get("shop_access"))
        user.backup_access = admin or bool(data.get("backup_access"))
        if password:
            user.password = generate_password_hash(password, method="scrypt")
        db.session.commit()
        logger.info(f"Updated user {name} (id {user.id})")
        return jsonify({"success": True})
