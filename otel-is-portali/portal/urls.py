from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("panel/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("profile/cv/", views.my_cv, name="my_cv"),
    path("profile/photo/", views.photo_upload, name="photo_upload"),
    path("profile/photo/delete/", views.photo_delete, name="photo_delete"),
    path("users/<int:pk>/photo/", views.user_photo, name="user_photo"),

    path("applications/", views.applications, name="applications"),
    path("applications/<int:pk>/status/", views.application_status, name="application_status"),
    path("applications/<int:pk>/withdraw/", views.application_withdraw, name="application_withdraw"),
    path("applications/<int:pk>/cv/", views.application_cv, name="application_cv"),

    path("my-jobs/", views.my_jobs, name="my_jobs"),
    path("my-jobs/new/", views.job_create, name="job_create"),
    path("my-jobs/<int:pk>/edit/", views.job_edit, name="job_edit"),
    path("my-jobs/<int:pk>/toggle/", views.job_toggle, name="job_toggle"),
    path("my-jobs/<int:pk>/delete/", views.job_delete, name="job_delete"),

    path("ai/match/", views.ai_match, name="ai_match"),
    path("ai/match/run/", views.ai_match_run, name="ai_match_run"),
    path("ai/match/<int:pk>/apply-profile/", views.ai_apply_profile, name="ai_apply_profile"),

    path("jobs/", views.market, name="market"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/apply/", views.job_apply, name="job_apply"),
]
