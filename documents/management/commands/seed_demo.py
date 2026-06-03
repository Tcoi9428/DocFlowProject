from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand

from documents.models import (
    ApprovalRoute,
    ApprovalStep,
    ContractKind,
    CustomFieldDefinition,
    Department,
    DocumentPurpose,
    DocumentType,
)


class Command(BaseCommand):
    help = "Создает стартовые справочники, роли, пользователей и маршруты для прототипа."

    def handle(self, *args, **options):
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True, "email": "admin@company.local"},
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password("admin")
        admin_user.save()

        director = self._user("director", "Директор", "company.local")
        manager = self._user("manager", "Руководитель отдела", "company.local")
        accountant = self._user("accountant", "Бухгалтер", "company.local")
        initiator = self._user("user", "Инициатор", "company.local")

        self._groups()

        departments = [
            ("ADM", "Администрация", director),
            ("FIN", "Бухгалтерия", accountant),
            ("PRD", "Производственный отдел", manager),
            ("RMD", "Ремонтная служба", manager),
        ]
        for code, name, manager_user in departments:
            Department.objects.get_or_create(code=code, defaults={"name": name, "manager": manager_user})

        doc_types = [
            ("Договоры", "DOG", "Договоры с контрагентами, подрядчиками и заказчиками."),
            ("Служебные записки", "SZ", "Внутренние обращения и обоснования."),
            ("Приказы", "PRK", "Распорядительные документы компании."),
            ("Внутренние документы", "VND", "Инструкции, методики, положения."),
            ("Счета/УПД и заявки на оплату", "PAY", "Согласование оплаты работ, услуг и поставок."),
        ]
        created_types = {}
        for name, code, description in doc_types:
            document_type, _ = DocumentType.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": description, "default_due_days": 3},
            )
            created_types[code] = document_type

        self._custom_fields(created_types)
        self._contract_reference_data()
        self._routes(created_types, director, manager, accountant)

        self.stdout.write(self.style.SUCCESS("Demo data created. Logins: admin/admin, user/user, manager/manager."))

    def _user(self, username, first_name, email_domain):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "email": f"{username}@{email_domain}", "is_staff": False},
        )
        if created:
            user.set_password(username)
            user.save()
        return user

    def _groups(self):
        group_names = ["Администратор документооборота", "Руководитель", "Инициатор", "Согласующий", "Бухгалтерия"]
        for name in group_names:
            group, _ = Group.objects.get_or_create(name=name)
            if name == "Администратор документооборота":
                permissions = Permission.objects.filter(
                    content_type__app_label="documents",
                    codename__in=["view_all_documents", "soft_delete_document"],
                )
                group.permissions.set(permissions)

    def _custom_fields(self, doc_types):
        fields = {
            "DOG": [
                ("Номер договора контрагента", "counterparty_contract_no", CustomFieldDefinition.TEXT, False, ""),
                ("Дата окончания договора", "contract_end_date", CustomFieldDefinition.DATE, False, ""),
            ],
            "SZ": [
                ("Основание", "reason", CustomFieldDefinition.TEXT, False, ""),
                ("Требуется исполнение", "requires_execution", CustomFieldDefinition.BOOLEAN, False, ""),
            ],
            "PRK": [
                ("Вид приказа", "order_kind", CustomFieldDefinition.CHOICE, True, "По основной деятельности\nПо персоналу\nПо производству"),
            ],
            "VND": [
                ("Версия документа", "version", CustomFieldDefinition.TEXT, False, ""),
                ("Область применения", "scope", CustomFieldDefinition.TEXT, False, ""),
            ],
            "PAY": [
                ("Номер счета/УПД", "invoice_number", CustomFieldDefinition.TEXT, True, ""),
                ("Дата счета/УПД", "invoice_date", CustomFieldDefinition.DATE, True, ""),
            ],
        }
        for code, definitions in fields.items():
            for order, (name, key, field_type, required, choices) in enumerate(definitions, start=1):
                CustomFieldDefinition.objects.get_or_create(
                    document_type=doc_types[code],
                    key=key,
                    defaults={
                        "name": name,
                        "field_type": field_type,
                        "is_required": required,
                        "choices": choices,
                        "sort_order": order,
                    },
                )

    def _contract_reference_data(self):
        contract_kinds = [
            ("SERVICE", "Договор оказания услуг"),
            ("SUPPLY", "Договор поставки"),
            ("WORKS", "Договор подряда"),
            ("LEASE", "Договор аренды"),
            ("NDA", "Соглашение о конфиденциальности"),
        ]
        for code, name in contract_kinds:
            ContractKind.objects.get_or_create(code=code, defaults={"name": name})

        purposes = [
            ("REGISTRATION", "Регистрация нового документа"),
            ("APPROVAL", "Согласование условий"),
            ("PAYMENT", "Основание для оплаты"),
            ("EXTENSION", "Продление срока действия"),
            ("ARCHIVE", "Архивное хранение"),
        ]
        for code, name in purposes:
            DocumentPurpose.objects.get_or_create(code=code, defaults={"name": name})

    def _routes(self, doc_types, director, manager, accountant):
        routes = {
            "DOG": [("Проверка руководителем", manager), ("Утверждение директором", director)],
            "SZ": [("Согласование руководителем", manager)],
            "PRK": [("Проверка руководителем", manager), ("Утверждение директором", director)],
            "VND": [("Проверка руководителем", manager), ("Утверждение директором", director)],
            "PAY": [("Проверка бухгалтерией", accountant), ("Утверждение директором", director)],
        }
        for code, steps in routes.items():
            route, _ = ApprovalRoute.objects.get_or_create(
                document_type=doc_types[code],
                name=f"Типовой маршрут: {doc_types[code].name}",
                defaults={"is_default": True, "route_type": ApprovalRoute.SEQUENTIAL},
            )
            for order, (name, approver) in enumerate(steps, start=1):
                ApprovalStep.objects.get_or_create(
                    route=route,
                    order=order,
                    defaults={"name": name, "approver": approver, "due_days": 3},
                )
