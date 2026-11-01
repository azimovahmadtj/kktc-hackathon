import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import scoring
from .models import Application, CandidateProfile, EmployerProfile, Job, User

TMP_MEDIA = tempfile.mkdtemp()


class PortalHelpers:

    def make_employer(self, email="hotel@example.com"):
        user = User.objects.create_user(email, "Str0ng-pass!", role=User.Role.EMPLOYER, first_name="H")
        EmployerProfile.objects.create(user=user, company_name="Test Resort")
        return user

    def make_candidate(self, email="cand@example.com", **profile):
        user = User.objects.create_user(email, "Str0ng-pass!", first_name="Ada", last_name="Lee")
        defaults = dict(phone="+90 533 000 00 00", department="front_office", languages=["en", "ru"],
                        experience_years=3, cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4"))
        defaults.update(profile)
        CandidateProfile.objects.create(user=user, **defaults)
        return user

    def make_job(self, employer, **kw):
        data = dict(title="Receptionist", department="front_office", city="girne", employment_type="full_time",
                    required_languages=["en", "ru"], min_experience=2, housing=True)
        data.update(kw)
        return Job.objects.create(employer=employer, **data)



@override_settings(MEDIA_ROOT=TMP_MEDIA)
class PortalTests(PortalHelpers, TestCase):
    # ---- registration & login
    def test_register_candidate_logs_in_and_creates_profile(self):
        resp = self.client.post(reverse("register"), {
            "role": "candidate", "first_name": "Ahmad", "last_name": "Azimov", "email": "Ahmad@Example.com",
            "password1": "Otel-Portal-2026", "password2": "Otel-Portal-2026", "accept_terms": "on",
        })
        self.assertRedirects(resp, reverse("profile"))
        user = User.objects.get(email="ahmad@example.com")
        self.assertTrue(hasattr(user, "candidate_profile"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_register_employer_requires_company(self):
        resp = self.client.post(reverse("register"), {
            "role": "employer", "first_name": "A", "last_name": "B", "email": "e@example.com",
            "password1": "Otel-Portal-2026", "password2": "Otel-Portal-2026", "accept_terms": "on",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="e@example.com").exists())

    def test_login_with_email_case_insensitive(self):
        self.make_candidate()
        resp = self.client.post(reverse("login"), {"username": "CAND@example.com", "password": "Str0ng-pass!"})
        self.assertRedirects(resp, reverse("dashboard"))

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp["Location"])

    # ---- scoring
    def test_score_full_match(self):
        employer = self.make_employer()
        cand = self.make_candidate()
        job = self.make_job(employer)
        self.assertEqual(scoring.compute(cand.candidate_profile, job)["total"], 100)

    def test_score_partial(self):
        employer = self.make_employer()
        cand = self.make_candidate(department="kitchen", languages=["en"], experience_years=1,
                                   availability="seasonal", needs_accommodation=True)
        job = self.make_job(employer, housing=False)
        parts = scoring.compute(cand.candidate_profile, job)["parts"]
        self.assertEqual(parts, {"department": 0, "language": 12, "experience": 10, "availability": 0, "accommodation": 0})

    # ---- apply & permissions
    def test_apply_and_employer_updates_status(self):
        employer = self.make_employer()
        cand = self.make_candidate()
        job = self.make_job(employer)
        self.client.force_login(cand)
        self.client.post(reverse("job_apply", args=[job.pk]), {"note": "Hi"})
        app = Application.objects.get()
        self.assertEqual(app.score, 100)

        self.client.force_login(employer)
        self.client.post(reverse("application_status", args=[app.pk]), {"status": "interview"})
        app.refresh_from_db()
        self.assertEqual(app.status, "interview")
        self.assertFalse(app.candidate_seen)

    def test_other_employer_cannot_change_status_or_read_cv(self):
        employer = self.make_employer()
        other = self.make_employer("other@example.com")
        cand = self.make_candidate()
        app = Application.objects.create(job=self.make_job(employer), candidate=cand)
        self.client.force_login(other)
        resp = self.client.post(reverse("application_status", args=[app.pk]), {"status": "accepted"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.client.get(reverse("application_cv", args=[app.pk])).status_code, 403)

    def test_incomplete_profile_cannot_apply(self):
        employer = self.make_employer()
        user = User.objects.create_user("new@example.com", "Str0ng-pass!")
        CandidateProfile.objects.create(user=user)
        self.client.force_login(user)
        resp = self.client.post(reverse("job_apply", args=[self.make_job(employer).pk]))
        self.assertRedirects(resp, reverse("profile"))
        self.assertFalse(Application.objects.exists())

    # ---- pages render in all three languages
    def test_pages_render_in_three_languages(self):
        employer = self.make_employer()
        cand = self.make_candidate()
        job = self.make_job(employer)
        Application.objects.create(job=job, candidate=cand, score=80)
        expectations = {"tr": "Panel", "en": "Dashboard", "ru": "Панель"}
        for code, word in expectations.items():
            self.client.cookies["oip_language"] = code
            self.assertEqual(self.client.get(reverse("landing")).status_code, 200)
            for user in (employer, cand):
                self.client.force_login(user)
                for name in ("dashboard", "profile", "applications", "market"):
                    resp = self.client.get(reverse(name))
                    self.assertEqual(resp.status_code, 200, f"{name} {code}")
                self.assertContains(self.client.get(reverse("dashboard")), word)
                self.assertEqual(self.client.get(reverse("job_detail", args=[job.pk])).status_code, 200)
            self.client.force_login(employer)
            self.assertEqual(self.client.get(reverse("my_jobs")).status_code, 200)
            self.assertEqual(self.client.get(reverse("job_create")).status_code, 200)
            self.client.logout()


# ---------------------------------------------------------------- AI CV matching (Claude API mocked)
import io as _io
import json as _json
import zipfile as _zipfile
from types import SimpleNamespace
from unittest import mock

from . import ai
from .models import CvAnalysis


def fake_response(payload, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=_json.dumps(payload))],
        stop_reason=stop_reason, stop_details=None, model="claude-opus-5-5", _request_id="req_test",
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300, cache_read_input_tokens=900),
    )


def make_docx(text):
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml",
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                    f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p><w:p><w:r><w:t>Line two</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TMP_MEDIA, ANTHROPIC_API_KEY="test-key", ANTHROPIC_MODEL="claude-opus-5-5")
class AiMatchTests(PortalHelpers, TestCase):
    def payload(self, job_ids):
        return {
            "is_cv": True,
            "candidate": {"full_name": "Ada Lee", "summary": "Receptionist with 4 years.", "experience_years": 4,
                          "department": "front_office", "languages": ["en", "ru", "de"], "availability": "full_time",
                          "skills": ["Opera PMS"], "suggested_bio": "I am a friendly receptionist."},
            "matches": [{"job_id": i, "fit_score": 130 if n == 0 else 70, "reasons": ["Languages"], "gaps": []}
                        for n, i in enumerate(job_ids)],
        }

    def test_docx_text_extraction(self):
        self.assertEqual(ai.docx_text(make_docx("Reception 2019-2023")), "Reception 2019-2023\nLine two")

    def test_run_analysis_saves_result_and_builds_request(self):
        employer = self.make_employer()
        job = self.make_job(employer)
        cand = self.make_candidate()
        client = mock.Mock()
        client.beta.messages.create.return_value = fake_response(self.payload([job.id, 999999, job.id]))
        self.client.force_login(cand)
        with mock.patch.object(ai, "get_client", return_value=client):
            resp = self.client.post(reverse("ai_match_run"))
        self.assertRedirects(resp, reverse("ai_match"))

        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertIn("cache_control", kwargs["system"][-1])
        self.assertIn(f'"id": {job.id}', kwargs["system"][-1]["text"])
        self.assertEqual(kwargs["messages"][0]["content"][0]["type"], "document")  # PDF sent natively

        analysis = CvAnalysis.objects.get()
        self.assertEqual([m["job_id"] for m in analysis.result["matches"]], [job.id])  # unknown + duplicate dropped
        self.assertEqual(analysis.result["matches"][0]["fit_score"], 100)              # clamped
        self.assertEqual(analysis.cache_read_tokens, 900)

        page = self.client.get(reverse("ai_match"))
        self.assertContains(page, job.title)
        self.assertContains(page, "Languages")

    def test_apply_profile_from_analysis(self):
        cand = self.make_candidate(languages=["en"], department="kitchen", experience_years=1)
        analysis = CvAnalysis.objects.create(candidate=cand, cv_name="cv.pdf", language="en", model="m",
                                             result=self.payload([]))
        self.client.force_login(cand)
        self.client.post(reverse("ai_apply_profile", args=[analysis.pk]),
                         {"fields": ["department", "languages", "experience", "bio"]})
        p = CandidateProfile.objects.get(user=cand)
        self.assertEqual(p.department, "front_office")
        self.assertEqual(p.languages, ["de", "en", "ru"])
        self.assertEqual(p.experience_years, 4)
        self.assertEqual(p.bio, "I am a friendly receptionist.")
        self.assertEqual(p.availability, "any")  # not selected -> unchanged

    def test_refusal_shows_error_and_saves_nothing(self):
        self.make_job(self.make_employer())
        cand = self.make_candidate()
        client = mock.Mock()
        client.beta.messages.create.return_value = fake_response({}, stop_reason="refusal")
        self.client.force_login(cand)
        with mock.patch.object(ai, "get_client", return_value=client):
            resp = self.client.post(reverse("ai_match_run"), follow=True)
        self.assertFalse(CvAnalysis.objects.exists())
        self.assertEqual(len(list(resp.context["messages"])), 1)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_without_key_uses_free_local_matcher(self):
        employer = self.make_employer()
        reception = self.make_job(employer)
        self.make_job(employer, title="Aşçı", department="kitchen", required_languages=["tr"])
        cv = make_docx("Reception 2019 - 2024 Kaya Palazzo front desk. Languages: English, Russian. Full-time.")
        cand = self.make_candidate(cv=SimpleUploadedFile("cv.docx", cv), department="", languages=[])
        self.client.force_login(cand)
        with mock.patch.object(ai, "get_client") as get_client:
            resp = self.client.post(reverse("ai_match_run"), follow=True)
        get_client.assert_not_called()  # no API call
        analysis = CvAnalysis.objects.get()
        self.assertEqual(analysis.model, "local")
        self.assertEqual(analysis.result["candidate"]["department"], "front_office")
        self.assertEqual(analysis.result["matches"][0]["job_id"], reception.id)
        self.assertEqual(analysis.result["matches"][0]["fit_score"], 100)
        self.assertContains(resp, reception.title)

    def test_docx_cv_sent_as_text(self):
        self.make_job(self.make_employer())
        cand = self.make_candidate(cv=SimpleUploadedFile("cv.docx", make_docx("Waiter at Kaya 2021")))
        block = ai.cv_content_block(cand.candidate_profile)
        self.assertEqual(block["type"], "text")
        self.assertIn("Waiter at Kaya 2021", block["text"])


def tearDownModule():
    shutil.rmtree(TMP_MEDIA, ignore_errors=True)


class LocalMatcherFactsTests(TestCase):
    def test_russian_cv(self):
        from .local_matcher import extract_facts
        f = extract_facts("Администратор ресепшн\n2019 – 2021 Rixos\n03.2021 – настоящее время Kaya Palazzo\n"
                          "Образование: 2014 – 2018 Университет\nЯзыки: русский, английский\nВозраст: 29 лет")
        self.assertEqual(f["department"], "front_office")
        self.assertEqual(f["languages"], ["en", "ru"])
        self.assertGreaterEqual(f["experience_years"], 5)   # education and age lines are ignored

    def test_turkish_cv(self):
        from .local_matcher import extract_facts
        f = extract_facts("Garson. 4 yıl sezonluk restoran deneyimi, 5 yıldızlı otellerde servis. "
                          "Diller: Türkçe, İngilizce. HACCP, ilk yardım.")
        self.assertEqual(f["department"], "food_beverage")
        self.assertEqual(f["experience_years"], 4)            # "5 yıldızlı" (5-star) is not experience
        self.assertEqual(f["availability"], "seasonal")
        self.assertEqual(f["languages"], ["tr", "en"])
        self.assertIn("HACCP", f["skills"])


# ---------------------------------------------------------------- profile confirm / edit flow and photos
PNG_1PX = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
           b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ProfileFlowTests(PortalHelpers, TestCase):
    def profile_post(self, **extra):
        data = {"phone": "+90 533 000 00 00", "experience_years": "2", "department": "front_office",
                "availability": "any", "languages": ["en"], "first_name": "Ada", "last_name": "Lee"}
        data.update(extra)
        return data

    def test_first_save_is_confirm_and_goes_to_job_ads(self):
        cand = self.make_candidate()
        self.client.force_login(cand)
        page = self.client.get(reverse("profile"))
        self.assertEqual(page.context["mode"], "confirm")
        resp = self.client.post(reverse("profile"), self.profile_post())
        self.assertRedirects(resp, reverse("market") + "?sort=match")
        self.assertIsNotNone(CandidateProfile.objects.get(user=cand).confirmed_at)

    def test_confirmed_profile_view_then_edit(self):
        cand = self.make_candidate()
        CandidateProfile.objects.filter(user=cand).update(confirmed_at="2026-01-01T00:00:00Z")
        self.client.force_login(cand)
        view = self.client.get(reverse("profile"))
        self.assertEqual(view.context["mode"], "view")
        self.assertIsNone(view.context["form"])
        edit = self.client.get(reverse("profile") + "?edit=1")
        self.assertEqual(edit.context["mode"], "edit")
        resp = self.client.post(reverse("profile"), self.profile_post(phone="+90 548 111 11 11"))
        self.assertRedirects(resp, reverse("profile"))
        self.assertEqual(CandidateProfile.objects.get(user=cand).phone, "+90 548 111 11 11")

    def test_photo_upload_change_delete(self):
        cand = self.make_candidate()
        self.client.force_login(cand)
        self.client.post(reverse("photo_upload"), {"photo": SimpleUploadedFile("me.png", PNG_1PX)})
        cand.refresh_from_db()
        first = cand.photo.name
        self.assertTrue(first)
        self.assertEqual(self.client.get(reverse("user_photo", args=[cand.pk]))["Content-Type"], "image/png")

        self.client.post(reverse("photo_upload"), {"photo": SimpleUploadedFile("new.png", PNG_1PX)})
        cand.refresh_from_db()
        self.assertNotEqual(cand.photo.name, first)
        self.assertFalse(cand.photo.storage.exists(first))  # old file removed

        self.client.post(reverse("photo_delete"))
        cand.refresh_from_db()
        self.assertFalse(cand.photo)

    def test_fake_image_rejected(self):
        cand = self.make_candidate()
        self.client.force_login(cand)
        self.client.post(reverse("photo_upload"), {"photo": SimpleUploadedFile("evil.png", b"<script>alert(1)</script>")})
        cand.refresh_from_db()
        self.assertFalse(cand.photo)

    def test_photo_visibility(self):
        employer = self.make_employer()
        other_employer = self.make_employer("other@example.com")
        cand = self.make_candidate()
        stranger = self.make_candidate("stranger@example.com")
        self.client.force_login(cand)
        self.client.post(reverse("photo_upload"), {"photo": SimpleUploadedFile("me.png", PNG_1PX)})
        Application.objects.create(job=self.make_job(employer), candidate=cand)
        url = reverse("user_photo", args=[cand.pk])
        self.client.force_login(employer)
        self.assertEqual(self.client.get(url).status_code, 200)        # candidate applied to this hotel
        self.client.force_login(other_employer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(url).status_code, 403)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class EmployerProfileFlowTests(PortalHelpers, TestCase):
    def data(self, **extra):
        d = {"company_name": "Test Resort", "city": "girne", "phone": "+90 392 000 00 00", "website": "",
             "description": "Beach resort", "first_name": "Selin", "last_name": "Arslan"}
        d.update(extra)
        return d

    def test_employer_confirm_then_view_then_edit(self):
        employer = self.make_employer()
        self.client.force_login(employer)
        self.assertEqual(self.client.get(reverse("profile")).context["mode"], "confirm")
        resp = self.client.post(reverse("profile"), self.data())
        self.assertRedirects(resp, reverse("my_jobs"))
        self.assertIsNotNone(EmployerProfile.objects.get(user=employer).confirmed_at)

        view = self.client.get(reverse("profile"))
        self.assertEqual(view.context["mode"], "view")
        self.assertContains(view, "Beach resort")
        self.assertEqual(self.client.get(reverse("profile") + "?edit=1").context["mode"], "edit")
        resp = self.client.post(reverse("profile"), self.data(company_name="New Name Resort"))
        self.assertRedirects(resp, reverse("profile"))
        self.assertEqual(EmployerProfile.objects.get(user=employer).company_name, "New Name Resort")
