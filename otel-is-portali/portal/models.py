from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import FileExtensionValidator, MaxValueValidator
import os
import uuid

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------- choices
class Department(models.TextChoices):
    FRONT_OFFICE = "front_office", _("Front Office")
    FOOD_BEVERAGE = "food_beverage", _("Food & Beverage")
    KITCHEN = "kitchen", _("Kitchen")
    HOUSEKEEPING = "housekeeping", _("Housekeeping")
    ENTERTAINMENT = "entertainment", _("Entertainment")
    SPA = "spa", _("Spa & Wellness")
    TECHNICAL = "technical", _("Technical Service")


class Language(models.TextChoices):
    TURKISH = "tr", _("Turkish")
    ENGLISH = "en", _("English")
    RUSSIAN = "ru", _("Russian")
    GERMAN = "de", _("German")
    ARABIC = "ar", _("Arabic")
    GREEK = "el", _("Greek")


class EmploymentType(models.TextChoices):
    SEASONAL = "seasonal", _("Seasonal")
    FULL_TIME = "full_time", _("Full-time")
    PART_TIME = "part_time", _("Part-time")


class Availability(models.TextChoices):
    ANY = "any", _("Any type")
    SEASONAL = "seasonal", _("Seasonal")
    FULL_TIME = "full_time", _("Full-time")
    PART_TIME = "part_time", _("Part-time")


class City(models.TextChoices):
    GIRNE = "girne", "Girne"
    GAZIMAGUSA = "gazimagusa", "Gazimağusa"
    LEFKOSA = "lefkosa", "Lefkoşa"
    ISKELE = "iskele", "İskele"
    BAFRA = "bafra", "Bafra"
    GUZELYURT = "guzelyurt", "Güzelyurt"
    LEFKE = "lefke", "Lefke"


# ---------------------------------------------------------------- users
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.EMPLOYER)
        return self._create_user(email, password, **extra)


def photo_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"photos/{instance.pk}/{uuid.uuid4().hex}{ext}"


class User(AbstractUser):
    """Logs in with email. A user is either a job seeker or an employer (hotel)."""

    class Role(models.TextChoices):
        CANDIDATE = "candidate", _("Job seeker")
        EMPLOYER = "employer", _("Employer")

    username = None
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(_("account type"), max_length=20, choices=Role.choices, default=Role.CANDIDATE)
    photo = models.FileField(_("profile photo"), upload_to=photo_upload_to, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    @property
    def is_employer(self):
        return self.role == self.Role.EMPLOYER

    @property
    def is_candidate(self):
        return self.role == self.Role.CANDIDATE

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts).upper()[:2]
        return (self.email[:2] if self.email else "?").upper()

    @property
    def photo_url(self):
        """URL of the photo (served by a permission-checked view); changes when the photo changes."""
        if not self.photo:
            return ""
        return reverse("user_photo", args=[self.pk]) + "?v=" + os.path.basename(self.photo.name)[:12]

    @property
    def display_name(self):
        return self.get_full_name() or self.email

    def __str__(self):
        return self.display_name


def cv_upload_to(instance, filename):
    return f"cvs/{instance.user_id}/{filename}"


class CandidateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="candidate_profile")
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    experience_years = models.PositiveSmallIntegerField(_("experience (years)"), default=0, validators=[MaxValueValidator(50)])
    department = models.CharField(_("preferred department"), max_length=30, choices=Department.choices, blank=True)
    availability = models.CharField(_("work availability"), max_length=20, choices=Availability.choices, default=Availability.ANY)
    needs_accommodation = models.BooleanField(_("needs accommodation"), default=False)
    languages = models.JSONField(_("languages"), default=list, blank=True)
    bio = models.TextField(_("short introduction"), max_length=500, blank=True)
    cv = models.FileField(
        _("CV"), upload_to=cv_upload_to, blank=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx"])],
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)  # set when the candidate presses "Confirm"
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("candidate profile")
        verbose_name_plural = _("candidate profiles")

    def __str__(self):
        return str(self.user)

    # Fields needed before the candidate can apply
    def missing_fields(self):
        missing = []
        if not self.phone:
            missing.append(_("Phone"))
        if not self.department:
            missing.append(_("Department"))
        if not self.languages:
            missing.append(_("Languages"))
        if not self.cv:
            missing.append(_("CV"))
        return missing

    @property
    def is_ready_to_apply(self):
        return not self.missing_fields()

    @property
    def completeness(self):
        checks = [
            self.user.first_name, self.user.last_name, self.phone, self.department, self.languages,
            self.experience_years > 0, len(self.bio) >= 20, self.cv,
        ]
        return round(100 * sum(bool(c) for c in checks) / len(checks))

    def language_labels(self):
        labels = dict(Language.choices)
        return [labels.get(code, code) for code in self.languages]

    @property
    def cv_filename(self):
        return self.cv.name.rsplit("/", 1)[-1] if self.cv else ""


class EmployerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer_profile")
    company_name = models.CharField(_("hotel / company name"), max_length=120)
    city = models.CharField(_("city"), max_length=20, choices=City.choices, default=City.GIRNE)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    website = models.URLField(_("website"), blank=True)
    description = models.TextField(_("about the business"), max_length=1000, blank=True)
    is_verified = models.BooleanField(_("verified"), default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # set when the employer presses "Confirm"

    class Meta:
        verbose_name = _("employer profile")
        verbose_name_plural = _("employer profiles")

    def __str__(self):
        return self.company_name


# ---------------------------------------------------------------- jobs
class Job(models.Model):
    employer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(_("position"), max_length=120)
    department = models.CharField(_("department"), max_length=30, choices=Department.choices)
    city = models.CharField(_("city"), max_length=20, choices=City.choices)
    employment_type = models.CharField(_("employment type"), max_length=20, choices=EmploymentType.choices)
    salary = models.PositiveIntegerField(_("monthly salary (GBP)"), null=True, blank=True)
    housing = models.BooleanField(_("accommodation provided"), default=False)
    meals = models.BooleanField(_("meals provided"), default=False)
    required_languages = models.JSONField(_("required languages"), default=list, blank=True)
    min_experience = models.PositiveSmallIntegerField(_("minimum experience (years)"), default=0, validators=[MaxValueValidator(50)])
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("published"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("job ad")
        verbose_name_plural = _("job ads")

    def __str__(self):
        return f"{self.title} · {self.hotel_name}"

    @property
    def hotel_name(self):
        profile = getattr(self.employer, "employer_profile", None)
        return profile.company_name if profile else self.employer.display_name

    @property
    def hotel_initials(self):
        words = [w for w in self.hotel_name.replace("'", " ").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "H"

    def required_language_labels(self):
        labels = dict(Language.choices)
        return [labels.get(code, code) for code in self.required_languages]


class Application(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", _("Sent")
        REVIEWED = "reviewed", _("Reviewed")
        INTERVIEW = "interview", _("Interview")
        ACCEPTED = "accepted", _("Accepted")
        REJECTED = "rejected", _("Rejected")

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.SENT)
    score = models.PositiveSmallIntegerField(_("match score"), default=0)
    score_breakdown = models.JSONField(default=dict, blank=True)
    note = models.TextField(_("note to employer"), max_length=1000, blank=True)
    candidate_seen = models.BooleanField(default=True)  # False after the employer changes the status
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["job", "candidate"], name="unique_application_per_job")]
        verbose_name = _("application")
        verbose_name_plural = _("applications")

    def __str__(self):
        return f"{self.candidate} → {self.job}"


class CvAnalysis(models.Model):
    """Result of an AI CV analysis (see portal/ai.py)."""

    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cv_analyses")
    cv_name = models.CharField(max_length=255)
    language = models.CharField(max_length=8)
    model = models.CharField(max_length=64)
    result = models.JSONField()
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_tokens = models.PositiveIntegerField(default=0)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("CV analysis")
        verbose_name_plural = _("CV analyses")

    def __str__(self):
        return f"{self.candidate} · {self.created_at:%Y-%m-%d %H:%M}"
