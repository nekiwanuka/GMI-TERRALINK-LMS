"""Run a daily scheduler for workflow consistency reconciliation."""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import BaseCommand, call_command
from django_apscheduler.jobstores import DjangoJobStore, register_events


def run_daily_reconciliation(fix_enabled: bool):
    args = ["reconcile_workflow_consistency"]
    if fix_enabled:
        args.append("--fix")
    call_command(*args)


class Command(BaseCommand):
    help = "Starts a blocking scheduler to run reconcile_workflow_consistency daily."

    def handle(self, *args, **options):
        schedule = getattr(
            settings,
            "RECONCILIATION_SCHEDULE",
            {"hour": 2, "minute": 0, "fix": True},
        )
        hour = int(schedule.get("hour", 2))
        minute = int(schedule.get("minute", 0))
        fix_enabled = bool(schedule.get("fix", True))

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            run_daily_reconciliation,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="workflow_reconciliation_daily",
            max_instances=1,
            replace_existing=True,
            kwargs={"fix_enabled": fix_enabled},
        )
        register_events(scheduler)

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduler started. Daily reconciliation at {hour:02d}:{minute:02d} (fix={fix_enabled})."
            )
        )
        self.stdout.write(
            "Press Ctrl+C to stop. Keep this process running in your service manager."
        )

        try:
            scheduler.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Scheduler stopped."))
