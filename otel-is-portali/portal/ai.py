"""
AI CV matching with the Claude API.

Claude reads the candidate's CV (PDF natively, DOCX as extracted text) together with
the catalog of active job ads and returns structured JSON:

  * the profile facts it found in the CV (department, languages, experience, …)
  * up to 5 job ads from the catalog that fit best, each with a 0–100 fit score,
    concrete reasons and gaps, written in the user's interface language

Design notes
  * Structured outputs (`output_config.format`) guarantee schema-valid JSON; the result is
    validated again with Pydantic and every job id is checked against the database.
  * The system prompt + job catalog are a stable prefix marked with `cache_control`, so
    repeated analyses reuse the cached prefix; the CV and the output language come after it.
  * `fallbacks: "default"` re-runs a request on Anthropic's recommended fallback model
    if the primary model's safety classifiers decline it.
"""
import base64
import io
import json
import logging
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

import anthropic
from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel, ValidationError

from .models import Availability, Department, Job, Language

logger = logging.getLogger(__name__)

MAX_MATCHES = 5
MAX_CV_BYTES = 5 * 1024 * 1024
MAX_DOCX_CHARS = 150_000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept server-side `fallbacks: "default"` on the Claude API
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
OUTPUT_LANGUAGE = {"tr": "Turkish", "en": "English", "ru": "Russian"}

UNKNOWN = "unknown"


class AIError(Exception):
    """A problem the user should see as a friendly message."""

    def __init__(self, user_message, *, detail=""):
        super().__init__(detail or str(user_message))
        self.user_message = user_message


# ---------------------------------------------------------------- result schema
class CandidateFacts(BaseModel):
    full_name: str
    summary: str
    experience_years: int
    department: str
    languages: list[str]
    availability: str
    skills: list[str]
    suggested_bio: str


class JobMatch(BaseModel):
    job_id: int
    fit_score: int
    reasons: list[str]
    gaps: list[str]


class MatchResult(BaseModel):
    is_cv: bool
    candidate: CandidateFacts
    matches: list[JobMatch]


def _enum(values):
    return {"type": "string", "enum": list(values)}


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["is_cv", "candidate", "matches"],
    "properties": {
        "is_cv": {"type": "boolean", "description": "false if the document is not a CV / resume"},
        "candidate": {
            "type": "object",
            "additionalProperties": False,
            "required": ["full_name", "summary", "experience_years", "department", "languages",
                         "availability", "skills", "suggested_bio"],
            "properties": {
                "full_name": {"type": "string"},
                "summary": {"type": "string", "description": "2-3 sentences about the candidate"},
                "experience_years": {"type": "integer", "description": "total years of relevant work experience, 0 if none"},
                "department": _enum([*Department.values, UNKNOWN]),
                "languages": {"type": "array", "items": _enum(Language.values)},
                "availability": _enum(Availability.values),
                "skills": {"type": "array", "items": {"type": "string"}},
                "suggested_bio": {"type": "string", "description": "first-person profile introduction, max 500 characters"},
            },
        },
        "matches": {
            "type": "array",
            "description": f"best-fitting job ads, best first, at most {MAX_MATCHES}",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["job_id", "fit_score", "reasons", "gaps"],
                "properties": {
                    "job_id": {"type": "integer"},
                    "fit_score": {"type": "integer", "description": "0-100"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "gaps": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

SYSTEM_PROMPT = f"""You are the matching engine of Otel İş Portalı, a recruitment platform for hotels, resorts and restaurants in Northern Cyprus.

You receive one candidate's CV and the catalog of open job ads. Your output is shown directly to the candidate, so it must be accurate, specific and kind.

1. Extract the candidate's facts from the CV only. Do not invent anything; when the CV does not state something, use the neutral value (experience_years 0, department "{UNKNOWN}", availability "any", empty lists).
   - department: the hospitality department their experience and goals point to.
   - languages: only languages the CV says they speak.
   - suggested_bio: a first-person introduction they could put on their profile, at most 500 characters.
2. Choose up to {MAX_MATCHES} job ads from the catalog that genuinely fit, best first. Use only job ids that appear in the catalog. Return fewer, or none, when few fit; a short honest list is better than a padded one.
   - fit_score (0-100): how well the candidate fits the job's role, required languages, minimum experience, employment type and accommodation needs. 75+ means a strong fit, 50-74 a reasonable fit with gaps, below 50 a stretch.
   - reasons: 2-3 short points tied to concrete facts in the CV.
   - gaps: 0-2 short points about what is missing for that job, phrased as advice.
3. If the document is not a CV or resume, set is_cv to false and return no matches.

Write summary, skills, suggested_bio, reasons and gaps in the output language named in the user message. Keep job titles and hotel names as they are.

Field codes:
- department: {", ".join(f"{v} ({l})" for v, l in zip(Department.values, ["front office / reception", "food & beverage / waiter / bar", "kitchen / cook", "housekeeping", "entertainment / animation", "spa & wellness", "technical service / maintenance"]))}
- languages: tr Turkish, en English, ru Russian, de German, ar Arabic, el Greek
- availability: any, seasonal, full_time, part_time"""


# ---------------------------------------------------------------- inputs
def job_catalog(limit=None):
    """Active job ads as a deterministic text block (stable order keeps the prompt cacheable)."""
    limit = limit or settings.AI_MAX_JOBS_IN_PROMPT
    jobs = (Job.objects.filter(is_active=True).select_related("employer__employer_profile")
            .order_by("-created_at", "-id")[:limit])
    rows = []
    for j in sorted(jobs, key=lambda j: j.id):
        rows.append(json.dumps({
            "id": j.id,
            "title": j.title,
            "hotel": j.hotel_name,
            "city": j.get_city_display(),
            "department": j.department,
            "employment_type": j.employment_type,
            "salary_gbp_month": j.salary,
            "accommodation": j.housing,
            "meals": j.meals,
            "required_languages": sorted(j.required_languages or []),
            "min_experience_years": j.min_experience,
            "description": " ".join((j.description or "").split())[:600],
        }, ensure_ascii=False, sort_keys=True))
    return rows


def docx_text(data):
    """Plain text of a .docx file (paragraphs and table cells) using only the standard library."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise AIError(_("The CV file could not be read. Please upload it again as PDF or DOCX."), detail=str(exc))
    root = ElementTree.fromstring(xml)
    lines = []
    for para in root.iter(f"{ns}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{ns}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{ns}tab":
                parts.append("\t")
        text = "".join(parts).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def cv_content_block(profile):
    """The CV as a Claude content block (PDF document, or text for DOCX)."""
    if not profile.cv:
        raise AIError(_("Upload your CV on your profile first."))
    name = profile.cv.name.lower()
    with profile.cv.open("rb") as fh:
        data = fh.read(MAX_CV_BYTES + 1)
    if len(data) > MAX_CV_BYTES:
        raise AIError(_("The file can be at most 5 MB."))
    if name.endswith(".pdf"):
        return {"type": "document", "title": "CV",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": base64.standard_b64encode(data).decode("ascii")}}
    if name.endswith(".docx"):
        text = docx_text(data)
        if not text.strip():
            raise AIError(_("No text was found in your CV. Please upload it as PDF."))
        if len(text) > MAX_DOCX_CHARS:
            raise AIError(_("Your CV is too long to analyse. Please upload a shorter version."))
        return {"type": "text", "text": f"<cv>\n{text}\n</cv>"}
    raise AIError(_("AI analysis supports PDF and DOCX files. Please upload your CV in one of these formats."))


# ---------------------------------------------------------------- Claude call
def is_configured():
    return bool(settings.ANTHROPIC_API_KEY)


def get_client():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY,
                               timeout=settings.AI_TIMEOUT_SECONDS, max_retries=2)


@dataclass
class Analysis:
    result: MatchResult
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    request_id: str


def analyse_cv(profile, language_code=None):
    """Run the CV analysis. Raises AIError with a user-facing message on any failure."""
    if not is_configured():
        raise AIError(_("AI matching is not configured yet (missing ANTHROPIC_API_KEY)."))

    catalog = job_catalog()
    if not catalog:
        raise AIError(_("There are no open job ads to match yet."))

    cv_block = cv_content_block(profile)
    lang = OUTPUT_LANGUAGE.get((language_code or get_language() or "tr")[:2], "Turkish")
    model = settings.ANTHROPIC_MODEL

    request = dict(
        model=model,
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        system=[
            {"type": "text", "text": SYSTEM_PROMPT},
            # Stable prefix ends here: cache system prompt + catalog for the next analyses
            {"type": "text", "text": "<job_catalog>\n" + "\n".join(catalog) + "\n</job_catalog>",
             "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": [
            cv_block,
            {"type": "text", "text": f"Analyse this CV and match it to the catalog. Output language: {lang}."},
        ]}],
    )
    if model in FALLBACK_MODELS:
        request.update(betas=[FALLBACK_BETA], fallbacks="default")

    client = get_client()
    try:
        response = client.beta.messages.create(**request)
    except anthropic.AuthenticationError as exc:
        logger.error("Claude authentication failed: %s", exc)
        raise AIError(_("The AI service key is invalid. Please contact the site administrator."), detail=str(exc))
    except anthropic.PermissionDeniedError as exc:
        logger.error("Claude permission denied: %s", exc)
        raise AIError(_("The AI service key is invalid. Please contact the site administrator."), detail=str(exc))
    except anthropic.NotFoundError as exc:
        logger.error("Claude model not found (%s): %s", model, exc)
        raise AIError(_("The AI service is misconfigured. Please contact the site administrator."), detail=str(exc))
    except anthropic.BadRequestError as exc:
        logger.warning("Claude rejected the request: %s", exc)
        raise AIError(_("The AI could not process this CV. Try uploading it as a PDF."), detail=str(exc))
    except anthropic.RateLimitError as exc:
        logger.warning("Claude rate limited: %s", exc)
        raise AIError(_("The AI service is busy right now. Please try again in a minute."), detail=str(exc))
    except anthropic.APITimeoutError as exc:
        logger.warning("Claude request timed out: %s", exc)
        raise AIError(_("The AI analysis took too long. Please try again."), detail=str(exc))
    except anthropic.APIConnectionError as exc:
        logger.warning("Could not reach Claude: %s", exc)
        raise AIError(_("Could not connect to the AI service. Please try again later."), detail=str(exc))
    except anthropic.APIStatusError as exc:
        logger.error("Claude API error %s: %s", exc.status_code, exc)
        raise AIError(_("The AI service is temporarily unavailable. Please try again later."), detail=str(exc))

    request_id = getattr(response, "_request_id", "") or ""
    if response.stop_reason == "refusal":
        logger.warning("Claude declined the CV analysis (request %s): %s", request_id, response.stop_details)
        raise AIError(_("The AI could not analyse this document."))
    if response.stop_reason == "max_tokens":
        logger.warning("Claude output truncated (request %s)", request_id)
        raise AIError(_("The AI analysis was incomplete. Please try again."))

    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    try:
        result = MatchResult.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Unexpected Claude output (request %s): %s", request_id, exc)
        raise AIError(_("The AI analysis was incomplete. Please try again."), detail=str(exc))

    result = clean_result(result)
    usage = response.usage
    return Analysis(
        result=result,
        model=getattr(response, "model", model) or model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        request_id=request_id,
    )


def clean_result(result):
    """Clamp numbers, drop unknown/duplicate/inactive job ids, keep the best MAX_MATCHES."""
    c = result.candidate
    c.experience_years = max(0, min(50, c.experience_years))
    c.languages = [code for code in dict.fromkeys(c.languages) if code in Language.values]
    if c.department not in Department.values:
        c.department = UNKNOWN
    if c.availability not in Availability.values:
        c.availability = Availability.ANY
    c.suggested_bio = c.suggested_bio.strip()[:500]

    active = set(Job.objects.filter(is_active=True, id__in=[m.job_id for m in result.matches]).values_list("id", flat=True))
    seen, matches = set(), []
    for m in result.matches:
        if m.job_id in active and m.job_id not in seen:
            seen.add(m.job_id)
            m.fit_score = max(0, min(100, m.fit_score))
            m.reasons, m.gaps = m.reasons[:4], m.gaps[:3]
            matches.append(m)
    result.matches = matches[:MAX_MATCHES] if result.is_cv else []
    return result
