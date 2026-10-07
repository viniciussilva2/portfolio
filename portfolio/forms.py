"""Contact form, with the anti-spam checks that need no database."""

import time

from django import forms
from django.conf import settings
from django.core import signing

from .content import get_interface

_TOKEN_SALT = "portfolio.contact"


def new_form_token(issued_at: float | None = None) -> str:
    """Signed record of the moment the form was handed to the visitor."""
    return signing.dumps(time.time() if issued_at is None else issued_at, salt=_TOKEN_SALT)


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=254)
    message = forms.CharField(max_length=4000)
    # Honeypot: hidden from people by CSS, filled in by bots that complete every field.
    website = forms.CharField(required=False)
    token = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Messages in the language of the page the form was sent from.
        ui = self.ui = get_interface()
        self.fields["name"].error_messages["required"] = ui["error_name"]
        self.fields["email"].error_messages["required"] = ui["error_email"]
        self.fields["email"].error_messages["invalid"] = ui["error_email_invalid"]
        self.fields["message"].error_messages["required"] = ui["error_message"]

    def clean_name(self):
        # One line only: the name goes into the e-mail subject.
        return " ".join(self.cleaned_data["name"].split())

    def clean_token(self):
        ui = self.ui
        try:
            issued_at = float(signing.loads(self.cleaned_data["token"], salt=_TOKEN_SALT))
        except (signing.BadSignature, TypeError, ValueError):
            raise forms.ValidationError(ui["form_expired"], code="expired") from None
        age = time.time() - issued_at
        if age > settings.CONTACT_MAX_FORM_AGE_SECONDS:
            raise forms.ValidationError(ui["form_expired"], code="expired")
        if age < settings.CONTACT_MIN_FILL_SECONDS:
            raise forms.ValidationError(ui["form_too_fast"], code="too_fast")
        return self.cleaned_data["token"]

    @property
    def token_error(self) -> forms.ValidationError | None:
        errors = self.errors.as_data().get("token")
        return errors[0] if errors else None

    @property
    def field_errors(self) -> dict[str, list[str]]:
        """Errors the visitor can fix, keyed by field name."""
        return {name: list(messages) for name, messages in self.errors.items() if name != "token"}
