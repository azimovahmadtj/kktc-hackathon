from django.utils.translation import gettext_lazy as _

from .models import Application


def portal(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    if user.is_employer:
        notif_count = Application.objects.filter(job__employer=user, status=Application.Status.SENT).count()
        nav = [
            ("dashboard", "dashboard", _("Dashboard"), "grid", 0),
            ("applications", "applications", _("Applications"), "file", notif_count),
            ("my_jobs", "my_jobs", _("My listings"), "layers", 0),
            ("market", "market", _("Market"), "store", 0),
        ]
        portal_name = _("Employer portal")
    else:
        notif_count = user.applications.filter(candidate_seen=False).count()
        nav = [
            ("dashboard", "dashboard", _("Dashboard"), "grid", 0),
            ("market", "market", _("Job ads"), "briefcase", 0),
            ("ai_match", "ai_match", _("AI matching"), "sparkle", 0),
            ("applications", "applications", _("My applications"), "file", notif_count),
            ("profile", "profile", _("My profile"), "user", 0),
        ]
        portal_name = _("Candidate portal")

    return {
        "nav_items": [{"key": k, "url_name": u, "label": l, "icon": i, "badge": b} for k, u, l, i, b in nav],
        "notif_count": notif_count,
        "portal_name": portal_name,
    }
