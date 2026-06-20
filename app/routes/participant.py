import time
from collections import defaultdict

from flask import Blueprint, abort, current_app, g, jsonify, render_template, request

from app import db
from app.grid import (
    calendar_weeks,
    compute_heatmap,
    day_labels,
    generate_slots,
    slot_map,
    unique_time_rows,
    weekday_headers,
)
from app.i18n import translate
from app.models import Poll, Response
from app.email import is_valid_email, send_edit_link_email, smtp_enabled
from app.routes.public import build_edit_url
from app.security import validate_csrf_token

bp = Blueprint("participant", __name__)

_rate_limits: dict[str, list[float]] = defaultdict(list)
_email_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60
_RATE_MAX = 30
_EMAIL_RATE_MAX = 5


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _get_poll(participant_token: str) -> Poll:
    poll = Poll.query.filter_by(participant_token=participant_token).first()
    if not poll:
        abort(404)
    return poll


def _check_rate_limit(store: dict[str, list[float]], max_hits: int) -> bool:
    ip = request.remote_addr or "unknown"
    now = time.time()
    hits = [t for t in store[ip] if now - t < _RATE_WINDOW]
    if len(hits) >= max_hits:
        return False
    hits.append(now)
    store[ip] = hits
    return True


def _check_rate_limit_save() -> bool:
    return _check_rate_limit(_rate_limits, _RATE_MAX)


def _check_rate_limit_email() -> bool:
    return _check_rate_limit(_email_rate_limits, _EMAIL_RATE_MAX)


def _grid_context(poll: Poll, mode: str = "select", response: Response | None = None):
    responses = poll.responses
    slots = generate_slots(poll)
    heatmap = compute_heatmap(poll, responses)
    selected = set(response.get_slot_indices()) if response else set()
    return {
        "poll": poll,
        "mode": mode,
        "slots": slots,
        "time_rows": unique_time_rows(poll),
        "days": day_labels(poll, g.lang),
        "weekday_headers": weekday_headers(g.lang),
        "calendar_weeks": calendar_weeks(poll, g.lang),
        "heatmap": heatmap,
        "response_count": len(responses),
        "selected_slots": sorted(selected),
        "slot_indices": slot_map(poll),
        "response": response,
        "can_edit": not poll.is_closed,
        "email_enabled": smtp_enabled(),
    }


@bp.route("/poll/<participant_token>")
def view_poll(participant_token: str):
    poll = _get_poll(participant_token)
    edit_token = request.args.get("edit")
    response = None
    if edit_token:
        response = Response.query.filter_by(edit_token=edit_token, poll_id=poll.id).first()
    return render_template(
        "poll/grid.html",
        **_grid_context(poll, mode="select", response=response),
    )


@bp.route("/poll/<participant_token>/results")
def view_results(participant_token: str):
    poll = _get_poll(participant_token)
    return render_template(
        "poll/grid.html",
        **_grid_context(poll, mode="heatmap"),
    )


@bp.route("/poll/<participant_token>/responses/<edit_token>")
def get_response(participant_token: str, edit_token: str):
    poll = _get_poll(participant_token)
    response = Response.query.filter_by(edit_token=edit_token, poll_id=poll.id).first()
    if not response:
        abort(404)
    return jsonify(
        {
            "id": response.id,
            "edit_token": response.edit_token,
            "edit_url": build_edit_url(poll.participant_token, response.edit_token),
            "display_name": response.display_name,
            "selected_slots": response.get_slot_indices(),
            "updated_at": response.updated_at.isoformat(),
        }
    )


@bp.route("/poll/<participant_token>/responses", methods=["POST"])
def save_response(participant_token: str):
    poll = _get_poll(participant_token)
    if poll.is_closed:
        return jsonify({"error": _t("error_poll_closed")}), 403

    if not _check_rate_limit_save():
        return jsonify({"error": _t("error_rate_limit")}), 429

    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        return jsonify({"error": _t("error_csrf")}), 400

    data = request.get_json(silent=True) or {}
    display_name = (data.get("display_name") or request.form.get("display_name") or "").strip()
    if not display_name:
        return jsonify({"error": _t("error_name_required")}), 400
    if len(display_name) > 100:
        return jsonify({"error": _t("error_name_too_long")}), 400

    raw_slots = data.get("selected_slots")
    if raw_slots is None:
        return jsonify({"error": _t("error_slots_required")}), 400
    if not isinstance(raw_slots, list):
        return jsonify({"error": _t("error_slots_list")}), 400

    max_index = len(generate_slots(poll)) - 1
    indices: list[int] = []
    for item in raw_slots:
        try:
            index = int(item)
        except (TypeError, ValueError):
            return jsonify({"error": _t("error_slot_invalid")}), 400
        if index < 0 or index > max_index:
            return jsonify({"error": _t("error_slot_range")}), 400
        indices.append(index)

    edit_token = data.get("edit_token")
    created = False
    if edit_token:
        response = Response.query.filter_by(edit_token=edit_token, poll_id=poll.id).first()
        if not response:
            return jsonify({"error": _t("error_response_not_found")}), 404
    else:
        response = Response(poll_id=poll.id, display_name=display_name)
        db.session.add(response)
        created = True

    response.display_name = display_name
    response.set_slot_indices(indices)
    db.session.commit()

    heatmap = compute_heatmap(poll, poll.responses)
    return jsonify(
        {
            "id": response.id,
            "edit_token": response.edit_token,
            "edit_url": build_edit_url(poll.participant_token, response.edit_token),
            "created": created,
            "display_name": response.display_name,
            "selected_slots": response.get_slot_indices(),
            "response_count": len(poll.responses),
            "heatmap": heatmap,
        }
    )


@bp.route("/poll/<participant_token>/responses/send-edit-link", methods=["POST"])
def send_edit_link(participant_token: str):
    poll = _get_poll(participant_token)

    if not smtp_enabled():
        return jsonify({"error": _t("error_email_not_configured")}), 503

    if not _check_rate_limit_email():
        return jsonify({"error": _t("error_rate_limit")}), 429

    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not validate_csrf_token(current_app.config["SECRET_KEY"], token):
        return jsonify({"error": _t("error_csrf")}), 400

    data = request.get_json(silent=True) or {}
    edit_token = (data.get("edit_token") or "").strip()
    if not edit_token:
        return jsonify({"error": _t("error_response_not_found")}), 400

    response = Response.query.filter_by(edit_token=edit_token, poll_id=poll.id).first()
    if not response:
        return jsonify({"error": _t("error_response_not_found")}), 404

    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": _t("error_email_required")}), 400
    if not is_valid_email(email):
        return jsonify({"error": _t("error_email_invalid")}), 400

    edit_url = build_edit_url(poll.participant_token, response.edit_token)
    try:
        send_edit_link_email(
            to_email=email,
            poll=poll,
            response=response,
            edit_url=edit_url,
            lang=g.lang,
        )
    except Exception:
        current_app.logger.exception("Failed to send edit link email to %s", email)
        return jsonify({"error": _t("error_email_send_failed")}), 500

    return jsonify({"ok": True})
