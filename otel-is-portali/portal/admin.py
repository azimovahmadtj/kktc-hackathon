from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Application, CandidateProfile, EmployerProfile, Job, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password", "role")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "experience_years", "availability", "needs_accommodation", "updated_at")
    list_filter = ("department", "availability", "needs_accommodation")
    search_fields = ("user__email", "user__first_name", "user__last_name")


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "city", "user", "is_verified")
    list_filter = ("city", "is_verified")
    list_editable = ("is_verified",)
    search_fields = ("company_name", "user__email")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "department", "city", "employment_type", "is_active", "created_at")
    list_filter = ("department", "city", "employment_type", "is_active")
    search_fields = ("title", "employer__employer_profile__company_name")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "score", "created_at")
    list_filter = ("status",)
    search_fields = ("candidate__email", "job__title")


from .models import CvAnalysis  # noqa: E402


@admin.register(CvAnalysis)
class CvAnalysisAdmin(admin.ModelAdmin):
    list_display = ("candidate", "cv_name", "model", "language", "input_tokens", "output_tokens", "cache_read_tokens", "created_at")
    list_filter = ("model", "language")
    search_fields = ("candidate__email", "request_id")
    readonly_fields = [f.name for f in CvAnalysis._meta.fields]
