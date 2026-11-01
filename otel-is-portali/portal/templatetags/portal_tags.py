from django import template
from django.utils.safestring import mark_safe

from .. import scoring

register = template.Library()

# Inline SVG icons (stroke-based, 24x24)
ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    "store": '<path d="M4 9h16l-1-5H5zM4 9v11h16V9M9 20v-6h6v6"/><path d="M4 9a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M17 11a3 3 0 1 0 0-6M22 21a6 6 0 0 0-4-5.6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    "translate": '<path d="M4 5h9M8.5 3v2M6 5c.5 3.5 2.5 6 5.5 7.5M11 5c-.8 3.8-3.2 6.6-7 8"/><path d="m12 21 4.5-10 4.5 10M13.6 17.5h5.8"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "megaphone": '<path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1zM15 9a3 3 0 0 1 0 6M18 6a7 7 0 0 1 0 12"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "send": '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    "check": '<path d="m5 12 5 5 9-10"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calc": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "home": '<path d="M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "meal": '<path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 3c-2 0-3 2-3 6s1 5 3 5v7"/>',
    "edit": '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "trash": '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    "pause": '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
    "play": '<path d="M7 4v16l13-8z"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    "bed": '<path d="M2 18V6M2 14h20v4M22 14v-2a3 3 0 0 0-3-3h-8v5M6.5 11.5a1.5 1.5 0 1 0 0-.01"/>',
    "paperclip": '<path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
    "upload": '<path d="M7 18a5 5 0 0 1-.6-10A6 6 0 0 1 18 9a4 4 0 0 1 0 9M12 12v8M9 15l3-3 3 3"/>',
    "id": '<rect x="3" y="5" width="18" height="15" rx="2"/><circle cx="9" cy="11" r="2.5"/><path d="M5.5 17a3.5 3.5 0 0 1 7 0M15 10h3M15 14h3"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    "building": '<path d="M3 21h18M5 21V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v16M14 9h4a1 1 0 0 1 1 1v11M8 8h2M8 12h2M8 16h2"/>',
    "shield": '<path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z"/><path d="m9 12 2 2 4-4"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
    "sparkle": '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
}

FLAGS = {
    "tr": '<svg viewBox="0 0 30 20" aria-hidden="true"><rect width="30" height="20" fill="#E30A17"/><circle cx="11" cy="10" r="5" fill="#fff"/><circle cx="12.3" cy="10" r="4" fill="#E30A17"/><path d="m16.5 10 3.7-1.2-2.3 3.1V8.1l2.3 3.1z" fill="#fff"/></svg>',
    "en": '<svg viewBox="0 0 60 30" aria-hidden="true"><rect width="60" height="30" fill="#012169"/><path d="M0 0l60 30M60 0 0 30" stroke="#fff" stroke-width="6"/><path d="M0 0l60 30M60 0 0 30" stroke="#C8102E" stroke-width="2.4"/><path d="M30 0v30M0 15h60" stroke="#fff" stroke-width="10"/><path d="M30 0v30M0 15h60" stroke="#C8102E" stroke-width="6"/></svg>',
    "ru": '<svg viewBox="0 0 30 20" aria-hidden="true"><rect width="30" height="20" fill="#fff"/><rect y="6.67" width="30" height="6.67" fill="#0039A6"/><rect y="13.33" width="30" height="6.67" fill="#D52B1E"/></svg>',
}

DEPT_PHOTOS = {
    "front_office": "1564501049412-61c2a3083791",
    "food_beverage": "1414235077428-338989a2e8c0",
    "kitchen": "1577219491135-ce391730fb2c",
    "housekeeping": "1590490360182-c33d57733427",
    "entertainment": "1540541338287-41700207dee6",
    "spa": "1544161515-4ab6ce6db874",
    "technical": "1542314831-068cd1dbfeeb",
}


@register.simple_tag
def icon(name, cls=""):
    body = ICONS.get(name, ICONS["info"])
    cls_attr = f' class="{cls}"' if cls else ""
    return mark_safe(f'<svg{cls_attr} viewBox="0 0 24 24" aria-hidden="true">{body}</svg>')


@register.simple_tag
def flag(code):
    return mark_safe(f'<span class="flag">{FLAGS.get(code, "")}</span>')


@register.filter
def dept_photo(department, width=600):
    photo = DEPT_PHOTOS.get(department, "1566073771259-6a8506099945")
    return f"https://images.unsplash.com/photo-{photo}?w={width}&q=70&auto=format&fit=crop"


@register.filter
def score_level(total):
    try:
        return scoring.level(int(total))
    except (TypeError, ValueError):
        return "low"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def initials(text):
    words = [w for w in str(text).replace("'", " ").split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


@register.filter
def money(value):
    if value in (None, ""):
        return ""
    return f"£{int(value):,}".replace(",", ".")


@register.simple_tag
def avatar(user, cls=""):
    """Round avatar: the user's photo if they have one, otherwise their initials."""
    from django.utils.html import format_html
    classes = f"avatar {cls}".strip()
    if getattr(user, "photo", None):
        return format_html('<span class="{} avatar--photo"><img src="{}" alt="" loading="lazy" decoding="async" /></span>',
                           classes, user.photo_url)
    return format_html('<span class="{}">{}</span>', classes, getattr(user, "initials", "?"))
