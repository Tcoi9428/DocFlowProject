from django.contrib.auth.models import User
from django.test import TestCase

from .forms import DocumentForm
from .models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalTask,
    ContractKind,
    Document,
    DocumentApprover,
    DocumentPurpose,
    Notification,
    DocumentType,
)
from .services import approve_task, start_approval


class DocumentWorkflowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="test")
        self.manager = User.objects.create_user(username="manager", password="test")
        self.director = User.objects.create_user(username="director", password="test")
        self.document_type = DocumentType.objects.create(name="Договоры", code="DOG")
        self.memo_type = DocumentType.objects.create(name="Служебные записки", code="SZ")
        self.order_type = DocumentType.objects.create(name="Приказы", code="PRK")
        ContractKind.objects.create(name="Договор поставки", code="SUPPLY")
        DocumentPurpose.objects.create(name="Основание для оплаты", code="PAYMENT")
        self.route = ApprovalRoute.objects.create(
            name="Типовой маршрут",
            document_type=self.document_type,
            is_default=True,
            route_type=ApprovalRoute.SEQUENTIAL,
        )
        ApprovalStep.objects.create(route=self.route, name="Руководитель", approver=self.manager, order=1)
        ApprovalStep.objects.create(route=self.route, name="Директор", approver=self.director, order=2)

    def test_system_number_is_generated_by_document_type_and_year(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Поставка запчастей",
            author=self.author,
        )

        self.assertTrue(document.system_number.startswith("DOG-"))
        self.assertTrue(document.system_number.endswith("00001"))

    def test_sequential_approval_creates_next_task_and_approves_document(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Ремонт оборудования",
            author=self.author,
            route=self.route,
        )

        start_approval(document, self.author)
        first_task = ApprovalTask.objects.get(document=document, approver=self.manager)
        approve_task(first_task, self.manager, "OK")

        self.assertTrue(ApprovalTask.objects.filter(document=document, approver=self.director).exists())

        second_task = ApprovalTask.objects.get(document=document, approver=self.director)
        approve_task(second_task, self.director, "OK")
        document.refresh_from_db()

        self.assertEqual(document.status, Document.APPROVED)

    def test_create_form_keeps_selected_document_type_after_refresh(self):
        self.client.force_login(self.author)

        response = self.client.get(f"/documents/new/?document_type={self.document_type.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.document_type.id}" selected')
        self.assertContains(response, f'name="document_type" value="{self.document_type.id}"')
        self.assertContains(response, "addEventListener")
        self.assertNotContains(response, "window.location")
        self.assertNotContains(response, "Обновить поля")

    def test_contract_fields_are_visible_only_for_contract_documents(self):
        contract_form = DocumentForm(initial={"document_type": self.document_type.id})
        memo_form = DocumentForm(initial={"document_type": self.memo_type.id})

        self.assertIn("contract_kind", contract_form.fields)
        self.assertIn("document_purpose", contract_form.fields)
        self.assertNotIn("contract_kind", memo_form.fields)
        self.assertNotIn("document_purpose", memo_form.fields)

    def test_order_form_hides_counterparty_and_amount(self):
        order_form = DocumentForm(initial={"document_type": self.order_type.id})

        self.assertNotIn("counterparty", order_form.fields)
        self.assertNotIn("amount", order_form.fields)

    def test_custom_document_approvers_drive_sequential_approval(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Договор по пользовательскому маршруту",
            author=self.author,
            route=self.route,
        )
        DocumentApprover.objects.create(document=document, approver=self.manager, name="Первый этап", order=1)
        DocumentApprover.objects.create(document=document, approver=self.director, name="Второй этап", order=2)

        start_approval(document, self.author)
        first_task = ApprovalTask.objects.get(document=document, approver=self.manager)

        approve_task(first_task, self.manager, "OK")

        self.assertTrue(ApprovalTask.objects.filter(document=document, approver=self.director).exists())

    def test_start_approval_creates_notification_for_approver(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Договор с уведомлением",
            author=self.author,
            route=self.route,
        )
        DocumentApprover.objects.create(document=document, approver=self.manager, name="Первый этап", order=1)

        start_approval(document, self.author)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.manager,
                document=document,
                notification_type=Notification.APPROVAL_REQUIRED,
                is_read=False,
            ).exists()
        )

# Create your tests here.
