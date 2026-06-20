from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from app import db
from app.i18n import translate
from app.models import Poll
from app.security import validate_csrf_token

bp = Blueprint("public", __name__)


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _app_base_url() -> str:
    base = current_app.config.get("APP_BASE_URL") or ""
    if base:
        return base.rstrip("/")
    return request.url_root.rstrip("/")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_time_to_minute(value: str) -> int | None:
    if not value or ":" not in value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def _validate_poll_form(
    title: str,
    start: date | None,
    end: date | None,
    day_start: int | None,
    day_end: int | None,
    slot_minutes: int,
    timezone_name: str,
) -> list[str]:
    errors: list[str] = []
    if not title:
        errors.append(_t("error_title_required"))
    if len(title) > 200:
        errors.append(_t("error_title_too_long"))
    if not start or not end:
        errors.append(_t("error_dates_required"))
    elif end < start:
        errors.append(_t("error_end_before_start"))
    elif (end - start).days + 1 > current_app.config["MAX_POLL_DAYS"]:
        errors.append(
            _t("error_max_days", days=current_app.config["MAX_POLL_DAYS"])
        )
    if day_start is None or day_end is None:
        errors.append(_t("error_times_required"))
    elif day_end <= day_start:
        errors.append(_t("error_end_time_before_start"))
    if slot_minutes not in current_app.config["ALLOWED_SLOT_MINUTES"]:
        errors.append(_t("error_slot_minutes"))
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        errors.append(_t("error_timezone"))
    return errors


@bp.route("/health")
def health():
    return {"status": "ok"}


@bp.route("/")
def index():
    today = date.today()
    default_end = today + timedelta(days=6)
    return render_template(
        "index.html",
        default_start=today.isoformat(),
        default_end=default_end.isoformat(),
        form=None,
    )


@bp.route("/polls", methods=["POST"])
def create_poll():
    token = request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        abort(400)

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    timezone_name = (request.form.get("timezone") or "UTC").strip()
    start = _parse_date(request.form.get("start_date", ""))
    end = _parse_date(request.form.get("end_date", ""))
    day_start = _parse_time_to_minute(request.form.get("day_start", "08:00"))
    day_end = _parse_time_to_minute(request.form.get("day_end", "22:00"))

    try:
        slot_minutes = int(request.form.get("slot_minutes", "30"))
    except ValueError:
        slot_minutes = 0

    errors = _validate_poll_form(
        title, start, end, day_start, day_end, slot_minutes, timezone_name
    )

    if errors:
        return render_template(
            "index.html",
            errors=errors,
            form=request.form,
            default_start=request.form.get("start_date", ""),
            default_end=request.form.get("end_date", ""),
        ), 400

    poll = Poll(
        title=title,
        description=description,
        timezone=timezone_name,
        start_date=start,
        end_date=end,
        day_start_minute=day_start,
        day_end_minute=day_end,
        slot_minutes=slot_minutes,
    )
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
