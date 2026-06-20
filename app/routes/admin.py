from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from app import db
from app.grid import (
    calendar_weeks,
    compute_heatmap,
    compute_slot_attendees,
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
        "show_grid_tabs": False,
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
