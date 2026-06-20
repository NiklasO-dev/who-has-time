from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from app import db
from app.grid import compute_heatmap, day_labels, generate_slots, slot_map, unique_time_rows
from app.i18n import translate
from app.models import Poll
from app.routes.public import _parse_date, _parse_time_to_minute, build_admin_url, build_participant_url
from app.security import validate_csrf_token

bp = Blueprint("admin", __name__)


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _get_poll(admin_token: str) -> Poll:
    poll = Poll.query.filter_by(admin_token=admin_token).first()
    if not poll:
        abort(404)
    return poll


def _minute_to_time_value(minute: int) -> str:
    h, m = divmod(minute, 60)
    return f"{h:02d}:{m:02d}"


def _grid_context(poll: Poll, mode: str = "heatmap"):
    responses = poll.responses
    slots = generate_slots(poll)
    heatmap = compute_heatmap(poll, responses)
    total = len(responses)
    return {
        "poll": poll,
        "mode": mode,
        "slots": slots,
        "time_rows": unique_time_rows(poll),
        "days": day_labels(poll, g.lang),
        "heatmap": heatmap,
        "response_count": total,
        "responses": responses,
        "selected_slots": [],
        "slot_indices": slot_map(poll),
        "participant_url": build_participant_url(poll.participant_token),
        "admin_url": build_admin_url(poll.admin_token),
    }


@bp.route("/poll/admin/<admin_token>")
def dashboard(admin_token: str):
    poll = _get_poll(admin_token)
    ctx = _grid_context(poll, mode="heatmap")
    ctx["admin_url"] = request.url
    return render_template("admin/dashboard.html", **ctx)


@bp.route("/poll/admin/<admin_token>/edit", methods=["GET", "POST"])
def edit(admin_token: str):
    poll = _get_poll(admin_token)
    errors: list[str] = []

    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
            abort(400)

        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        timezone_name = (request.form.get("timezone") or poll.timezone).strip()
        start = _parse_date(request.form.get("start_date", ""))
        end = _parse_date(request.form.get("end_date", ""))
        day_start = _parse_time_to_minute(request.form.get("day_start", ""))
        day_end = _parse_time_to_minute(request.form.get("day_end", ""))
        try:
            slot_minutes = int(request.form.get("slot_minutes", str(poll.slot_minutes)))
        except ValueError:
            slot_minutes = 0

        if not title:
            errors.append(_t("error_title_required"))

        has_responses = bool(poll.responses)

        if has_responses:
            if not errors:
                poll.title = title
                poll.description = description
                db.session.commit()
                return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)
        else:
            if not start or not end or end < start:
                errors.append(_t("error_date_range"))
            elif (end - start).days + 1 > current_app.config["MAX_POLL_DAYS"]:
                errors.append(
                    _t("error_max_days", days=current_app.config["MAX_POLL_DAYS"])
                )
            if day_start is None or day_end is None or day_end <= day_start:
                errors.append(_t("error_time_range"))
            if slot_minutes not in current_app.config["ALLOWED_SLOT_MINUTES"]:
                errors.append(_t("error_slot_minutes"))
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            try:
                ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                errors.append(_t("error_timezone"))

            if not errors:
                poll.title = title
                poll.description = description
                poll.timezone = timezone_name
                poll.start_date = start
                poll.end_date = end
                poll.day_start_minute = day_start
                poll.day_end_minute = day_end
                poll.slot_minutes = slot_minutes
                db.session.commit()
                return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)

    return render_template(
        "admin/edit.html",
        poll=poll,
        errors=errors,
        day_start_value=_minute_to_time_value(poll.day_start_minute),
        day_end_value=_minute_to_time_value(poll.day_end_minute),
        has_responses=bool(poll.responses),
        participant_url=build_participant_url(poll.participant_token),
    )


@bp.route("/poll/admin/<admin_token>/close", methods=["POST"])
def close(admin_token: str):
    poll = _get_poll(admin_token)
    token = request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        abort(400)
    if not poll.is_closed:
        poll.closed_at = datetime.now(timezone.utc)
        db.session.commit()
    return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)


@bp.route("/poll/admin/<admin_token>/reopen", methods=["POST"])
def reopen(admin_token: str):
    poll = _get_poll(admin_token)
    token = request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        abort(400)
    poll.closed_at = None
    db.session.commit()
    return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)


@bp.route("/poll/admin/<admin_token>/delete", methods=["POST"])
def delete(admin_token: str):
    poll = _get_poll(admin_token)
    token = request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        abort(400)
    db.session.delete(poll)
    db.session.commit()
    return redirect(url_for("public.index"), code=303)
