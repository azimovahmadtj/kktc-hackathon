"""
Free "smart matching" without any AI service.

1. Extracts text from the CV (PDF with pypdf, DOCX with the standard library).
2. Finds facts with keyword dictionaries in Turkish, English and Russian:
   department, spoken languages, years of experience, availability, skills.
3. Scores every open job ad with the platform formula (portal/scoring.py),
   plus a small bonus when the job title appears in the CV.
4. Writes reasons and gaps in the current interface language.

Returns the same MatchResult structure as the Claude engine (portal/ai.py),
so the page and the database work the same for both engines.
"""
import io
import logging
import re
from datetime import date
from types import SimpleNamespace

from django.utils.translation import gettext as _

from . import scoring
from .models import Availability, Department, EmploymentType, Job, Language

logger = logging.getLogger(__name__)

ENGINE_NAME = "local"
MAX_MATCHES = 5
MIN_FIT = 40
TITLE_BONUS = 5
DEPARTMENT_MISMATCH_FACTOR = 0.6


class CvReadError(Exception):
    """Text could not be read from the CV; .user_message is shown to the user."""

    def __init__(self, user_message):
        super().__init__(str(user_message))
        self.user_message = user_message


# ---------------------------------------------------------------- normalisation
_TR_MAP = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u", "â": "a", "î": "i", "û": "u",
                         "ё": "е", "̇": None})


def norm(text):
    """Lower-case, fold Turkish letters to ASCII, collapse spaces. Cyrillic stays Cyrillic."""
    text = text.replace("İ", "i").replace("I", "i")
    return re.sub(r"[ \t ]+", " ", text.casefold().translate(_TR_MAP))


def _pattern(keyword):
    """'word' = whole word, 'stem*' = word starting with stem (for TR/RU suffixes)."""
    stem = keyword.endswith("*")
    kw = norm(keyword.rstrip("*"))
    body = re.escape(kw).replace(r"\ ", r"[\s\-]*")
    return re.compile(r"(?<!\w)" + body + (r"" if stem else r"(?!\w)"))


def _compile(table):
    return {key: [_pattern(k) for k in words] for key, words in table.items()}


# ---------------------------------------------------------------- dictionaries
DEPARTMENT_WORDS = _compile({
    "front_office": [
        "reception*", "front office", "front desk", "guest relation*", "concierge", "night audit*", "bellboy",
        "resepsiyon*", "on buro", "misafir iliskileri", "konsiyerj", "gece muhasebe*",
        "ресепшн*", "ресепшен*", "администратор*", "портье", "консьерж*", "front-office",
    ],
    "food_beverage": [
        "waiter*", "waitress*", "bartender*", "barista*", "sommelier*", "restaurant*", "f&b", "food and beverage",
        "garson*", "barmen*", "restoran*", "servis eleman*", "komi", "sef de rang",
        "официант*", "бармен*", "бариста", "ресторан*", "сомелье", "хостес",
    ],
    "kitchen": [
        "chef*", "cook*", "kitchen*", "pastry*", "commis", "sous chef", "line cook",
        "asci*", "mutfak*", "pasta*", "sef*", "kasap*",
        "повар*", "шеф*", "кухн*", "кондитер*", "су-шеф",
    ],
    "housekeeping": [
        "housekeep*", "room attendant*", "laundry", "cleaning",
        "kat gorevli*", "kat hizmet*", "camasirhane*", "temizlik*", "oda hizmet*",
        "горничн*", "хаускипинг*", "уборк*", "прачечн*",
    ],
    "entertainment": [
        "animator*", "animation*", "entertainment*", "mini club", "kids club", "dancer*", "show*", "dj",
        "animasyon*", "animator*", "dansci*", "sahne*",
        "аниматор*", "анимаци*", "танцор*", "шоу", "детск* клуб*", "мини-клуб*",
    ],
    "spa": [
        "spa", "massage*", "therapist*", "wellness", "beauty", "sauna", "hammam",
        "masaj*", "terapist*", "guzellik*", "hamam*",
        "массаж*", "спа", "косметолог*", "велнес*", "терапевт*",
    ],
    "technical": [
        "technician*", "maintenance", "electrician*", "plumb*", "hvac", "engineer*", "repair*",
        "teknisyen*", "teknik servis*", "bakim*", "elektrikci*", "tesisat*", "klima*", "muhendis*",
        "техник*", "электрик*", "сантехник*", "инженер*", "ремонт*", "обслуживани*",
    ],
})

LANGUAGE_WORDS = _compile({
    "tr": ["turkish", "turkce", "turk dili", "турецк*"],
    "en": ["english", "ingilizce", "английск*"],
    "ru": ["russian", "rusca", "русск*"],
    "de": ["german", "deutsch", "almanca", "немецк*"],
    "ar": ["arabic", "arapca", "арабск*"],
    "el": ["greek", "yunanca", "греческ*"],
})

AVAILABILITY_WORDS = _compile({
    "seasonal": ["seasonal", "season", "sezonluk", "sezon*", "сезон*"],
    "full_time": ["full time", "fulltime", "tam zamanli", "tam gun", "полный день", "полная занятость", "полн* рабоч* ден*"],
    "part_time": ["part time", "parttime", "yari zamanli", "частичн* занятост*", "неполный день"],
})

SKILLS = {
    "Opera PMS": ["opera", "opera pms"],
    "Fidelio": ["fidelio"],
    "Protel": ["protel"],
    "Micros POS": ["micros"],
    "POS": ["pos"],
    "MS Excel": ["excel"],
    "HACCP": ["haccp"],
    "First aid": ["first aid", "ilk yardim", "первая помощь", "первой помощи"],
    "Barista": ["barista*", "latte art"],
    "Cocktails": ["cocktail*", "kokteyl*", "коктейл*"],
    "Customer service": ["customer service", "musteri hizmet*", "musteri iliskileri", "обслуживани* гост*", "клиентск* сервис*"],
    "Cash register": ["cashier", "kasa*", "касс*"],
    "Driving licence": ["driving licen*", "driver's licen*", "ehliyet*", "водительск*"],
    "Lifeguard": ["lifeguard", "cankurtaran*", "спасател*"],
    "Fine dining": ["fine dining", "a la carte", "ala carte"],
    "Hotel software": ["elektra", "sedna", "hotelrunner"],
}
SKILL_PATTERNS = {name: [_pattern(k) for k in words] for name, words in SKILLS.items()}

EDUCATION_LINE = re.compile(
    r"(univers|universite|college|school|lise|okul|egitim|education|faculty|fakulte|"
    r"университет|колледж|училищ|школ|образовани|институт|академи)")
AGE_LINE = re.compile(r"(\bage\b|years old|yasinda|\byas\b|dogum|born|возраст|дата рождения|родил)")
YEARS_EXPLICIT = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|yil|yillik|года|год|лет)(?!\w)")
PRESENT = r"(?:present|current|now|today|halen|hala|gunumuz|devam\w*|настоящ\w*|сейчас|н\.?\s?в\.?|по сей)"
YEAR = r"(?:\d{1,2}[./])?((?:19|20)\d{2})"
DATE_RANGE = re.compile(YEAR + r"\s*(?:[-–—]|to|until|по|до)\s*(?:" + YEAR + r"|(" + PRESENT + r"))")


def _hits(patterns, text):
    return sum(len(p.findall(text)) for p in patterns)


# ---------------------------------------------------------------- text extraction
def extract_text(profile):
    from .ai import docx_text, AIError  # same DOCX reader as the Claude engine

    if not profile.cv:
        raise CvReadError(_("Upload your CV on your profile first."))
    name = profile.cv.name.lower()
    with profile.cv.open("rb") as fh:
        data = fh.read()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            logging.getLogger("pypdf").setLevel(logging.ERROR)
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
        except Exception as exc:  # broken or encrypted PDF
            logger.warning("Could not read PDF %s: %s", profile.cv.name, exc)
            raise CvReadError(_("The CV file could not be read. Please upload it again as PDF or DOCX."))
    elif name.endswith(".docx"):
        try:
            text = docx_text(data)
        except AIError as exc:
            raise CvReadError(exc.user_message)
    else:
        raise CvReadError(_("AI analysis supports PDF and DOCX files. Please upload your CV in one of these formats."))
    if len(text.strip()) < 30:
        raise CvReadError(_("No text was found in your CV. If it is a scanned image, upload a text PDF or DOCX."))
    return text


# ---------------------------------------------------------------- fact extraction
def experience_years(text_norm):
    explicit = 0
    intervals = []
    this_year = date.today().year
    for line in text_norm.splitlines():
        if AGE_LINE.search(line):
            continue
        for m in YEARS_EXPLICIT.finditer(line):
            value = int(m.group(1))
            if value <= 40 and not line[m.end():m.end() + 4].strip().startswith("old"):
                explicit = max(explicit, value)
        if EDUCATION_LINE.search(line):
            continue
        for m in DATE_RANGE.finditer(line):
            start = int(m.group(1))
            end = this_year if m.group(3) else int(m.group(2))
            if 1970 <= start <= end <= this_year:
                intervals.append((start, max(end, start + 0.5)))
    total = 0.0
    for start, end in sorted(intervals):
        if total and start < merged_end:
            if end > merged_end:
                total += end - merged_end
                merged_end = end
        else:
            total += end - start
            merged_end = end
    return min(40, max(explicit, round(total)))


def detect_languages(text_raw, text_norm):
    found = [code for code, pats in LANGUAGE_WORDS.items() if _hits(pats, text_norm)]
    letters = [ch for ch in text_raw if ch.isalpha()]
    if letters:
        cyr = sum("а" <= ch.lower() <= "я" or ch in "ёЁ" for ch in letters) / len(letters)
        if cyr > 0.3 and "ru" not in found:
            found.append("ru")
    if sum(text_raw.count(ch) for ch in "şğıŞĞİ") >= 5 and "tr" not in found:
        found.append("tr")
    if len(re.findall(r"(?<!\w)(?:the|and|with|experience|responsible)(?!\w)", text_norm)) >= 5 and "en" not in found:
        found.append("en")
    order = list(Language.values)
    return sorted(found, key=order.index)


def extract_facts(text_raw):
    text_norm = norm(text_raw)
    dept_scores = {d: _hits(p, text_norm) for d, p in DEPARTMENT_WORDS.items()}
    best = max(dept_scores, key=dept_scores.get)
    department = best if dept_scores[best] else "unknown"

    avail_scores = {a: _hits(p, text_norm) for a, p in AVAILABILITY_WORDS.items()}
    top = max(avail_scores, key=avail_scores.get)
    availability = top if avail_scores[top] else Availability.ANY

    skills = [name for name, pats in SKILL_PATTERNS.items() if _hits(pats, text_norm)]
    return {
        "text_norm": text_norm,
        "department": department,
        "department_hits": dept_scores,
        "languages": detect_languages(text_raw, text_norm),
        "experience_years": experience_years(text_norm),
        "availability": availability,
        "skills": skills,
    }


# ---------------------------------------------------------------- matching
def _labels(codes):
    labels = dict(Language.choices)
    return ", ".join(str(labels.get(c, c)) for c in codes)


TITLE_STOPWORDS = {"eleman", "elemani", "staff", "personel", "assistant", "yardimci", "senior", "junior", "sorumlu"}


def _title_word_in_cv(job, text_norm):
    """True when a meaningful word of the job title appears in the CV (suffixes allowed: garson -> garsonluk)."""
    for word in re.findall(r"\w{5,}", norm(job.title)):
        if word not in TITLE_STOPWORDS and re.search(r"(?<!\w)" + re.escape(word), text_norm):
            return job.title
    return ""


def match_job(facts, needs_accommodation, job):
    candidate = SimpleNamespace(
        department=facts["department"] if facts["department"] != "unknown" else "",
        languages=facts["languages"], experience_years=facts["experience_years"],
        availability=facts["availability"], needs_accommodation=needs_accommodation,
    )
    result = scoring.compute(candidate, job)
    parts = result["parts"]
    reasons, gaps = [], []
    dept_label = str(Department(job.department).label)
    type_label = str(EmploymentType(job.employment_type).label)

    title_hit = _title_word_in_cv(job, facts["text_norm"])
    bonus = TITLE_BONUS if title_hit else 0
    if title_hit:
        reasons.append(_("Your CV mentions \"%(title)s\"") % {"title": title_hit})

    if parts["department"]:
        reasons.append(_("Your experience is in %(dept)s") % {"dept": dept_label})
    else:
        gaps.append(_("This job is in a different department: %(dept)s") % {"dept": dept_label})

    required = list(job.required_languages or [])
    spoken = [c for c in required if c in facts["languages"]]
    missing = [c for c in required if c not in facts["languages"]]
    if spoken:
        reasons.append(_("You speak the required languages: %(langs)s") % {"langs": _labels(spoken)})
    if missing:
        gaps.append(_("Required language not found in your CV: %(langs)s") % {"langs": _labels(missing)})

    years = facts["experience_years"]
    if job.min_experience and years >= job.min_experience:
        reasons.append(_("%(years)s years of experience (required: %(req)s)") % {"years": years, "req": job.min_experience})
    elif job.min_experience:
        gaps.append(_("Requires %(req)s years of experience, your CV shows %(years)s") % {"years": years, "req": job.min_experience})
    else:
        reasons.append(_("No experience required"))

    if parts["availability"]:
        if facts["availability"] != Availability.ANY:
            reasons.append(_("Fits your availability: %(type)s") % {"type": type_label})
    else:
        gaps.append(_("This is a %(type)s position") % {"type": type_label.lower()})

    if needs_accommodation and job.housing:
        reasons.append(_("Accommodation is provided"))
    elif needs_accommodation and not job.housing:
        gaps.append(_("No accommodation provided"))

    total = result["total"]
    if facts["department"] != "unknown" and not parts["department"] and not title_hit:
        # A different department matters more for CV matching than the other criteria
        total = round(total * DEPARTMENT_MISMATCH_FACTOR)
    return min(100, total + bonus), reasons[:4], gaps[:3]


def summary_text(facts):
    dept = facts["department"]
    parts = []
    if dept in Department.values:
        parts.append(str(Department(dept).label))
    parts.append(_("%(years)s years of experience") % {"years": facts["experience_years"]})
    if facts["languages"]:
        parts.append(_("Languages: %(langs)s") % {"langs": _labels(facts["languages"])})
    return " · ".join(parts)


def bio_text(facts):
    dept = facts["department"]
    if dept in Department.values:
        text = _("I am a hospitality professional in %(dept)s with %(years)s years of experience.") % {
            "dept": str(Department(dept).label), "years": facts["experience_years"]}
    else:
        text = _("I am looking for a job in the hospitality industry in Northern Cyprus.")
    if facts["languages"]:
        text += " " + _("I speak %(langs)s.") % {"langs": _labels(facts["languages"])}
    if facts["skills"]:
        text += " " + _("Skills: %(skills)s.") % {"skills": ", ".join(facts["skills"][:5])}
    return text[:500]


def analyse_cv(profile):
    """Analyse the candidate's CV without any external service. Returns ai.MatchResult."""
    from .ai import CandidateFacts, JobMatch, MatchResult

    text = extract_text(profile)
    facts = extract_facts(text)
    found_something = facts["department"] != "unknown" or facts["languages"] or facts["experience_years"]
    is_cv = len(text) >= 80 and bool(found_something)

    matches = []
    if is_cv:
        jobs = Job.objects.filter(is_active=True).select_related("employer__employer_profile")
        scored = []
        for job in jobs:
            fit, reasons, gaps = match_job(facts, profile.needs_accommodation, job)
            if fit >= MIN_FIT:
                scored.append((fit, job.created_at, JobMatch(job_id=job.id, fit_score=fit, reasons=reasons, gaps=gaps)))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        matches = [s[2] for s in scored[:MAX_MATCHES]]

    return MatchResult(
        is_cv=is_cv,
        candidate=CandidateFacts(
            full_name=profile.user.get_full_name(),
            summary=summary_text(facts),
            experience_years=facts["experience_years"],
            department=facts["department"],
            languages=facts["languages"],
            availability=facts["availability"],
            skills=facts["skills"],
            suggested_bio=bio_text(facts) if is_cv else "",
        ),
        matches=matches,
    )
