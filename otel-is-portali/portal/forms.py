import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import (
    Application, Availability, CandidateProfile, City, Department, EmployerProfile, EmploymentType, Job, Language, User,
)

PHONE_RE = re.compile(r"^[0-9+ ()\-]{7,20}$")


class RegisterForm(BaseUserCreationForm):
    role = forms.ChoiceField(
        label=_("I am a"), choices=User.Role.choices, widget=forms.RadioSelect, initial=User.Role.CANDIDATE,
    )
    company_name = forms.CharField(label=_("Hotel / company name"), max_length=120, required=False)
    city = forms.ChoiceField(label=_("City"), choices=City.choices, required=False, initial=City.GIRNE)
    accept_terms = forms.BooleanField(label=_("I accept the terms of use and privacy policy"))

    class Meta:
        model = User
        fields = ("role", "first_name", "last_name", "email")
        labels = {"first_name": _("First name"), "last_name": _("Last name"), "email": _("Email")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].label = _("Password")
        self.fields["password2"].label = _("Repeat password")
        self.fields["password1"].help_text = _("At least 8 characters, not only numbers.")
        self.fields["password2"].help_text = ""
        autocomplete = {"first_name": "given-name", "last_name": "family-name", "email": "email",
                        "password1": "new-password", "password2": "new-password", "company_name": "organization"}
        for name, value in autocomplete.items():
            self.fields[name].widget.attrs["autocomplete"] = value

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("role") == User.Role.EMPLOYER and not cleaned.get("company_name", "").strip():
            self.add_error("company_name", _("Please enter your hotel or company name."))
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        user.save()
        if user.is_employer:
            EmployerProfile.objects.create(
                user=user, company_name=self.cleaned_data["company_name"].strip(),
                city=self.cleaned_data.get("city") or City.GIRNE,
            )
        else:
            CandidateProfile.objects.create(user=user)
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))

    error_messages = {
        "invalid_login": _("Email or password is incorrect."),
        "inactive": _("This account is inactive."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].label = _("Password")

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class NameFieldsMixin(forms.Form):
    first_name = forms.CharField(label=_("First name"), max_length=150)
    last_name = forms.CharField(label=_("Last name"), max_length=150)

    def save_names(self, user):
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.save(update_fields=["first_name", "last_name"])


def clean_phone_value(value, required=True):
    value = (value or "").strip()
    if not value:
        if required:
            raise forms.ValidationError(_("Phone is required."))
        return value
    if not PHONE_RE.match(value):
        raise forms.ValidationError(_("Enter a valid phone number."))
    return value


class CandidateProfileForm(NameFieldsMixin, forms.ModelForm):
    languages = forms.MultipleChoiceField(
        label=_("Languages"), choices=Language.choices, widget=forms.CheckboxSelectMultiple,
        error_messages={"required": _("Select at least one language.")},
    )
    cv = forms.FileField(label=_("CV"), required=False, widget=forms.FileInput(attrs={"accept": ".pdf,.doc,.docx"}))
    remove_cv = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = CandidateProfile
        fields = ("phone", "experience_years", "department", "availability", "needs_accommodation", "languages", "bio", "cv")
        widgets = {
            "phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel", "placeholder": "05XX XXX XX XX"}),
            "experience_years": forms.NumberInput(attrs={"min": 0, "max": 50}),
            "bio": forms.Textarea(attrs={"rows": 4, "maxlength": 500}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
        self.fields["phone"].required = True
        self.fields["department"].required = True
        self.fields["department"].choices = [("", _("Select…"))] + list(Department.choices)
        self.fields["availability"].required = True
        self.fields["bio"].widget.attrs["placeholder"] = _("Write a short introduction about yourself…")
        # Field order for the two-column layout
        self.order_fields(["phone", "experience_years", "department", "availability", "needs_accommodation",
                           "languages", "bio", "cv", "first_name", "last_name"])

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv and hasattr(cv, "size") and cv.size > settings.CV_MAX_UPLOAD_BYTES:
            raise forms.ValidationError(_("The file can be at most 5 MB."))
        return cv

    def clean(self):
        cleaned = super().clean()
        has_new = bool(self.files.get("cv"))
        has_old = bool(self.instance.cv) and not cleaned.get("remove_cv")
        if not has_new and not has_old:
            self.add_error("cv", _("Please upload your CV."))
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get("remove_cv") and not self.files.get("cv") and profile.cv:
            profile.cv.delete(save=False)
            profile.cv = ""
        profile.save()
        self.save_names(profile.user)
        return profile


class EmployerProfileForm(NameFieldsMixin, forms.ModelForm):
    class Meta:
        model = EmployerProfile
        fields = ("company_name", "city", "phone", "website", "description")
        widgets = {
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"), required=False)

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save()
        self.save_names(profile.user)
        return profile


class JobForm(forms.ModelForm):
    required_languages = forms.MultipleChoiceField(
        label=_("Required languages"), choices=Language.choices, widget=forms.CheckboxSelectMultiple, required=False,
    )

    class Meta:
        model = Job
        fields = ("title", "department", "city", "employment_type", "salary", "min_experience",
                  "required_languages", "housing", "meals", "description", "is_active")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": _("e.g. Receptionist")}),
            "salary": forms.NumberInput(attrs={"min": 0, "placeholder": "1200"}),
            "min_experience": forms.NumberInput(attrs={"min": 0, "max": 50}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].choices = [("", _("Select…"))] + list(Department.choices)
        self.fields["employment_type"].choices = [("", _("Select…"))] + list(EmploymentType.choices)
        self.fields["description"].widget.attrs["placeholder"] = _("Duties, working hours, benefits…")


class ApplyForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("note",)
        widgets = {"note": forms.Textarea(attrs={"rows": 3, "maxlength": 1000})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].label = _("Note to the employer (optional)")
        self.fields["note"].widget.attrs["placeholder"] = _("Why are you a good fit for this position?")


class JobFilterForm(forms.Form):
    q = forms.CharField(required=False)
    department = forms.ChoiceField(required=False, choices=[("", _("All departments"))] + list(Department.choices))
    city = forms.ChoiceField(required=False, choices=[("", _("All regions"))] + list(City.choices))
    type = forms.ChoiceField(required=False, choices=[("", _("All types"))] + list(EmploymentType.choices))
    housing = forms.BooleanField(required=False)
    sort = forms.ChoiceField(required=False, choices=[("new", _("Newest")), ("match", _("Best match"))])


PHOTO_MAX_BYTES = 3 * 1024 * 1024
PHOTO_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",), ".webp": (b"RIFF",),
}


class PhotoForm(forms.Form):
    photo = forms.FileField(label=_("Profile photo"), error_messages={"required": _("Choose a photo to upload.")})

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        ext = ("." + photo.name.rsplit(".", 1)[-1]).lower() if "." in photo.name else ""
        if ext not in PHOTO_SIGNATURES:
            raise forms.ValidationError(_("The photo must be a JPG, PNG or WEBP image."))
        if photo.size > PHOTO_MAX_BYTES:
            raise forms.ValidationError(_("The photo can be at most 3 MB."))
        head = photo.read(16)
        photo.seek(0)
        valid = any(head.startswith(sig) for sig in PHOTO_SIGNATURES[ext]) and (ext != ".webp" or head[8:12] == b"WEBP")
        if not valid:
            raise forms.ValidationError(_("The photo must be a JPG, PNG or WEBP image."))
        return photo
