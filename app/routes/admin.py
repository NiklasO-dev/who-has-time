import time
from collections import defaultdict
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, url_for

from app import db
from app.email import is_valid_email, send_poll_links_email, smtp_enabled
from app.grid import (
    calendar_weeks,
    compute_heatmap,
    compute_slot_attendees,
    compute_top_results,
    day_labels,
    generate_slots,
    slot_map,
    unique_time_rows,
    weekday_headers,
)
from app.i18n import month_names_short, translate
from app.models import Poll
from app.poll_form import apply_poll_form, parse_poll_form, poll_to_form_values
from app.routes.public import build_admin_url, build_participant_url
from app.security import validate_csrf_token

bp = Blueprint("admin", __name__)

_email_rate_limits: dict[str, list[float]] = defaultdict(list)
_EMAIL_RATE_WINDOW = 60
_EMAIL_RATE_MAX = 5


def _check_rate_limit_email() -> bool:
    ip = request.remote_addr or "unknown"
    now = time.time()
    hits = [t for t in _email_rate_limits[ip] if now - t < _EMAIL_RATE_WINDOW]
    if len(hits) >= _EMAIL_RATE_MAX:
        return False
    hits.append(now)
    _email_rate_limits[ip] = hits
    return True


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _get_poll(admin_token: str) -> Poll:
    poll = Poll.query.filter_by(admin_token=admin_token).first()
    if not poll:
        abort(404)
    return poll


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
        "weekday_headers": weekday_headers(g.lang),
        "calendar_weeks": calendar_weeks(poll, g.lang),
        "heatmap": heatmap,
        "response_count": total,
        "responses": responses,
        "selected_slots": [],
        "slot_indices": slot_map(poll),
        "slot_attendees": compute_slot_attendees(responses),
        "top_results": compute_top_results(poll, responses, lang=g.lang),
        "show_grid_tabs": False,
        "participant_url": build_participant_url(poll.participant_token),
        "admin_url": build_admin_url(poll.admin_token),
        "email_enabled": smtp_enabled(),
    }


@bp.route("/poll/admin/<admin_token>")
def dashboard(admin_token: str):
    poll = _get_poll(admin_token)
    ctx = _grid_context(poll, mode="heatmap")
    ctx["admin_url"] = request.url
    return render_template("admin/dashboard.html", **ctx)


@bp.route("/poll/admin/<admin_token>/send-links", methods=["POST"])
def send_links(admin_token: str):
    poll = _get_poll(admin_token)

    if not smtp_enabled():
        return jsonify({"error": _t("error_email_not_configured")}), 503

    if not _check_rate_limit_email():
        return jsonify({"error": _t("error_rate_limit")}), 429

    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        return jsonify({"error": _t("error_csrf")}), 400

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": _t("error_email_required")}), 400
    if not is_valid_email(email):
        return jsonify({"error": _t("error_email_invalid")}), 400

    participant_url = build_participant_url(poll.participant_token)
    admin_url = build_admin_url(poll.admin_token)
    try:
        send_poll_links_email(
            to_email=email,
            poll=poll,
            participant_url=participant_url,
            admin_url=admin_url,
            lang=g.lang,
        )
    except Exception:
        current_app.logger.exception("Failed to send poll links email to %s", email)
        return jsonify({"error": _t("error_email_send_failed")}), 500

    return jsonify({"ok": True})


@bp.route("/poll/admin/<admin_token>/edit", methods=["GET", "POST"])
def edit(admin_token: str):
    poll = _get_poll(admin_token)
    errors: list[str] = []
    has_responses = bool(poll.responses)
    form_values = poll_to_form_values(poll)

    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
            abort(400)

        if has_responses:
            title = (request.form.get("title") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            if not title:
                errors.append(_t("error_title_required"))
            if not errors:
                poll.title = title
                poll.description = description
                db.session.commit()
                return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)
        else:
            data, errors = parse_poll_form(
                request.form,
                lang=g.lang,
                default_timezone=poll.timezone,
                default_slot_minutes=poll.slot_minutes,
            )
            if not errors:
                apply_poll_form(poll, data)
                db.session.commit()
                return redirect(url_for("admin.dashboard", admin_token=admin_token), code=303)
            form_values = dict(request.form)

    return render_template(
        "admin/edit.html",
        poll=poll,
        errors=errors,
        form_values=form_values,
        has_responses=has_responses,
        weekday_headers=weekday_headers(g.lang),
        month_names=month_names_short(g.lang),
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
