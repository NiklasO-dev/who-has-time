import os

from flask import Flask, g, redirect, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config, validate_secret_key
from app.i18n import (
    DEFAULT_LANGUAGE,
    LANG_COOKIE,
    SUPPORTED_LANGUAGES,
    detect_language,
    format_date_day_month,
    format_date_day_month_year,
    get_translations,
    translate,
)

db = SQLAlchemy()


def _migrate_schema() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "polls" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("polls")}
    statements: list[str] = []
    if "date_mode" not in columns:
        statements.append(
            "ALTER TABLE polls ADD COLUMN date_mode VARCHAR(10) NOT NULL DEFAULT 'range'"
        )
    if "picked_dates" not in columns:
        statements.append(
            "ALTER TABLE polls ADD COLUMN picked_dates TEXT NOT NULL DEFAULT '[]'"
        )
    if "show_names_on_heatmap" not in columns:
        statements.append(
            "ALTER TABLE polls ADD COLUMN show_names_on_heatmap BOOLEAN NOT NULL DEFAULT 0"
        )
    if "responses" in inspector.get_table_names():
        response_columns = {col["name"] for col in inspector.get_columns("responses")}
        if "edit_token" not in response_columns:
            statements.append("ALTER TABLE responses ADD COLUMN edit_token VARCHAR(64)")

    if statements:
        with db.engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))

    if "responses" in inspector.get_table_names():
        from app.models import Response
        from app.security import generate_token

        missing = Response.query.filter(
            (Response.edit_token.is_(None)) | (Response.edit_token == "")
        ).all()
        if missing:
            for response in missing:
                response.edit_token = generate_token()
            db.session.commit()


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    validate_secret_key(app.config["SECRET_KEY"])

    if os.environ.get("BEHIND_PROXY", "1") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)

    @app.before_request
    def set_language():
        if request.path.startswith("/static"):
            return
        cookie_lang = request.cookies.get(LANG_COOKIE)
        accept_lang = request.headers.get("Accept-Language")
        g.lang = detect_language(accept_lang, cookie_lang)
        g.t = get_translations(g.lang)

    @app.context_processor
    def inject_globals():
        from app.security import generate_csrf_token

        ctx = {
            "csrf_token": generate_csrf_token(app.config["SECRET_KEY"]),
            "supported_languages": SUPPORTED_LANGUAGES,
        }
        if hasattr(g, "lang"):
            ctx["lang"] = g.lang
        if hasattr(g, "t"):
            ctx["t"] = g.t
        return ctx

    @app.template_filter("tr")
    def translate_filter(key: str, **kwargs) -> str:
        lang = getattr(g, "lang", DEFAULT_LANGUAGE)
        return translate(lang, key, **kwargs)

    @app.template_filter("format_date_day_month")
    def format_date_day_month_filter(d, lang: str) -> str:
        return format_date_day_month(d, lang)

    @app.template_filter("format_date_day_month_year")
    def format_date_day_month_year_filter(d, lang: str) -> str:
        return format_date_day_month_year(d, lang)

    from app.routes.admin import bp as admin_bp
    from app.routes.participant import bp as participant_bp
    from app.routes.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(participant_bp)

    with app.app_context():
        db.create_all()
        _migrate_schema()

    @app.get("/set-lang/<lang>")
    def set_language_route(lang: str):
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        referer = request.headers.get("Referer", "/")
        response = redirect(referer, code=303)
        response.set_cookie(LANG_COOKIE, lang, max_age=365 * 24 * 3600, samesite="Lax")
        return response

    return app
