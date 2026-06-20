from datetime import date, timedelta

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from app import db
from app.grid import weekday_headers
from app.i18n import month_names_short, translate
from app.models import Poll
from app.poll_form import apply_poll_form, default_form_values, parse_poll_form
from app.security import validate_csrf_token

bp = Blueprint("public", __name__)


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _app_base_url() -> str:
    base = current_app.config.get("APP_BASE_URL") or ""
    if base:
        return base.rstrip("/")
    return request.url_root.rstrip("/")


def _form_context(form_values: dict | None, default_start: str, default_end: str) -> dict:
    return {
        "form_values": form_values,
        "default_start": default_start,
        "default_end": default_end,
        "weekday_headers": weekday_headers(g.lang),
        "month_names": month_names_short(g.lang),
    }


@bp.route("/health")
def health():
    return {"status": "ok"}


@bp.route("/")
def index():
    today = date.today()
    default_end = today + timedelta(days=6)
    defaults = default_form_values(start=today, end=default_end)
    return render_template(
        "index.html",
        form_values=defaults,
        default_start=today.isoformat(),
        default_end=default_end.isoformat(),
        weekday_headers=weekday_headers(g.lang),
        month_names=month_names_short(g.lang),
    )


@bp.route("/polls", methods=["POST"])
def create_poll():
    token = request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        abort(400)

    data, errors = parse_poll_form(request.form, lang=g.lang)

    if errors:
        form_values = dict(request.form)
        return render_template(
            "index.html",
            errors=errors,
            form_values=form_values,
            default_start=form_values.get("start_date", ""),
            default_end=form_values.get("end_date", ""),
            weekday_headers=weekday_headers(g.lang),
            month_names=month_names_short(g.lang),
        ), 400

    poll = Poll()
    apply_poll_form(poll, data)
    db.session.add(poll)
    db.session.commit()

    return redirect(url_for("admin.dashboard", admin_token=poll.admin_token), code=303)


def build_admin_url(admin_token: str) -> str:
    return f"{_app_base_url()}{url_for('admin.dashboard', admin_token=admin_token)}"


def build_participant_url(participant_token: str) -> str:
    return f"{_app_base_url()}{url_for('participant.view_poll', participant_token=participant_token)}"


@bp.app_context_processor
def url_helpers():
    return {
        "build_admin_url": build_admin_url,
        "build_participant_url": build_participant_url,
    }
