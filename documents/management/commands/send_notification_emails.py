from django.core.management.base import BaseCommand

from documents.services import process_email_queue


class Command(BaseCommand):
    help = "Повторно отправляет ожидающие и ранее не отправленные email-уведомления."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Максимальное количество писем за один запуск.")

    def handle(self, *args, **options):
        sent, failed = process_email_queue(limit=max(options["limit"], 1))
        self.stdout.write(f"Отправлено: {sent}. Ошибок: {failed}.")
