from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import ai, local_matcher, scoring
from .forms import (
    ApplyForm, CandidateProfileForm, EmailAuthenticationForm, EmployerProfileForm, JobFilterForm, JobForm, PhotoForm,
    RegisterForm,
)
from .models import (
    Application, Availability, CandidateProfile, City, CvAnalysis, Department, EmployerProfile, Job, Language, User,
)

STATUS_ICONS = {
    "sent": "send", "reviewed": "search", "interview": "phone", "accepted": "check", "rejected": "x",
}


# ---------------------------------------------------------------- helpers
def employer_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_employer:
            messages.info(request, _("This page is only for employers."))
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def candidate_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_candidate:
            messages.info(request, _("This page is only for job seekers."))
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def get_candidate_profile(user):
    if not user.is_authenticated or not user.is_candidate:
        return None
    profile, _created = CandidateProfile.objects.get_or_create(user=user)
    return profile


def get_employer_profile(user):
    profile, _created = EmployerProfile.objects.get_or_create(
        user=user, defaults={"company_name": user.display_name, "city": City.GIRNE},
    )
    return profile


def safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


def status_tiles(queryset):
    counts = dict(queryset.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    return [
        {"key": key, "label": label, "count": counts.get(key, 0), "icon": STATUS_ICONS[key]}
        for key, label in Application.Status.choices
    ]


def attach_scores(jobs, profile):
    """Annotate job objects in-place with .match (dict) for a candidate."""
    for job in jobs:
        job.match = scoring.compute(profile, job) if profile else None
        if job.match:
            job.match["level"] = scoring.level(job.match["total"])
    return jobs


# ---------------------------------------------------------------- public
def landing(request):
    profile = get_candidate_profile(request.user)
    jobs = list(Job.objects.filter(is_active=True).select_related("employer__employer_profile")[:6])
    attach_scores(jobs, profile)
    jobs_data = [
        {
            "id": j.id,
            "title": j.title,
            "dept": j.department,
            "hotel": j.hotel_name,
            "logo": j.hotel_initials,
            "city": j.get_city_display(),
            "type": j.employment_type,
            "salary": f"£{j.salary:,}".replace(",", ".") if j.salary else None,
            "housing": j.housing,
            "meals": j.meals,
            "score": j.match["total"] if j.match else None,
            "url": reverse("job_detail", args=[j.id]),
        }
        for j in jobs
    ]
    return render(request, "landing.html", {"jobs_data": jobs_data})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    initial = {"role": request.GET.get("role")} if request.GET.get("role") in User.Role.values else {}
    form = RegisterForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if user.is_employer:
            messages.success(request, _("Welcome! Your employer account is ready. Publish your first job ad."))
            return redirect("dashboard")
        messages.success(request, _("Welcome! Complete your profile to see your match scores."))
        return redirect("profile")
    return render(request, "auth/register.html", {"form": form})


class PortalLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


# ---------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    if request.user.is_employer:
        return employer_dashboard(request)
    return candidate_dashboard(request)


def employer_dashboard(request):
    get_employer_profile(request.user)
    jobs = request.user.jobs.all()
    apps = Application.objects.filter(job__employer=request.user).select_related("job", "candidate__candidate_profile")
    week_ago = timezone.now() - timedelta(days=7)
    context = {
        "open_jobs": jobs.filter(is_active=True).count(),
        "total_jobs": jobs.count(),
        "total_apps": apps.count(),
        "apps_this_week": apps.filter(created_at__gte=week_ago).count(),
        "pending": apps.filter(status=Application.Status.SENT).count(),
        "status_tiles": status_tiles(apps),
        "top_pending": apps.filter(status=Application.Status.SENT).order_by("-score", "-created_at")[:5],
        "recent": apps[:6],
        "weights": scoring.weight_rows(),
        "page": "dashboard",
    }
    return render(request, "app/employer_dashboard.html", context)


def candidate_dashboard(request):
    profile = get_candidate_profile(request.user)
    apps = request.user.applications.select_related("job__employer__employer_profile")
    applied_ids = set(apps.values_list("job_id", flat=True))
    recommended = []
    if profile.department or profile.languages:
        candidates = list(Job.objects.filter(is_active=True).exclude(id__in=applied_ids)
                          .select_related("employer__employer_profile")[:60])
        attach_scores(candidates, profile)
        recommended = sorted(candidates, key=lambda j: j.match["total"], reverse=True)[:4]
    context = {
        "profile": profile,
        "total_apps": apps.count(),
        "interviews": apps.filter(status=Application.Status.INTERVIEW).count(),
        "accepted": apps.filter(status=Application.Status.ACCEPTED).count(),
        "status_tiles": status_tiles(apps),
        "recommended": recommended,
        "recent": apps[:6],
        "weights": scoring.weight_rows(),
        "page": "dashboard",
    }
    return render(request, "app/candidate_dashboard.html", context)


# ---------------------------------------------------------------- profile
@login_required
def profile(request):
    # Both roles: "confirm" the first time, then "view" with an "Add changes" button -> "edit" (Save / Cancel)
    if request.user.is_employer:
        return employer_profile(request)
    instance = get_candidate_profile(request.user)
    if not instance.confirmed_at:
        mode = "confirm"
    elif request.method == "POST" or request.GET.get("edit"):
        mode = "edit"
    else:
        mode = "view"

    form = None
    if mode != "view":
        form = CandidateProfileForm(request.POST or None, request.FILES or None, instance=instance, user=request.user)
        if request.method == "POST":
            if form.is_valid():
                saved = form.save()
                if mode == "confirm":
                    saved.confirmed_at = timezone.now()
                    saved.save(update_fields=["confirmed_at"])
                    messages.success(request, _("Your profile is confirmed. Here are the job ads that fit you best."))
                    return redirect(reverse("market") + "?sort=match")
                messages.success(request, _("Your profile has been saved."))
                return redirect("profile")
            messages.error(request, _("Please check the highlighted fields."))

    return render(request, "app/profile_candidate.html", {
        "form": form, "profile": instance, "page": "profile", "mode": mode, "photo_form": PhotoForm(),
        "completeness_hint": _("You can apply to jobs") if instance.is_ready_to_apply
        else _("Missing:") + " " + ", ".join(str(m) for m in instance.missing_fields()),
    })


def employer_profile(request):
    instance = get_employer_profile(request.user)
    if not instance.confirmed_at:
        mode = "confirm"
    elif request.method == "POST" or request.GET.get("edit"):
        mode = "edit"
    else:
        mode = "view"

    form = None
    if mode != "view":
        form = EmployerProfileForm(request.POST or None, instance=instance, user=request.user)
        if request.method == "POST":
            if form.is_valid():
                saved = form.save()
                if mode == "confirm":
                    saved.confirmed_at = timezone.now()
                    saved.save(update_fields=["confirmed_at"])
                    messages.success(request, _("Your company profile is confirmed. Publish and manage your job ads here."))
                    return redirect("my_jobs")
                messages.success(request, _("Your profile has been saved."))
                return redirect("profile")
            messages.error(request, _("Please check the highlighted fields."))
    return render(request, "app/profile_employer.html", {"form": form, "profile": instance, "page": "profile", "mode": mode})


@login_required
@require_POST
def photo_upload(request):
    form = PhotoForm(request.POST, request.FILES)
    if form.is_valid():
        user = request.user
        old = user.photo.name if user.photo else ""
        user.photo = form.cleaned_data["photo"]
        user.save(update_fields=["photo"])
        if old:
            user.photo.storage.delete(old)
        messages.success(request, _("Your photo has been updated."))
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(safe_next(request, reverse("profile")))


@login_required
@require_POST
def photo_delete(request):
    if request.user.photo:
        request.user.photo.delete(save=False)
        request.user.photo = ""
        request.user.save(update_fields=["photo"])
        messages.success(request, _("Your photo has been deleted."))
    return redirect(safe_next(request, reverse("profile")))


PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@login_required
def user_photo(request, pk):
    """Profile photos are visible to the owner and to employers the person applied to."""
    owner = get_object_or_404(User, pk=pk)
    allowed = (
        request.user == owner or request.user.is_staff
        or (request.user.is_employer and Application.objects.filter(candidate=owner, job__employer=request.user).exists())
        or owner.is_employer  # hotel photos/logos are public to logged-in users
    )
    if not allowed:
        return HttpResponseForbidden()
    if not owner.photo:
        raise Http404
    ext = "." + owner.photo.name.rsplit(".", 1)[-1].lower()
    response = FileResponse(owner.photo.open("rb"), content_type=PHOTO_TYPES.get(ext, "application/octet-stream"))
    response["Cache-Control"] = "private, max-age=86400"
    return response


@candidate_required
def my_cv(request):
    profile = get_candidate_profile(request.user)
    if not profile.cv:
        raise Http404
    return FileResponse(profile.cv.open("rb"), filename=profile.cv_filename)


# ---------------------------------------------------------------- applications
@login_required
def applications(request):
    status = request.GET.get("status", "")
    if status not in Application.Status.values:
        status = ""

    if request.user.is_employer:
        base = Application.objects.filter(job__employer=request.user).select_related("job", "candidate__candidate_profile")
        job_id = request.GET.get("job", "")
        if job_id.isdigit():
            base = base.filter(job_id=int(job_id))
        tiles = status_tiles(base)
        qs = base.filter(status=status) if status else base
        if request.GET.get("sort") == "score":
            qs = qs.order_by("-score", "-created_at")
        page = Paginator(qs, 15).get_page(request.GET.get("page"))
        context = {"page_obj": page, "status": status, "tiles": tiles, "jobs": request.user.jobs.all(),
                   "job_id": job_id, "statuses": Application.Status.choices, "page": "applications"}
        return render(request, "app/applications_employer.html", context)

    base = request.user.applications.select_related("job__employer__employer_profile")
    tiles = status_tiles(base)
    qs = base.filter(status=status) if status else base
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    unseen_ids = [a.id for a in page if not a.candidate_seen]
    if unseen_ids:
        Application.objects.filter(id__in=unseen_ids).update(candidate_seen=True)
    context = {"page_obj": page, "status": status, "tiles": tiles, "unseen_ids": unseen_ids, "page": "applications"}
    return render(request, "app/applications_candidate.html", context)


@employer_required
@require_POST
def application_status(request, pk):
    app = get_object_or_404(Application, pk=pk, job__employer=request.user)
    new_status = request.POST.get("status")
    if new_status in Application.Status.values and new_status != app.status:
        app.status = new_status
        app.candidate_seen = False
        app.save(update_fields=["status", "candidate_seen", "updated_at"])
        messages.success(request, _("Status updated: %(name)s → %(status)s") % {
            "name": app.candidate.display_name, "status": app.get_status_display()})
    return redirect(safe_next(request, reverse("applications")))


@candidate_required
@require_POST
def application_withdraw(request, pk):
    app = get_object_or_404(Application, pk=pk, candidate=request.user)
    if app.status != Application.Status.SENT:
        messages.error(request, _("This application has already been processed and cannot be withdrawn."))
    else:
        app.delete()
        messages.success(request, _("Your application was withdrawn."))
    return redirect("applications")


@login_required
def application_cv(request, pk):
    app = get_object_or_404(Application.objects.select_related("candidate__candidate_profile", "job"), pk=pk)
    if request.user != app.job.employer and request.user != app.candidate:
        return HttpResponseForbidden()
    profile = getattr(app.candidate, "candidate_profile", None)
    if not profile or not profile.cv:
        raise Http404
    return FileResponse(profile.cv.open("rb"), filename=profile.cv_filename)


# ---------------------------------------------------------------- employer job ads
@employer_required
def my_jobs(request):
    jobs = request.user.jobs.annotate(
        app_count=Count("applications"),
        pending_count=Count("applications", filter=Q(applications__status=Application.Status.SENT)),
    )
    return render(request, "app/my_jobs.html", {"jobs": jobs, "page": "my_jobs"})


@employer_required
def job_create(request):
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = request.user
        job.save()
        messages.success(request, _("Job ad published."))
        return redirect("my_jobs")
    return render(request, "app/job_form.html", {"form": form, "page": "my_jobs", "is_new": True})


@employer_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk, employer=request.user)
    form = JobForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Job ad updated."))
        return redirect("my_jobs")
    return render(request, "app/job_form.html", {"form": form, "job": job, "page": "my_jobs", "is_new": False})


@employer_required
@require_POST
def job_toggle(request, pk):
    job = get_object_or_404(Job, pk=pk, employer=request.user)
    job.is_active = not job.is_active
    job.save(update_fields=["is_active"])
    messages.success(request, _("Job ad published.") if job.is_active else _("Job ad paused."))
    return redirect("my_jobs")


@employer_required
@require_POST
def job_delete(request, pk):
    job = get_object_or_404(Job, pk=pk, employer=request.user)
    job.delete()
    messages.success(request, _("Job ad deleted."))
    return redirect("my_jobs")


# ---------------------------------------------------------------- market
@login_required
def market(request):
    form = JobFilterForm(request.GET or None)
    jobs = Job.objects.filter(is_active=True).select_related("employer__employer_profile")
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            jobs = jobs.filter(Q(title__icontains=d["q"]) | Q(employer__employer_profile__company_name__icontains=d["q"])
                               | Q(description__icontains=d["q"]))
        if d["department"]:
            jobs = jobs.filter(department=d["department"])
        if d["city"]:
            jobs = jobs.filter(city=d["city"])
        if d["type"]:
            jobs = jobs.filter(employment_type=d["type"])
        if d["housing"]:
            jobs = jobs.filter(housing=True)

    profile = get_candidate_profile(request.user)
    job_list = list(jobs[:300])
    attach_scores(job_list, profile)
    if profile and request.GET.get("sort") == "match":
        job_list.sort(key=lambda j: j.match["total"], reverse=True)
    applied = set(request.user.applications.values_list("job_id", flat=True)) if profile else set()
    page = Paginator(job_list, 12).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "app/market.html", {
        "form": form, "page_obj": page, "applied": applied, "query": query.urlencode(), "page": "market",
        "total": len(job_list),
    })


@login_required
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related("employer__employer_profile"), pk=pk)
    is_owner = job.employer_id == request.user.id
    if not job.is_active and not is_owner:
        raise Http404
    profile = get_candidate_profile(request.user)
    context = {"job": job, "is_owner": is_owner, "page": "market"}
    if profile:
        match = scoring.compute(profile, job)
        context.update({
            "match": match, "level": scoring.level(match["total"]), "rows": scoring.breakdown_rows(match["parts"]),
            "application": job.applications.filter(candidate=request.user).first(),
            "profile": profile, "apply_form": ApplyForm(),
        })
    if is_owner:
        context["app_count"] = job.applications.count()
    return render(request, "app/job_detail.html", context)


@candidate_required
@require_POST
def job_apply(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    profile = get_candidate_profile(request.user)
    if not profile.is_ready_to_apply:
        missing = ", ".join(str(m) for m in profile.missing_fields())
        messages.warning(request, _("Complete your profile before applying. Missing: %(fields)s") % {"fields": missing})
        return redirect("profile")
    form = ApplyForm(request.POST)
    if form.is_valid():
        match = scoring.compute(profile, job)
        try:
            Application.objects.create(job=job, candidate=request.user, note=form.cleaned_data["note"],
                                       score=match["total"], score_breakdown=match["parts"])
            messages.success(request, _("Your application has been sent to %(hotel)s.") % {"hotel": job.hotel_name})
        except IntegrityError:
            messages.info(request, _("You have already applied for this position."))
    return redirect("job_detail", pk=job.pk)


# ---------------------------------------------------------------- AI CV matching
AI_COOLDOWN = timedelta(seconds=30)
AI_DAILY_LIMIT = 20


def _ai_suggestions(profile, facts):
    """Rows comparing what the AI found in the CV with the current profile."""
    lang_labels = dict(Language.choices)
    dept_labels = dict(Department.choices)
    avail_labels = dict(Availability.choices)
    rows = []
    if facts.get("department") in dept_labels:
        rows.append({"key": "department", "label": _("Department"), "value": dept_labels[facts["department"]],
                     "same": facts["department"] == profile.department})
    if facts.get("languages"):
        merged = sorted(set(profile.languages) | set(facts["languages"]))
        rows.append({"key": "languages", "label": _("Languages"),
                     "value": ", ".join(str(lang_labels.get(c, c)) for c in facts["languages"]),
                     "same": set(merged) == set(profile.languages)})
    rows.append({"key": "experience", "label": _("Experience"), "value": facts.get("experience_years", 0),
                 "same": facts.get("experience_years", 0) == profile.experience_years})
    if facts.get("availability") in avail_labels:
        rows.append({"key": "availability", "label": _("Availability"), "value": avail_labels[facts["availability"]],
                     "same": facts["availability"] == profile.availability})
    if facts.get("suggested_bio"):
        rows.append({"key": "bio", "label": _("Short introduction"), "value": facts["suggested_bio"],
                     "same": facts["suggested_bio"] == profile.bio})
    return rows


@candidate_required
def ai_match(request):
    profile = get_candidate_profile(request.user)
    analysis = request.user.cv_analyses.first()
    matches, suggestions = [], []
    if analysis:
        data = analysis.result
        jobs = {j.id: j for j in Job.objects.filter(id__in=[m["job_id"] for m in data.get("matches", [])])
                .select_related("employer__employer_profile")}
        for m in data.get("matches", []):
            job = jobs.get(m["job_id"])
            if job and job.is_active:
                platform = scoring.compute(profile, job)["total"]
                matches.append({**m, "job": job, "platform_score": platform, "level": scoring.level(m["fit_score"])})
        matches.sort(key=lambda m: m["fit_score"], reverse=True)
        suggestions = _ai_suggestions(profile, data.get("candidate", {}))
    applied = set(request.user.applications.values_list("job_id", flat=True))
    return render(request, "app/ai_match.html", {
        "profile": profile, "analysis": analysis, "matches": matches, "suggestions": suggestions,
        "applied": applied, "claude": ai.is_configured(), "page": "ai_match",
        "stale": bool(analysis and profile.cv and analysis.cv_name != profile.cv_filename),
    })


@candidate_required
@require_POST
def ai_match_run(request):
    """Run the CV analysis: Claude when ANTHROPIC_API_KEY is set, otherwise the free local matcher."""
    profile = get_candidate_profile(request.user)

    if not ai.is_configured():
        try:
            match_result = local_matcher.analyse_cv(profile)
        except local_matcher.CvReadError as exc:
            messages.error(request, exc.user_message)
            return redirect("ai_match")
        CvAnalysis.objects.create(
            candidate=request.user, cv_name=profile.cv_filename, language=get_language()[:8],
            model=local_matcher.ENGINE_NAME, result=match_result.model_dump(),
        )
        return _analysis_message(request, match_result)

    now = timezone.now()
    recent = request.user.cv_analyses.filter(created_at__gte=now - timedelta(days=1)).exclude(model=local_matcher.ENGINE_NAME)
    last = recent.first()
    if last and now - last.created_at < AI_COOLDOWN:
        messages.info(request, _("Please wait a few seconds before running a new analysis."))
        return redirect("ai_match")
    if recent.count() >= AI_DAILY_LIMIT:
        messages.warning(request, _("You have reached today's limit of AI analyses. Try again tomorrow."))
        return redirect("ai_match")
    try:
        result = ai.analyse_cv(profile, get_language())
    except ai.AIError as exc:
        messages.error(request, exc.user_message)
        return redirect("ai_match")
    CvAnalysis.objects.create(
        candidate=request.user, cv_name=profile.cv_filename, language=get_language()[:8], model=result.model,
        result=result.result.model_dump(), input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens, request_id=result.request_id[:64],
    )
    return _analysis_message(request, result.result)


def _analysis_message(request, result):
    if not result.is_cv:
        messages.warning(request, _("This file does not look like a CV. Please upload your CV on your profile."))
    elif result.matches:
        messages.success(request, _("Done! We found jobs that match your CV."))
    else:
        messages.info(request, _("Your CV was analysed, but no open job ad fits it well right now."))
    return redirect("ai_match")


@candidate_required
@require_POST
def ai_apply_profile(request, pk):
    analysis = get_object_or_404(CvAnalysis, pk=pk, candidate=request.user)
    facts = analysis.result.get("candidate", {})
    profile = get_candidate_profile(request.user)
    chosen = set(request.POST.getlist("fields"))
    changed = []
    if "department" in chosen and facts.get("department") in Department.values:
        profile.department = facts["department"]; changed.append("department")
    if "languages" in chosen and facts.get("languages"):
        profile.languages = sorted(set(profile.languages) | {c for c in facts["languages"] if c in Language.values})
        changed.append("languages")
    if "experience" in chosen:
        profile.experience_years = max(0, min(50, int(facts.get("experience_years") or 0))); changed.append("experience_years")
    if "availability" in chosen and facts.get("availability") in Availability.values:
        profile.availability = facts["availability"]; changed.append("availability")
    if "bio" in chosen and facts.get("suggested_bio"):
        profile.bio = facts["suggested_bio"][:500]; changed.append("bio")
    if changed:
        profile.save()
        messages.success(request, _("Your profile was updated with the information from your CV."))
    else:
        messages.info(request, _("Nothing was selected."))
    return redirect("ai_match")
