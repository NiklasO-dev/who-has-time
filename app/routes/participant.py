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
from app.security import validate_csrf_token

bp = Blueprint("participant", __name__)

_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60
_RATE_MAX = 30


def _t(key: str, **kwargs) -> str:
    return translate(g.lang, key, **kwargs)


def _get_poll(participant_token: str) -> Poll:
    poll = Poll.query.filter_by(participant_token=participant_token).first()
    if not poll:
        abort(404)
    return poll


def _check_rate_limit() -> bool:
    ip = request.remote_addr or "unknown"
    now = time.time()
    hits = [t for t in _rate_limits[ip] if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        return False
    hits.append(now)
    _rate_limits[ip] = hits
    return True


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
    }


@bp.route("/poll/<participant_token>")
def view_poll(participant_token: str):
    poll = _get_poll(participant_token)
    response_id = request.args.get("response_id")
    response = None
    if response_id:
        response = Response.query.filter_by(id=response_id, poll_id=poll.id).first()
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


@bp.route("/poll/<participant_token>/responses/<response_id>")
def get_response(participant_token: str, response_id: str):
    poll = _get_poll(participant_token)
    response = Response.query.filter_by(id=response_id, poll_id=poll.id).first()
    if not response:
        abort(404)
    return jsonify(
        {
            "id": response.id,
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

    if not _check_rate_limit():
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

    response_id = data.get("response_id")
    if response_id:
        response = Response.query.filter_by(id=response_id, poll_id=poll.id).first()
        if not response:
            return jsonify({"error": _t("error_response_not_found")}), 404
    else:
        response = Response(poll_id=poll.id, display_name=display_name)
        db.session.add(response)

    response.display_name = display_name
    response.set_slot_indices(indices)
    db.session.commit()

    heatmap = compute_heatmap(poll, poll.responses)
    return jsonify(
        {
            "id": response.id,
            "display_name": response.display_name,
            "selected_slots": response.get_slot_indices(),
            "response_count": len(poll.responses),
            "heatmap": heatmap,
        }
    )
