from __future__ import annotations

import html
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from app.grid import format_selected_slots_overview
from app.i18n import translate
from app.models import Poll, Response

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(address: str) -> bool:
    return bool(address and len(address) <= 254 and _EMAIL_RE.match(address))


def smtp_enabled() -> bool:
    return bool(current_app.config.get("SMTP_HOST") and current_app.config.get("SMTP_FROM"))


def _email_shell(*, lang: str, title: str, body_html: str, footer_text: str, footer_url: str = "") -> str:
    safe_title = html.escape(title)
    footer_url_html = ""
    if footer_url:
        footer_url_html = f'<br><span style="word-break:break-all;">{html.escape(footer_url)}</span>'
    return f"""\
<!DOCTYPE html>
<html lang="{html.escape(lang)}">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:system-ui,-apple-system,sans-serif;color:#1a1a1a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:24px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border:1px solid #e4e4e7;border-radius:8px;">
        <tr><td style="padding:28px 24px 8px;">
          <p style="margin:0 0 8px;font-size:13px;color:#71717a;text-transform:uppercase;letter-spacing:0.04em;">Who Has Time?</p>
          <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;font-weight:600;">{safe_title}</h1>
          {body_html}
          <p style="margin:0;font-size:12px;line-height:1.5;color:#71717a;border-top:1px solid #e4e4e7;padding-top:16px;">{html.escape(footer_text)}{footer_url_html}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _email_button(href: str, label: str) -> str:
    return (
        f'<a href="{html.escape(href)}" '
        f'style="display:inline-block;padding:10px 18px;background:#2ecc71;color:#ffffff;'
        f'text-decoration:none;border-radius:6px;font-size:15px;font-weight:500;">'
        f"{html.escape(label)}</a>"
    )


def _deliver_email(*, to_email: str, subject: str, plain_body: str, html_body: str) -> None:
    if not smtp_enabled():
        raise RuntimeError("SMTP is not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = current_app.config["SMTP_FROM"]
    msg["To"] = to_email
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host = current_app.config["SMTP_HOST"]
    port = current_app.config["SMTP_PORT"]
    user = current_app.config.get("SMTP_USER") or None
    password = current_app.config.get("SMTP_PASSWORD") or None
    use_tls = current_app.config.get("SMTP_USE_TLS", True)

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


def send_edit_link_email(
    *,
    to_email: str,
    poll: Poll,
    response: Response,
    edit_url: str,
    lang: str,
) -> None:
    if not smtp_enabled():
        raise RuntimeError("SMTP is not configured")

    slot_lines = format_selected_slots_overview(poll, response.get_slot_indices(), lang)
    subject = translate(lang, "email_edit_link_subject", title=poll.title)
    greeting = translate(lang, "email_edit_link_greeting", name=response.display_name)
    intro = translate(lang, "email_edit_link_intro", title=poll.title)
    link_label = translate(lang, "email_edit_link_button")
    availability_heading = translate(lang, "email_edit_link_availability")
    footer = translate(lang, "email_edit_link_footer")

    plain_slots = "\n".join(f"  • {line}" for line in slot_lines) or f"  • {translate(lang, 'email_no_slots')}"
    plain_body = (
        f"{greeting}\n\n"
        f"{intro}\n\n"
        f"{edit_url}\n\n"
        f"{availability_heading}\n"
        f"{plain_slots}\n\n"
        f"{footer}"
    )

    slot_items = "".join(f"<li>{html.escape(line)}</li>" for line in slot_lines)
    if not slot_items:
        slot_items = f"<li>{html.escape(translate(lang, 'email_no_slots'))}</li>"

    body_html = (
        f'<p style="margin:0 0 20px;font-size:15px;line-height:1.5;color:#3f3f46;">'
        f"{html.escape(greeting)} {html.escape(intro)}</p>"
        f'<p style="margin:0 0 24px;">{_email_button(edit_url, link_label)}</p>'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#18181b;">'
        f"{html.escape(availability_heading)}</p>"
        f'<ul style="margin:0 0 24px;padding-left:20px;font-size:14px;line-height:1.6;color:#3f3f46;">'
        f"{slot_items}</ul>"
    )
    html_body = _email_shell(
        lang=lang,
        title=poll.title,
        body_html=body_html,
        footer_text=footer,
        footer_url=edit_url,
    )

    _deliver_email(
        to_email=to_email,
        subject=subject,
        plain_body=plain_body,
        html_body=html_body,
    )


def send_poll_links_email(
    *,
    to_email: str,
    poll: Poll,
    participant_url: str,
    admin_url: str,
    lang: str,
) -> None:
    subject = translate(lang, "email_poll_links_subject", title=poll.title)
    intro = translate(lang, "email_poll_links_intro", title=poll.title)
    participant_label = translate(lang, "email_poll_links_participant_button")
    participant_hint = translate(lang, "email_poll_links_participant_hint")
    admin_label = translate(lang, "email_poll_links_admin_button")
    admin_hint = translate(lang, "email_poll_links_admin_hint")
    footer = translate(lang, "email_poll_links_footer")

    plain_body = (
        f"{intro}\n\n"
        f"{participant_hint}\n{participant_url}\n\n"
        f"{admin_hint}\n{admin_url}\n\n"
        f"{footer}"
    )

    body_html = (
        f'<p style="margin:0 0 24px;font-size:15px;line-height:1.5;color:#3f3f46;">{html.escape(intro)}</p>'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#18181b;">'
        f"{html.escape(participant_hint)}</p>"
        f'<p style="margin:0 0 20px;">{_email_button(participant_url, participant_label)}</p>'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#18181b;">'
        f"{html.escape(admin_hint)}</p>"
        f'<p style="margin:0 0 24px;">{_email_button(admin_url, admin_label)}</p>'
    )
    html_body = _email_shell(
        lang=lang,
        title=poll.title,
        body_html=body_html,
        footer_text=footer,
    )

    _deliver_email(
        to_email=to_email,
        subject=subject,
        plain_body=plain_body,
        html_body=html_body,
    )
