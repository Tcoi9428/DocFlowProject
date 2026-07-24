from django.core.management.base import BaseCommand

from documents.services import process_approval_reminders


class Command(BaseCommand):
    help = "Создает уведомления по задачам, до срока которых остался один день или меньше."

    def handle(self, *args, **options):
        count = process_approval_reminders()
        self.stdout.write(f"Создано напоминаний: {count}.")
