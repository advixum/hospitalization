from datetime import date, timedelta
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from .models import Patients, Files


# Create your forms here.
class AuthForm(AuthenticationForm):
    username = UsernameField(
        label=_('Логин'), 
        widget=forms.TextInput(attrs={"autofocus": True})
    )
    password = forms.CharField(
        label=_('Пароль'),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": _(
            "Пожалуйста, введите корректное имя пользователя и пароль. "
            "Проверьте регистр вводимых данных."
        ),
        "inactive": _("Этот аккаунт не активен."),
    }

class NewPatientForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        md = self.min_date()
        m = _('Дата должна быть равна или позднее %(limit_value)s.')
        self.fields['hosp_date'].validators=[MinValueValidator(md, m)]
        self.fields['oper_date'].validators=[MinValueValidator(md, m)]
        self.fields['alteration_user'].required=False
        self.fields['equipment'].required=False
        for field in self.fields.values():
            field.error_messages = {
                'required': 'Поле {f} необходимо заполнить.'.format(f=field.label)
            }
    
    def min_date(self):
        """Return the minimum date value for the validator."""
        target_day = date.today() - timedelta(days=7)
        while target_day.isoweekday() != 1:
            target_day -= timedelta(days=1)
        return target_day
    
    foreign_key = forms.ModelChoiceField(
        required=False,
        queryset=Files.objects.all(),
        widget=(forms.HiddenInput())
    )
    timestamp = forms.DateTimeField(
        required=False,
        widget=(forms.HiddenInput())
    )
    class Meta:
        model = Patients
        exclude = [
            'alteration_date'
        ]
        widgets = {
            'plain_text': forms.HiddenInput(),
            'alteration_user': forms.HiddenInput(),
            'hosp_date': forms.DateInput(attrs={'type': 'date'}),
            'oper_date': forms.DateInput(attrs={'type': 'date'}),
        }

class UploadFileForm(forms.Form):
    file = forms.FileField(
        label='Консультативное заключение',
        validators=[FileExtensionValidator(
            allowed_extensions=['rtf', 'docx'],
            message = _(
                "Файл типа “%(extension)s” не поддерживается. "
                "Доступные типы файлов: %(allowed_extensions)s."
            )
        )]
    )

class MultiUploadFileForm(forms.Form):
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True})
    )
