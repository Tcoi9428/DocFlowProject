from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .user_display import user_identity
from .models import (
    ApprovalRoute,
    ApprovalTask,
    Attachment,
    ContractKind,
    CorrespondenceDepartment,
    CorrespondenceRecord,
    CustomFieldDefinition,
    Document,
    DocumentComment,
    DocumentPurpose,
    DocumentType,
    PasswordResetRequest,
)


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return user_identity(obj)


class OutgoingCorrespondenceForm(forms.ModelForm):
    executor = UserModelChoiceField(
        label="Исполнитель",
        queryset=User.objects.none(),
    )

    class Meta:
        model = CorrespondenceRecord
        fields = [
            "department",
            "reply_to",
            "related_document_number",
            "addressee",
            "addressee_person",
            "subject",
            "registration_date",
            "executor",
            "signed_file",
        ]
        widgets = {
            "registration_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "addressee": forms.TextInput(attrs={"placeholder": "Наименование организации"}),
            "addressee_person": forms.TextInput(attrs={"placeholder": "ФИО и должность получателя"}),
            "subject": forms.TextInput(attrs={"placeholder": "Например: О согласовании поставки запасных частей"}),
            "signed_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}),
            "related_document_number": forms.TextInput(
                attrs={"placeholder": "Укажите номер, если письма еще нет в системе"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = CorrespondenceDepartment.objects.filter(is_active=True)
        self.fields["reply_to"].queryset = CorrespondenceRecord.objects.filter(
            kind=CorrespondenceRecord.INCOMING,
            status=CorrespondenceRecord.REGISTERED,
        ).order_by("-registration_date", "-sequence_number")
        self.fields["reply_to"].required = False
        self.fields["reply_to"].label = "Связанное входящее письмо"
        self.fields["reply_to"].empty_label = "Не выбрано"
        self.fields["reply_to"].widget.attrs.update(
            {
                "data-searchable-select": "true",
                "data-search-placeholder": "Поиск по номеру или наименованию",
            }
        )
        self.fields["related_document_number"].required = False
        self.fields["executor"].queryset = (
            User.objects.filter(is_active=True)
            .select_related("userprofile")
            .order_by("last_name", "first_name", "username")
        )
        self.fields["executor"].widget.attrs.update(
            {
                "data-searchable-select": "true",
                "data-search-placeholder": "Поиск по ФИО или должности",
            }
        )
        self.fields["signed_file"].required = False
        self.fields["registration_date"].input_formats = ["%Y-%m-%d"]
        max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
        self.fields["signed_file"].help_text = f"Можно прикрепить позднее. Максимальный размер файла — {max_size_mb} МБ."

    def clean_signed_file(self):
        uploaded_file = self.cleaned_data.get("signed_file")
        if uploaded_file and uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
            raise ValidationError(f"Размер файла больше {max_size_mb} МБ.")
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("reply_to"):
            cleaned_data["related_document_number"] = ""
        return cleaned_data


class IncomingCorrespondenceForm(forms.ModelForm):
    class Meta:
        model = CorrespondenceRecord
        fields = [
            "department",
            "subject",
            "sender",
            "related_outgoing",
            "related_document_number",
            "registration_date",
            "resolution",
            "incoming_file",
        ]
        widgets = {
            "subject": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Введите наименование входящего письма"}
            ),
            "sender": forms.TextInput(attrs={"placeholder": "Организация или ФИО отправителя"}),
            "related_document_number": forms.TextInput(
                attrs={"placeholder": "Номер из старого реестра, если письма нет в системе"}
            ),
            "registration_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "resolution": forms.Textarea(attrs={"rows": 4, "placeholder": "Текст резолюции"}),
            "incoming_file": forms.ClearableFileInput(
                attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = CorrespondenceDepartment.objects.filter(is_active=True)
        self.fields["department"].required = True
        self.fields["subject"].required = True
        self.fields["sender"].required = True
        self.fields["related_outgoing"].queryset = CorrespondenceRecord.objects.filter(
            kind=CorrespondenceRecord.OUTGOING,
            status=CorrespondenceRecord.REGISTERED,
        ).order_by("-registration_date", "-sequence_number")
        self.fields["related_outgoing"].required = False
        self.fields["related_outgoing"].empty_label = "Не выбрано"
        self.fields["related_outgoing"].widget.attrs.update(
            {
                "data-searchable-select": "true",
                "data-search-placeholder": "Поиск по номеру или наименованию",
            }
        )
        self.fields["related_document_number"].required = False
        self.fields["resolution"].required = False
        self.fields["incoming_file"].required = False
        self.fields["registration_date"].input_formats = ["%Y-%m-%d"]
        max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
        self.fields["incoming_file"].help_text = (
            f"Поле необязательное. Максимальный размер файла — {max_size_mb} МБ."
        )

    def clean_incoming_file(self):
        uploaded_file = self.cleaned_data.get("incoming_file")
        if uploaded_file and uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
            raise ValidationError(f"Размер файла больше {max_size_mb} МБ.")
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("related_outgoing"):
            cleaned_data["related_document_number"] = ""
        return cleaned_data


class IncomingCorrespondenceFileForm(forms.ModelForm):
    class Meta:
        model = CorrespondenceRecord
        fields = ["incoming_file"]
        widgets = {
            "incoming_file": forms.ClearableFileInput(
                attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}
            ),
        }

    def clean_incoming_file(self):
        uploaded_file = self.cleaned_data.get("incoming_file")
        if not uploaded_file:
            raise ValidationError("Выберите файл входящего письма.")
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
            raise ValidationError(f"Размер файла больше {max_size_mb} МБ.")
        return uploaded_file


class SignedCorrespondenceFileForm(forms.ModelForm):
    class Meta:
        model = CorrespondenceRecord
        fields = ["signed_file"]
        widgets = {
            "signed_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}),
        }

    def clean_signed_file(self):
        uploaded_file = self.cleaned_data.get("signed_file")
        if not uploaded_file:
            raise ValidationError("Выберите подписанный документ.")
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE // 1024 // 1024
            raise ValidationError(f"Размер файла больше {max_size_mb} МБ.")
        return uploaded_file


class DocumentForm(forms.ModelForm):
    HIDDEN_CUSTOM_FIELDS_BY_TYPE = {
        "DOG": {"counterparty_contract_no", "contract_end_date"},
        "SZ": {"reason", "requires_execution"},
    }

    class Meta:
        model = Document
        fields = [
            "document_type",
            "contract_kind",
            "document_purpose",
            "title",
            "internal_number",
            "responsible",
            "department",
            "route",
            "approval_route_type",
            "registration_date",
            "due_date",
            "amount",
            "counterparty",
            "summary",
        ]
        widgets = {
            "registration_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "approval_route_type": forms.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        self.custom_field_definitions = kwargs.pop("custom_field_definitions", None)
        super().__init__(*args, **kwargs)
        self.fields["responsible"] = UserModelChoiceField(
            queryset=User.objects.filter(is_active=True).select_related("userprofile").order_by("last_name", "first_name", "username"),
            required=False,
            label=self.fields["responsible"].label,
        )
        self.fields["contract_kind"].queryset = ContractKind.objects.filter(is_active=True)
        self.fields["document_purpose"].queryset = DocumentPurpose.objects.filter(is_active=True)
        self.fields["route"].queryset = ApprovalRoute.objects.filter(is_active=True)
        selected_type_id = self.data.get("document_type") or self.initial.get("document_type")
        if self.instance and self.instance.pk and self.instance.document_type_id:
            selected_type_id = self.instance.document_type_id
        selected_document_type = None
        if selected_type_id:
            selected_document_type = DocumentType.objects.filter(pk=selected_type_id).first()
            self.fields["route"].queryset = self.fields["route"].queryset.filter(
                document_type_id=selected_type_id
            )
        if selected_document_type and selected_document_type.code in {"DOG", "SZ", "PRK"}:
            self.fields["summary"].label = "Примечание"
            self.fields["amount"].required = False
            self.fields.pop("amount", None)
        if selected_document_type and selected_document_type.code in {"SZ", "PRK"}:
            self.fields.pop("counterparty", None)
        if not selected_document_type or selected_document_type.code != "DOG":
            self.fields.pop("contract_kind", None)
            self.fields.pop("document_purpose", None)

        definitions = self.custom_field_definitions
        if definitions is None and self.instance and self.instance.document_type_id:
            definitions = self.instance.document_type.custom_fields.filter(is_active=True)

        for definition in definitions or []:
            if (
                selected_document_type
                and definition.key in self.HIDDEN_CUSTOM_FIELDS_BY_TYPE.get(selected_document_type.code, set())
            ):
                continue
            field_name = f"custom__{definition.key}"
            initial = (self.instance.custom_data or {}).get(definition.key)
            self.fields[field_name] = self._build_custom_field(definition, initial)

    def _build_custom_field(self, definition, initial):
        common = {
            "label": definition.name,
            "required": definition.is_required,
            "initial": initial,
        }
        if definition.field_type == CustomFieldDefinition.NUMBER:
            return forms.DecimalField(**common)
        if definition.field_type == CustomFieldDefinition.DATE:
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
        if definition.field_type == CustomFieldDefinition.BOOLEAN:
            return forms.BooleanField(required=False, label=definition.name, initial=bool(initial))
        if definition.field_type == CustomFieldDefinition.CHOICE:
            choices = [("", "---------")] + [(value, value) for value in definition.choice_list()]
            return forms.ChoiceField(choices=choices, **common)
        return forms.CharField(widget=forms.TextInput(), **common)

    def clean(self):
        cleaned_data = super().clean()
        route = cleaned_data.get("route")
        document_type = cleaned_data.get("document_type")
        if route and document_type and route.document_type_id != document_type.id:
            self.add_error("route", "Маршрут должен соответствовать выбранному типу документа.")
        if document_type and document_type.code != "DOG":
            cleaned_data["contract_kind"] = None
            cleaned_data["document_purpose"] = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        custom_data = {}
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith("custom__"):
                custom_data[field_name.replace("custom__", "", 1)] = value
        if custom_data:
            instance.custom_data = custom_data
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file"]


class ApprovalActionForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ReturnForRevisionForm(forms.Form):
    responsible = UserModelChoiceField(
        label="Ответственный за доработку",
        queryset=User.objects.filter(is_active=True).select_related("userprofile").order_by("last_name", "first_name", "username"),
        required=False,
    )
    comment = forms.CharField(
        label="Причина возврата",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class DelegateForm(forms.Form):
    delegated_to = UserModelChoiceField(
        label="Новый согласующий",
        queryset=User.objects.filter(is_active=True).select_related("userprofile").order_by("last_name", "first_name", "username"),
    )
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = DocumentComment
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Добавить комментарий"})}


class RevisionCorrectionForm(forms.Form):
    corrections = forms.CharField(
        label="Внесенные корректировки",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Опишите, какие правки внесены перед повторным согласованием"}),
    )


class ParallelRevisionCorrectionForm(forms.Form):
    def __init__(self, *args, revision_requests, **kwargs):
        super().__init__(*args, **kwargs)
        self.revision_requests = list(revision_requests)
        for revision_request in self.revision_requests:
            self.fields[f"correction_{revision_request.pk}"] = forms.CharField(
                label="Внесенные корректировки",
                widget=forms.Textarea(
                    attrs={
                        "rows": 3,
                        "placeholder": "Опишите, что исправлено по этому замечанию",
                    }
                ),
            )

    def corrections_by_request(self):
        return {
            revision_request.pk: self.cleaned_data[f"correction_{revision_request.pk}"]
            for revision_request in self.revision_requests
        }


class ApprovalTaskFilterForm(forms.Form):
    only_overdue = forms.BooleanField(label="Только просроченные", required=False)


class DocumentSearchForm(forms.Form):
    query = forms.CharField(label="Поиск", required=False)
    status = forms.ChoiceField(label="Статус", choices=[("", "Все статусы")] + Document.STATUSES, required=False)


class PasswordResetRequestForm(forms.Form):
    username = forms.CharField(
        label="Логин",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        self.user = User.objects.filter(username__iexact=username, is_active=True).first()
        return username


class PasswordResetConfirmForm(forms.Form):
    username = forms.CharField(
        label="Логин",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    code = forms.CharField(
        label="4-значный код",
        min_length=4,
        max_length=4,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        help_text="Минимум 4 символа. Только латинские буквы и цифры. Нужна хотя бы одна буква и одна цифра.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Повторите пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise ValidationError("Код должен состоять из 4 цифр.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username", "").strip()
        code = cleaned_data.get("code")
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        user = User.objects.filter(username__iexact=username, is_active=True).first()
        if username and not user:
            self.add_error("username", "Активный пользователь с таким логином не найден.")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "Пароли не совпадают.")
        if user and code:
            reset_request = (
                PasswordResetRequest.objects.filter(user=user, code=code, status=PasswordResetRequest.PENDING)
                .order_by("-created_at")
                .first()
            )
            if not reset_request or not reset_request.is_active:
                self.add_error("code", "Код неверен или срок его действия истек.")
            else:
                self.reset_request = reset_request
        if user and password1:
            try:
                validate_password(password1, user)
            except ValidationError as exc:
                self.add_error("new_password1", exc)
        self.user = user
        return cleaned_data
