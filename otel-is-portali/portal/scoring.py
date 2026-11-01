"""
Match score (0–100) between a candidate profile and a job ad.

    Department    30   same department as the job
    Language      25   share of the job's required languages the candidate speaks
    Experience    20   candidate years / required years (capped)
    Availability  15   candidate availability fits the employment type
    Accommodation 10   candidate does not need housing, or the job provides it

75+ = high, 50–74 = medium, 0–49 = low
"""
from django.utils.translation import gettext_lazy as _

from .models import Availability

WEIGHTS = {
    "department": 30,
    "language": 25,
    "experience": 20,
    "availability": 15,
    "accommodation": 10,
}

LABELS = {
    "department": _("Department"),
    "language": _("Language"),
    "experience": _("Experience"),
    "availability": _("Availability"),
    "accommodation": _("Accommodation"),
}


def compute(profile, job):
    """Return {"total": int, "parts": {key: points}}."""
    parts = {}
    parts["department"] = WEIGHTS["department"] if profile.department and profile.department == job.department else 0

    required = set(job.required_languages or [])
    spoken = set(profile.languages or [])
    if required:
        parts["language"] = round(WEIGHTS["language"] * len(required & spoken) / len(required))
    else:
        parts["language"] = WEIGHTS["language"] if spoken else 0

    if job.min_experience <= 0:
        parts["experience"] = WEIGHTS["experience"]
    else:
        ratio = min(1.0, profile.experience_years / job.min_experience)
        parts["experience"] = round(WEIGHTS["experience"] * ratio)

    fits = profile.availability == Availability.ANY or profile.availability == job.employment_type
    parts["availability"] = WEIGHTS["availability"] if fits else 0

    parts["accommodation"] = WEIGHTS["accommodation"] if (not profile.needs_accommodation or job.housing) else 0

    return {"total": sum(parts.values()), "parts": parts}


def level(total):
    if total >= 75:
        return "high"
    if total >= 50:
        return "medium"
    return "low"


def breakdown_rows(parts):
    """Rows for templates: label, points, max, percent."""
    return [
        {"key": key, "label": LABELS[key], "points": parts.get(key, 0), "max": weight,
         "percent": round(100 * parts.get(key, 0) / weight)}
        for key, weight in WEIGHTS.items()
    ]


def weight_rows():
    return [{"key": k, "label": LABELS[k], "max": w, "percent": round(100 * w / 30)} for k, w in WEIGHTS.items()]
