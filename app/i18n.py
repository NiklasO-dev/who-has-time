import json
from datetime import date
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
SUPPORTED_LANGUAGES = ["en", "de"]
DEFAULT_LANGUAGE = "en"
LANG_COOKIE = "wht_lang"

_translations: dict[str, dict[str, str]] = {}

_MONTHS_SHORT = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
}
_WEEKDAYS_SHORT = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}


def load_translations() -> None:
    for lang in SUPPORTED_LANGUAGES:
        filepath = TRANSLATIONS_DIR / f"{lang}.json"
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                _translations[lang] = json.load(f)


def get_translations(lang: str) -> dict[str, str]:
    if not _translations:
        load_translations()
    if lang in _translations:
        return _translations[lang]
    return _translations.get(DEFAULT_LANGUAGE, {})


def detect_language(accept_language: str | None, cookie_lang: str | None) -> str:
    if cookie_lang and cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang

    if accept_language:
        for part in accept_language.split(","):
            lang_tag = part.split(";")[0].strip().lower()
            if lang_tag in SUPPORTED_LANGUAGES:
                return lang_tag
            prefix = lang_tag.split("-")[0]
            if prefix in SUPPORTED_LANGUAGES:
                return prefix

    return DEFAULT_LANGUAGE


def translate(lang: str, key: str, **kwargs) -> str:
    msg = get_translations(lang).get(key, key)
    if kwargs:
        return msg.format(**kwargs)
    return msg


def format_date_short(d: date, lang: str) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    weekday = _WEEKDAYS_SHORT[lang][d.weekday()]
    month = _MONTHS_SHORT[lang][d.month - 1]
    return f"{weekday} {d.day:02d} {month}"


def format_date_day_month(d: date, lang: str) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    month = _MONTHS_SHORT[lang][d.month - 1]
    return f"{d.day:02d} {month}"


def format_date_day_month_year(d: date, lang: str) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    month = _MONTHS_SHORT[lang][d.month - 1]
    return f"{d.day:02d} {month} {d.year}"


def weekday_names_short(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    return _WEEKDAYS_SHORT[lang]


def month_names_short(lang: str) -> list[str]:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    return _MONTHS_SHORT[lang]


def format_calendar_day(d: date, lang: str) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    month = _MONTHS_SHORT[lang][d.month - 1]
    return f"{d.day} {month}"


load_translations()
