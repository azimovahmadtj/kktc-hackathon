"""
Fill the database with demo hotels, job ads, candidates and applications.

    python manage.py seed_demo            # add demo data (safe to run again)
    python manage.py seed_demo --reset    # delete previous demo data first

Demo logins (password for all: Demo12345!)
    isveren@demo.com   employer (Kaya Palazzo Resort)
    aday@demo.com      job seeker
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from portal import scoring
from portal.models import Application, CandidateProfile, EmployerProfile, Job, User

PASSWORD = "Demo12345!"
DEMO_DOMAIN = "@demo.com"

HOTELS = [
    ("isveren@demo.com", "Selin", "Arslan", "Kaya Palazzo Resort", "girne", True),
    ("conti@demo.com", "Mehmet", "Öztürk", "Salamis Bay Conti", "gazimagusa", True),
    ("noahs@demo.com", "Ayşe", "Demir", "Noah's Ark Deluxe", "bafra", True),
    ("elexus@demo.com", "Can", "Yıldız", "Elexus Hotel", "girne", False),
    ("merit@demo.com", "Deniz", "Kaya", "Merit Lefkoşa", "lefkosa", True),
]

JOBS = [
    # employer, title, department, city, type, salary, housing, meals, languages, min_exp, description
    (0, "Resepsiyonist", "front_office", "girne", "full_time", 1450, True, True, ["en", "ru"], 2,
     "Misafir giriş-çıkış işlemleri, rezervasyon yönetimi ve misafir ilişkileri.\nVardiyalı çalışma, haftada 1 gün izin."),
    (0, "Animatör", "entertainment", "girne", "seasonal", 1200, True, True, ["en"], 0,
     "Gündüz ve akşam animasyon programları, mini club ve sahne şovları.\nMayıs–Ekim sezonu."),
    (1, "Garson", "food_beverage", "gazimagusa", "seasonal", 1050, True, True, ["en"], 1,
     "A la carte ve açık büfe restoranlarda servis. Sezonluk, lojman ve yemek dahil."),
    (2, "Kat Görevlisi", "housekeeping", "bafra", "full_time", None, True, True, ["tr"], 0,
     "Oda temizliği ve düzeni, çamaşırhane ile koordinasyon."),
    (3, "Aşçı", "kitchen", "girne", "full_time", 1600, False, True, ["tr"], 3,
     "Sıcak mutfak, a la carte menü hazırlığı ve hijyen standartlarına uyum."),
    (2, "Barmen", "food_beverage", "bafra", "seasonal", 1150, True, False, ["en", "ru"], 1,
     "Havuz bar ve lobi bar hizmeti, kokteyl hazırlama."),
    (4, "Spa Terapisti", "spa", "lefkosa", "full_time", 1400, False, True, ["en", "de"], 2,
     "Masaj ve cilt bakımı uygulamaları, misafir danışmanlığı."),
    (1, "Teknik Servis Elemanı", "technical", "gazimagusa", "full_time", 1300, True, True, [], 2,
     "Elektrik, tesisat ve klima bakım-onarım işleri."),
]

CANDIDATES = [
    ("aday@demo.com", "Elena", "Kovalenko", "+90 533 111 22 33", 3, "front_office", "any", True, ["en", "ru", "tr"],
     "Üç yıldır 5 yıldızlı otellerde ön büro deneyimim var. Misafir memnuniyetine önem veririm."),
    ("ali@demo.com", "Ali", "Kaya", "+90 548 222 33 44", 1, "food_beverage", "seasonal", True, ["tr", "en"],
     "Sezonluk restoran servisi deneyimi, takım çalışmasına yatkın."),
    ("maria@demo.com", "Maria", "Petrova", "+90 533 444 55 66", 0, "entertainment", "seasonal", True, ["ru", "en"],
     "Dans ve sahne performansı geçmişi olan enerjik animatör adayı."),
    ("john@demo.com", "John", "Miller", "+90 542 555 66 77", 4, "kitchen", "full_time", False, ["en"],
     "Uluslararası mutfak deneyimi, a la carte ve banket."),
    ("zeynep@demo.com", "Zeynep", "Aydın", "+90 533 777 88 99", 2, "housekeeping", "any", False, ["tr"],
     "Kat hizmetlerinde iki yıl deneyim, düzenli ve titiz çalışırım."),
]

APPLICATIONS = [
    # candidate index, job index, status
    (0, 0, "interview"), (0, 6, "sent"), (1, 2, "reviewed"), (1, 5, "sent"),
    (2, 1, "sent"), (2, 5, "accepted"), (3, 4, "sent"), (4, 3, "rejected"), (4, 0, "sent"),
]


DEMO_CV_TEXT = {
    "aday@demo.com": [
        "Elena Kovalenko - Front Office / Receptionist",
        "Experience:",
        "2019 - 2021  Rixos Antalya - Receptionist (front desk, check-in / check-out)",
        "2021 - present  Kaya Palazzo, Kyrenia - Senior Receptionist, guest relations, Opera PMS",
        "Education: 2014 - 2018 University, Tourism Management",
        "Languages: Russian (native), English (fluent), Turkish (good)",
        "Skills: customer service, Opera PMS, MS Excel. Looking for a full-time job.",
    ],
    "ali@demo.com": [
        "Ali Kaya - Waiter / Bartender",
        "2020 - 2023  Salamis Bay Conti - Waiter, a la carte restaurant (seasonal)",
        "Languages: Turkish (native), English (intermediate)",
        "Skills: cocktails, cashier, HACCP, first aid. Looking for seasonal work.",
    ],
    "maria@demo.com": [
        "Maria Petrova - Animator / Entertainment",
        "Dancer and kids club animator, stage shows. Seasonal work 2024.",
        "Languages: Russian (native), English (good)",
    ],
    "john@demo.com": [
        "John Miller - Cook / Sous Chef",
        "2016 - 2019  Hilton Dubai - line cook. 2019 - 2022  Merit Hotel - sous chef, hot kitchen.",
        "Languages: English (native). HACCP certified. Full-time.",
    ],
    "zeynep@demo.com": [
        "Zeynep Aydin - Housekeeping / Room attendant",
        "2022 - 2024  Noah's Ark Deluxe - room attendant, laundry",
        "Languages: Turkish (native)",
    ],
}


def _pdf_escape(line):
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace")


def demo_cv(name, lines=None):
    """A small valid PDF with real CV text, so CV links and the free CV matching work in the demo."""
    lines = lines or [f"Demo CV - {name}"]
    stream = b"BT /F1 12 Tf 72 740 Td 16 TL " + b" ".join(b"(" + _pdf_escape(l) + b") '" for l in lines) + b" ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class Command(BaseCommand):
    help = "Create demo hotels, job ads, candidates and applications."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo users (…@demo.com) first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            deleted, _ = User.objects.filter(email__endswith=DEMO_DOMAIN).delete()
            self.stdout.write(f"Removed {deleted} demo objects.")

        employers = []
        for email, first, last, company, city, verified in HOTELS:
            user, created = User.objects.get_or_create(
                email=email, defaults={"first_name": first, "last_name": last, "role": User.Role.EMPLOYER})
            if created:
                user.set_password(PASSWORD)
                user.save()
            EmployerProfile.objects.update_or_create(
                user=user, defaults={"company_name": company, "city": city, "is_verified": verified,
                                     "phone": "+90 392 815 00 00",
                                     "description": f"{company}, Kuzey Kıbrıs'ın önde gelen konaklama tesislerinden biridir.",
                                     "confirmed_at": timezone.now()})
            employers.append(user)

        jobs = []
        for e, title, dept, city, etype, salary, housing, meals, langs, min_exp, desc in JOBS:
            job, _ = Job.objects.get_or_create(
                employer=employers[e], title=title,
                defaults=dict(department=dept, city=city, employment_type=etype, salary=salary, housing=housing,
                              meals=meals, required_languages=langs, min_experience=min_exp, description=desc))
            jobs.append(job)

        candidates = []
        for email, first, last, phone, exp, dept, avail, housing, langs, bio in CANDIDATES:
            user, created = User.objects.get_or_create(
                email=email, defaults={"first_name": first, "last_name": last, "role": User.Role.CANDIDATE})
            if created:
                user.set_password(PASSWORD)
                user.save()
            profile, _ = CandidateProfile.objects.update_or_create(
                user=user, defaults=dict(phone=phone, experience_years=exp, department=dept, availability=avail,
                                         needs_accommodation=housing, languages=langs, bio=bio,
                                         confirmed_at=timezone.now()))
            if not profile.cv:
                profile.cv.save(f"cv-{first.lower()}.pdf",
                                ContentFile(demo_cv(f"{first} {last}", DEMO_CV_TEXT.get(email))), save=True)
            candidates.append(profile)

        created_apps = 0
        for c, j, status in APPLICATIONS:
            match = scoring.compute(candidates[c], jobs[j])
            _, created = Application.objects.get_or_create(
                job=jobs[j], candidate=candidates[c].user,
                defaults={"status": status, "score": match["total"], "score_breakdown": match["parts"],
                          "candidate_seen": status == "sent"})
            created_apps += created

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {len(employers)} hotels, {len(jobs)} job ads, {len(candidates)} candidates, "
            f"{created_apps} new applications.\n"
            f"  Employer login:   isveren@demo.com / {PASSWORD}\n"
            f"  Job seeker login: aday@demo.com / {PASSWORD}"))
