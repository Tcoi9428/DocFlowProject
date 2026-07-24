from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Отправляет тестовое письмо через настроенный email backend."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Email-адрес получателя тестового письма.")

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
            raise CommandError(
                "Сейчас включен console.EmailBackend. Передайте EmailUser и EmailPassword "
                "в deployment/set-localcorp-env.ps1."
            )

        recipient = options["recipient"]
        link_url = f"{settings.DOCFLOW_BASE_URL}/"
        message = (
            "Это тестовое письмо от системы DocFlow.\n\n"
            f"Адрес приложения: {link_url}\n\n"
            "Если вы получили письмо, SMTP настроен корректно."
        )
        sent_count = send_mail(
            "Проверка почтовых уведомлений DocFlow",
            message,
            None,
            [recipient],
            fail_silently=False,
        )
        if sent_count != 1:
            raise CommandError("Почтовый сервер не подтвердил отправку тестового письма.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Тестовое письмо отправлено на {recipient} через {settings.EMAIL_HOST}:{settings.EMAIL_PORT}."
            )
        )
