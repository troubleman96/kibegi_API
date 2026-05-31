from django.core.management.base import BaseCommand

from apps.schedule.services import ScheduleSmsService
from apps.core.utils.sms import AfricasTalkingSmsClient  # re-exported for test patching


class Command(BaseCommand):
    help = "Send due schedule reminders as SMS messages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional maximum number of due reminders to process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate due reminders without sending SMS or consuming credits.",
        )

    def handle(self, *args, **options):
        client = AfricasTalkingSmsClient()
        results = ScheduleSmsService.dispatch_due_reminders(
            client=client,
            limit=options["limit"],
            dry_run=options["dry_run"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {results['due']} reminders: {results['sent']} sent, {results['failed']} failed, {results['skipped']} skipped."
            )
        )
