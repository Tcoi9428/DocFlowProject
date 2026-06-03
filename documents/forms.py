from django import forms
from django.contrib.auth.models import User

from .models import (
    ApprovalRoute,
    ApprovalTask,
    Attachment,
    ContractKind,
    CustomFieldDefinition,
    Document,
    DocumentComment,
    DocumentPurpose,
    DocumentType,
)


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
        }

    def __init__(self, *args, **kwargs):
        self.custom_field_definitions = kwargs.pop("custom_field_definitions", None)
        super().__init__(*args, **kwargs)
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
        if selected_document_type and selected_document_type.code in {"DOG", "SZ"}:
            self.fields["summary"].label = "Примечание"
            self.fields["amount"].required = False
            self.fields.pop("amount", None)
        if selected_document_type and selected_document_type.code == "SZ":
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
    responsible = forms.ModelChoiceField(
        label="Ответственный за доработку",
        queryset=User.objects.filter(is_active=True),
        required=False,
    )
    comment = forms.CharField(
        label="Причина возврата",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class DelegateForm(forms.Form):
    delegated_to = forms.ModelChoiceField(
        label="Новый согласующий",
        queryset=User.objects.filter(is_active=True),
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


class ApprovalTaskFilterForm(forms.Form):
    only_overdue = forms.BooleanField(label="Только просроченные", required=False)


class DocumentSearchForm(forms.Form):
    query = forms.CharField(label="Поиск", required=False)
    status = forms.ChoiceField(label="Статус", choices=[("", "Все статусы")] + Document.STATUSES, required=False)
