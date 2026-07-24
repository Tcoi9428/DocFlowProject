from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .forms import DocumentForm
from .models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalTask,
    ContractKind,
    Document,
    DocumentApprover,
    DocumentComment,
    DocumentPurpose,
    EmailDelivery,
    Notification,
    DocumentType,
    PasswordResetRequest,
)
from .services import (
    approve_task,
    deliver_email,
    process_approval_reminders,
    return_for_revision,
    start_approval,
)


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

    @override_settings(
        DOCFLOW_EMAIL_SEND_IMMEDIATELY=False,
        DOCFLOW_BASE_URL="http://10.110.53.17:8010",
    )
    def test_approval_notification_queues_email_with_document_link(self):
        self.manager.email = "manager@example.com"
        self.manager.save(update_fields=["email"])
        document = Document.objects.create(
            document_type=self.document_type,
            title="Договор с email-уведомлением",
            author=self.author,
            route=self.route,
        )

        start_approval(document, self.author)

        delivery = EmailDelivery.objects.get(notification__document=document)
        self.assertEqual(delivery.recipient_email, "manager@example.com")
        self.assertEqual(delivery.status, EmailDelivery.PENDING)
        self.assertEqual(delivery.link_url, f"http://10.110.53.17:8010/documents/{document.pk}/")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DOCFLOW_EMAIL_SEND_IMMEDIATELY=False,
        DOCFLOW_BASE_URL="http://10.110.53.17:8010",
    )
    def test_email_delivery_is_sent_and_marked_as_sent(self):
        self.manager.email = "manager@example.com"
        self.manager.save(update_fields=["email"])
        document = Document.objects.create(
            document_type=self.document_type,
            title="Проверка отправки email",
            author=self.author,
            route=self.route,
        )
        start_approval(document, self.author)
        delivery = EmailDelivery.objects.get(notification__document=document)

        result = deliver_email(delivery.pk)

        delivery.refresh_from_db()
        self.assertTrue(result)
        self.assertEqual(delivery.status, EmailDelivery.SENT)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"/documents/{document.pk}/", mail.outbox[0].body)

    @override_settings(
        DOCFLOW_EMAIL_SEND_IMMEDIATELY=False,
        DOCFLOW_BASE_URL="http://10.110.53.17:8010",
    )
    def test_approval_reminder_is_created_once_for_current_due_date(self):
        self.manager.email = "manager@example.com"
        self.manager.save(update_fields=["email"])
        document = Document.objects.create(
            document_type=self.document_type,
            title="Документ с близким сроком",
            author=self.author,
            route=self.route,
        )
        start_approval(document, self.author)
        task = ApprovalTask.objects.get(document=document, approver=self.manager)
        task.due_date = timezone.localdate() + timedelta(days=1)
        task.save(update_fields=["due_date", "updated_at"])

        first_count = process_approval_reminders()
        second_count = process_approval_reminders()

        task.refresh_from_db()
        reminder = Notification.objects.get(
            recipient=self.manager,
            document=document,
            notification_type=Notification.APPROVAL_REMINDER,
        )
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(task.reminder_due_date, task.due_date)
        self.assertTrue(hasattr(reminder, "email_delivery"))
        self.assertIn(f"/documents/{document.pk}/", reminder.email_delivery.link_url)

    @override_settings(DOCFLOW_EMAIL_SEND_IMMEDIATELY=False)
    def test_responsible_is_notified_when_all_approvers_finish(self):
        responsible = User.objects.create_user(
            username="responsible",
            password="test",
            email="responsible@example.com",
        )
        document = Document.objects.create(
            document_type=self.document_type,
            title="Документ для ответственного",
            author=self.author,
            responsible=responsible,
            route=self.route,
        )
        start_approval(document, self.author)
        approve_task(ApprovalTask.objects.get(document=document, approver=self.manager), self.manager)
        approve_task(ApprovalTask.objects.get(document=document, approver=self.director), self.director)

        notification = Notification.objects.get(
            recipient=responsible,
            document=document,
            title__icontains="согласован всеми участниками",
        )
        self.assertTrue(hasattr(notification, "email_delivery"))

    @override_settings(DOCFLOW_EMAIL_SEND_IMMEDIATELY=False)
    def test_responsible_receives_revision_email_with_actor_and_link(self):
        self.director.email = "director@example.com"
        self.director.save(update_fields=["email"])
        document = Document.objects.create(
            document_type=self.document_type,
            title="Документ на доработку",
            author=self.author,
            responsible=self.director,
            route=self.route,
        )
        start_approval(document, self.author)
        task = ApprovalTask.objects.get(document=document, approver=self.manager)

        return_for_revision(task, self.manager, comment="Уточнить условия")

        notification = Notification.objects.get(
            recipient=self.director,
            document=document,
            title__icontains="отправлен на доработку",
        )
        self.assertIn("Уточнить условия", notification.message)
        self.assertTrue(hasattr(notification, "email_delivery"))
        self.assertIn(f"/documents/{document.pk}/", notification.email_delivery.link_url)

    def test_return_for_revision_keeps_document_responsible_and_saves_comment(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Договор на доработку",
            author=self.author,
            responsible=self.director,
            route=self.route,
        )

        start_approval(document, self.author)
        task = ApprovalTask.objects.get(document=document, approver=self.manager)
        return_for_revision(task, self.manager, comment="Исправить условия оплаты")
        document.refresh_from_db()

        self.assertEqual(document.status, Document.RETURNED)
        self.assertEqual(document.responsible, self.director)
        self.assertEqual(document.revision_requested_by, self.manager)
        self.assertEqual(document.revision_comment, "Исправить условия оплаты")
        self.assertTrue(
            DocumentComment.objects.filter(
                document=document,
                author=self.manager,
                text__icontains="Исправить условия оплаты",
            ).exists()
        )

    def test_resubmit_after_revision_increments_version_and_restarts_route(self):
        document = Document.objects.create(
            document_type=self.document_type,
            title="Повторное согласование",
            author=self.author,
            responsible=self.director,
            route=self.route,
        )

        start_approval(document, self.author)
        task = ApprovalTask.objects.get(document=document, approver=self.manager)
        return_for_revision(task, self.manager, comment="Нужна новая версия")

        self.client.force_login(self.director)
        response = self.client.post(
            f"/documents/{document.pk}/resubmit/",
            {"corrections": "Обновлен файл договора и условия оплаты."},
        )
        document.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(document.version, 2)
        self.assertEqual(document.status, Document.ON_APPROVAL)
        self.assertTrue(
            ApprovalTask.objects.filter(
                document=document,
                approver=self.manager,
                status=ApprovalTask.PENDING,
            ).exists()
        )
        self.assertTrue(
            DocumentComment.objects.filter(
                document=document,
                author=self.director,
                text__icontains="Обновлен файл договора",
            ).exists()
        )

    def test_password_reset_request_notifies_admin_with_code(self):
        admin = User.objects.create_user(username="admin2", password="admin2", is_staff=True)
        response = self.client.post("/password-reset/", {"username": self.author.username})
        reset_request = PasswordResetRequest.objects.get(user=self.author)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(reset_request.code), 4)
        self.assertTrue(reset_request.code.isdigit())
        self.assertTrue(
            Notification.objects.filter(
                recipient=admin,
                notification_type=Notification.PASSWORD_RESET,
                message__icontains=reset_request.code,
                link_url=f"/password-reset/admin/{reset_request.pk}/",
            ).exists()
        )

    def test_password_reset_confirm_changes_password_with_admin_code(self):
        reset_request = PasswordResetRequest.create_for_user(self.author)

        response = self.client.post(
            "/password-reset/confirm/",
            {
                "username": self.author.username,
                "code": reset_request.code,
                "new_password1": "pass1",
                "new_password2": "pass1",
            },
        )
        self.author.refresh_from_db()
        reset_request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.author.check_password("pass1"))
        self.assertEqual(reset_request.status, PasswordResetRequest.USED)

    def test_password_reset_confirm_rejects_password_without_digits(self):
        reset_request = PasswordResetRequest.create_for_user(self.author)

        response = self.client.post(
            "/password-reset/confirm/",
            {
                "username": self.author.username,
                "code": reset_request.code,
                "new_password1": "pass",
                "new_password2": "pass",
            },
        )
        self.author.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.author.check_password("pass"))

    @override_settings(DOCFLOW_MAINTENANCE_MODE=True)
    def test_maintenance_mode_returns_503(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "300")
        self.assertContains(response, "Технические работы", status_code=503)

    @override_settings(DEBUG=False, DOCFLOW_MAINTENANCE_MODE=False)
    def test_unknown_page_uses_custom_404(self):
        response = self.client.get("/definitely-missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Страница не найдена", status_code=404)

# Create your tests here.
