from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        abstract = True


class Department(TimeStampedModel):
    name = models.CharField("Наименование", max_length=200, unique=True)
    code = models.CharField("Код", max_length=20, unique=True)
    manager = models.ForeignKey(
        User,
        verbose_name="Руководитель",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
    )
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(User, verbose_name="Пользователь", on_delete=models.CASCADE)
    department = models.ForeignKey(
        Department,
        verbose_name="Подразделение",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    position = models.CharField("Должность", max_length=150, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class DocumentType(TimeStampedModel):
    name = models.CharField("Наименование", max_length=150, unique=True)
    code = models.CharField("Код для номера", max_length=12, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активно", default=True)
    default_due_days = models.PositiveSmallIntegerField("Срок согласования, дней", default=3)

    class Meta:
        verbose_name = "Тип документа"
        verbose_name_plural = "Типы документов"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ContractKind(TimeStampedModel):
    name = models.CharField("Наименование", max_length=150, unique=True)
    code = models.CharField("Код", max_length=30, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Вид договора"
        verbose_name_plural = "Виды договоров"
        ordering = ["name"]

    def __str__(self):
        return self.name


class DocumentPurpose(TimeStampedModel):
    name = models.CharField("Наименование", max_length=150, unique=True)
    code = models.CharField("Код", max_length=30, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Назначение документа"
        verbose_name_plural = "Назначения документов"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomFieldDefinition(TimeStampedModel):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    FIELD_TYPES = [
        (TEXT, "Текст"),
        (NUMBER, "Число"),
        (DATE, "Дата"),
        (BOOLEAN, "Да/Нет"),
        (CHOICE, "Список"),
    ]

    document_type = models.ForeignKey(
        DocumentType,
        verbose_name="Тип документа",
        on_delete=models.CASCADE,
        related_name="custom_fields",
    )
    name = models.CharField("Название поля", max_length=120)
    key = models.SlugField("Технический ключ", max_length=80)
    field_type = models.CharField("Тип поля", max_length=20, choices=FIELD_TYPES, default=TEXT)
    is_required = models.BooleanField("Обязательное", default=False)
    choices = models.TextField(
        "Варианты для списка",
        blank=True,
        help_text="Один вариант на строку. Используется только для типа поля 'Список'.",
    )
    sort_order = models.PositiveSmallIntegerField("Порядок", default=100)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Пользовательское поле"
        verbose_name_plural = "Пользовательские поля"
        unique_together = [("document_type", "key")]
        ordering = ["document_type__name", "sort_order", "name"]

    def __str__(self):
        return f"{self.document_type.code}: {self.name}"

    def choice_list(self):
        return [line.strip() for line in self.choices.splitlines() if line.strip()]


class ApprovalRoute(TimeStampedModel):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ROUTE_TYPES = [
        (SEQUENTIAL, "Последовательный"),
        (PARALLEL, "Параллельный"),
    ]

    name = models.CharField("Наименование", max_length=200)
    document_type = models.ForeignKey(
        DocumentType,
        verbose_name="Тип документа",
        on_delete=models.CASCADE,
        related_name="approval_routes",
    )
    route_type = models.CharField("Тип маршрута", max_length=20, choices=ROUTE_TYPES, default=SEQUENTIAL)
    is_default = models.BooleanField("Маршрут по умолчанию", default=False)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Маршрут согласования"
        verbose_name_plural = "Маршруты согласования"
        ordering = ["document_type__name", "name"]

    def __str__(self):
        return self.name


class ApprovalStep(TimeStampedModel):
    route = models.ForeignKey(
        ApprovalRoute,
        verbose_name="Маршрут",
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField("Этап", max_length=150)
    approver = models.ForeignKey(
        User,
        verbose_name="Согласующий",
        on_delete=models.PROTECT,
        related_name="approval_steps",
    )
    order = models.PositiveSmallIntegerField("Порядок", default=1)
    due_days = models.PositiveSmallIntegerField("Срок, дней", default=3)

    class Meta:
        verbose_name = "Этап согласования"
        verbose_name_plural = "Этапы согласования"
        ordering = ["route", "order"]

    def __str__(self):
        return f"{self.route}: {self.order}. {self.name}"


class Document(TimeStampedModel):
    DRAFT = "draft"
    ON_APPROVAL = "on_approval"
    RETURNED = "returned"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    STATUSES = [
        (DRAFT, "Черновик"),
        (ON_APPROVAL, "На согласовании"),
        (RETURNED, "Возвращен на доработку"),
        (APPROVED, "Согласован"),
        (REJECTED, "Отклонен"),
        (IN_PROGRESS, "В работе"),
        (COMPLETED, "Исполнен"),
        (ARCHIVED, "Архив"),
    ]

    document_type = models.ForeignKey(DocumentType, verbose_name="Тип документа", on_delete=models.PROTECT)
    contract_kind = models.ForeignKey(
        ContractKind,
        verbose_name="Вид договора",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    document_purpose = models.ForeignKey(
        DocumentPurpose,
        verbose_name="Назначение документа",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    title = models.CharField("Тема", max_length=250)
    system_number = models.CharField("Системный номер", max_length=40, unique=True, blank=True)
    internal_number = models.CharField("Внутренний номер компании", max_length=80, blank=True)
    status = models.CharField("Статус", max_length=30, choices=STATUSES, default=DRAFT)
    author = models.ForeignKey(User, verbose_name="Инициатор", on_delete=models.PROTECT, related_name="documents")
    responsible = models.ForeignKey(
        User,
        verbose_name="Ответственный",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_documents",
    )
    department = models.ForeignKey(
        Department,
        verbose_name="Подразделение",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    route = models.ForeignKey(
        ApprovalRoute,
        verbose_name="Маршрут согласования",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    registration_date = models.DateField("Дата регистрации", default=timezone.localdate)
    due_date = models.DateField("Срок исполнения/согласования", null=True, blank=True)
    amount = models.DecimalField("Сумма", max_digits=14, decimal_places=2, null=True, blank=True)
    counterparty = models.CharField("Контрагент", max_length=250, blank=True)
    summary = models.TextField("Краткое содержание", blank=True)
    custom_data = models.JSONField("Пользовательские поля", default=dict, blank=True)
    is_deleted = models.BooleanField("Помечен на удаление", default=False)
    archived_at = models.DateTimeField("Дата архивации", null=True, blank=True)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ["-created_at"]
        permissions = [
            ("view_all_documents", "Может видеть все документы"),
            ("soft_delete_document", "Может помечать документы на удаление"),
        ]

    def __str__(self):
        return f"{self.system_number or 'Новый'} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.system_number and self.document_type_id:
            self.system_number = self.generate_system_number()
        super().save(*args, **kwargs)

    def generate_system_number(self):
        year = timezone.localdate().year
        prefix = f"{self.document_type.code}-{year}-"
        last_number = (
            Document.objects.filter(system_number__startswith=prefix)
            .aggregate(max_number=Max("system_number"))
            .get("max_number")
        )
        if not last_number:
            next_number = 1
        else:
            next_number = int(last_number.rsplit("-", 1)[-1]) + 1
        return f"{prefix}{next_number:05d}"

    def can_be_seen_by(self, user):
        if user.is_superuser or user.has_perm("documents.view_all_documents"):
            return True
        if self.author_id == user.id or self.responsible_id == user.id:
            return True
        return self.approval_tasks.filter(approver=user).exists()


class DocumentApprover(TimeStampedModel):
    document = models.ForeignKey(
        Document,
        verbose_name="Документ",
        on_delete=models.CASCADE,
        related_name="configured_approvers",
    )
    approver = models.ForeignKey(
        User,
        verbose_name="Согласующий",
        on_delete=models.PROTECT,
        related_name="configured_document_approvals",
    )
    name = models.CharField("Этап согласования", max_length=150, blank=True)
    order = models.PositiveSmallIntegerField("Порядок", default=1)
    due_days = models.PositiveSmallIntegerField("Срок, дней", default=3)

    class Meta:
        verbose_name = "Согласующий документа"
        verbose_name_plural = "Согласующие документа"
        ordering = ["document", "order", "id"]

    def __str__(self):
        return f"{self.document.system_number}: {self.order}. {self.approver}"


def document_upload_path(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"documents/{instance.document.id}/{uuid4().hex}{ext}"


class Attachment(TimeStampedModel):
    document = models.ForeignKey(
        Document,
        verbose_name="Документ",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField("Файл", upload_to=document_upload_path)
    original_name = models.CharField("Исходное имя файла", max_length=255)
    size = models.PositiveBigIntegerField("Размер, байт", default=0)
    content_hash = models.CharField("Hash файла", max_length=64, blank=True)
    uploaded_by = models.ForeignKey(User, verbose_name="Кто загрузил", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
        ordering = ["-created_at"]

    def clean(self):
        if self.file and self.file.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError(f"Размер файла больше {settings.MAX_UPLOAD_SIZE // 1024 // 1024} МБ.")

    def __str__(self):
        return self.original_name


class ApprovalTask(TimeStampedModel):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    DELEGATED = "delegated"
    STATUSES = [
        (PENDING, "Ожидает"),
        (APPROVED, "Согласовано"),
        (REJECTED, "Отклонено"),
        (RETURNED, "Возвращено"),
        (DELEGATED, "Делегировано"),
    ]

    document = models.ForeignKey(
        Document,
        verbose_name="Документ",
        on_delete=models.CASCADE,
        related_name="approval_tasks",
    )
    step = models.ForeignKey(ApprovalStep, verbose_name="Этап", on_delete=models.SET_NULL, null=True, blank=True)
    configured_approver = models.ForeignKey(
        DocumentApprover,
        verbose_name="Согласующий документа",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approver = models.ForeignKey(User, verbose_name="Согласующий", on_delete=models.PROTECT, related_name="approval_tasks")
    status = models.CharField("Статус", max_length=20, choices=STATUSES, default=PENDING)
    due_date = models.DateField("Срок", null=True, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    completed_at = models.DateTimeField("Дата выполнения", null=True, blank=True)
    delegated_to = models.ForeignKey(
        User,
        verbose_name="Делегировано кому",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegated_approval_tasks",
    )

    class Meta:
        verbose_name = "Задача согласования"
        verbose_name_plural = "Задачи согласования"
        ordering = ["due_date", "created_at"]

    def __str__(self):
        return f"{self.document.system_number}: {self.approver}"

    @property
    def is_overdue(self):
        return self.status == self.PENDING and self.due_date and self.due_date < timezone.localdate()


class DocumentComment(TimeStampedModel):
    document = models.ForeignKey(Document, verbose_name="Документ", on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, verbose_name="Автор", on_delete=models.PROTECT)
    text = models.TextField("Комментарий")

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.created_at:%d.%m.%Y %H:%M}"


class AuditLog(TimeStampedModel):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"
    DELEGATE = "delegate"
    ARCHIVE = "archive"
    ACTIONS = [
        (CREATE, "Создание"),
        (UPDATE, "Изменение"),
        (DELETE, "Удаление/пометка"),
        (VIEW, "Просмотр"),
        (APPROVE, "Согласование"),
        (REJECT, "Отклонение"),
        (RETURN, "Возврат"),
        (DELEGATE, "Делегирование"),
        (ARCHIVE, "Архивация"),
    ]

    user = models.ForeignKey(User, verbose_name="Пользователь", on_delete=models.SET_NULL, null=True, blank=True)
    document = models.ForeignKey(Document, verbose_name="Документ", on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField("Действие", max_length=30, choices=ACTIONS)
    message = models.TextField("Описание")
    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)

    class Meta:
        verbose_name = "Журнал действий"
        verbose_name_plural = "Журнал действий"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} - {self.get_action_display()}"
