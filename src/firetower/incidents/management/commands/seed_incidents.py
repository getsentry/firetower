from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)


class Command(BaseCommand):
    help = "Seed database with sample incidents for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing incidents before seeding",
        )

    def handle(self, *args, **options):
        # Check if incidents already exist
        existing_count = Incident.objects.count()

        if existing_count > 0 and not options["clear"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Database already has {existing_count} incidents!"
                )
            )
            self.stdout.write("Run with --clear to delete existing data:")
            self.stdout.write("  python manage.py seed_incidents --clear")
            return

        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            ExternalLink.objects.all().delete()
            Incident.objects.all().delete()
            Tag.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS("✓ Cleared all incidents, tags, and links\n")
            )
        self.stdout.write("Creating test users...")

        # Create test users
        alice = User.objects.get_or_create(
            username="alice@example.com",
            defaults={
                "email": "alice@example.com",
                "first_name": "Alice",
                "last_name": "Anderson",
            },
        )[0]

        bob = User.objects.get_or_create(
            username="bob@example.com",
            defaults={
                "email": "bob@example.com",
                "first_name": "Bob",
                "last_name": "Builder",
            },
        )[0]

        charlie = User.objects.get_or_create(
            username="charlie@example.com",
            defaults={
                "email": "charlie@example.com",
                "first_name": "Charlie",
                "last_name": "Chen",
            },
        )[0]

        self.stdout.write("Creating tags...")

        # Create tags
        api_tag = Tag.objects.get_or_create(name="API", type=TagType.AFFECTED_AREA)[0]
        database_tag = Tag.objects.get_or_create(
            name="Database", type=TagType.AFFECTED_AREA
        )[0]
        auth_tag = Tag.objects.get_or_create(
            name="Authentication", type=TagType.AFFECTED_AREA
        )[0]
        frontend_tag = Tag.objects.get_or_create(
            name="Frontend", type=TagType.AFFECTED_AREA
        )[0]

        config_cause = Tag.objects.get_or_create(
            name="Configuration Error", type=TagType.ROOT_CAUSE
        )[0]
        memory_cause = Tag.objects.get_or_create(
            name="Memory Leak", type=TagType.ROOT_CAUSE
        )[0]
        deployment_cause = Tag.objects.get_or_create(
            name="Bad Deployment", type=TagType.ROOT_CAUSE
        )[0]

        self.stdout.write("Creating incidents...")

        # 1. Active P0 - Critical outage
        inc1 = Incident.objects.create(
            title="Complete Service Outage - Database Connection Failed",
            description="All services are down. Database connections are failing with timeout errors.",
            impact="100% of users unable to access the platform. Revenue impact estimated at $50k/hour.",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P0,
            captain=alice,
            reporter=bob,
            is_private=False,
        )
        inc1.affected_area_tags.add(database_tag, api_tag)
        inc1.root_cause_tags.add(config_cause)
        inc1.participants.add(alice, bob, charlie)

        ExternalLink.objects.create(
            incident=inc1,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C123456789",
        )
        ExternalLink.objects.create(
            incident=inc1,
            type=ExternalLinkType.DATADOG,
            url="https://app.datadoghq.com/dashboard/abc-123",
        )

        # 2. Active P1 - Major issue
        inc2 = Incident.objects.create(
            title="Authentication Service Degraded Performance",
            description="Login times increased from 200ms to 5s. Some users timing out.",
            impact="30% of users experiencing slow logins, 5% unable to login.",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=bob,
            reporter=charlie,
            is_private=False,
        )
        inc2.affected_area_tags.add(auth_tag, api_tag)
        inc2.root_cause_tags.add(memory_cause)
        inc2.participants.add(bob, charlie)

        ExternalLink.objects.create(
            incident=inc2,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C987654321",
        )

        # 3. Mitigated P1
        inc3 = Incident.objects.create(
            title="API Rate Limiting Causing 429 Errors",
            description="Third-party API rate limits exceeded, causing cascading failures.",
            impact="Mobile app users seeing error messages. Web users unaffected.",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P1,
            captain=alice,
            reporter=alice,
            is_private=False,
        )
        inc3.affected_area_tags.add(api_tag)
        inc3.root_cause_tags.add(config_cause)
        inc3.participants.add(alice)

        ExternalLink.objects.create(
            incident=inc3,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C111222333",
        )
        ExternalLink.objects.create(
            incident=inc3,
            type=ExternalLinkType.PAGERDUTY,
            url="https://example.pagerduty.com/incidents/P123",
        )

        # 4. Postmortem P2
        inc4 = Incident.objects.create(
            title="Frontend Bundle Size Causing Slow Load Times",
            description="Users on slow connections experiencing 10+ second page loads.",
            impact="User complaints increased 40%. Bounce rate up 15%.",
            status=IncidentStatus.POSTMORTEM,
            severity=IncidentSeverity.P2,
            captain=charlie,
            reporter=bob,
            is_private=False,
        )
        inc4.affected_area_tags.add(frontend_tag)
        inc4.root_cause_tags.add(deployment_cause)
        inc4.participants.add(charlie, bob)

        ExternalLink.objects.create(
            incident=inc4,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C444555666",
        )
        ExternalLink.objects.create(
            incident=inc4,
            type=ExternalLinkType.NOTION,
            url="https://notion.so/Postmortem-Frontend-Bundle-123abc",
        )

        # 5. Actions Pending P2
        inc5 = Incident.objects.create(
            title="Database Query Performance Degradation",
            description="Certain queries taking 3x longer than baseline. No immediate user impact.",
            impact="Admin dashboard slow. Background jobs taking longer.",
            status=IncidentStatus.ACTIONS_PENDING,
            severity=IncidentSeverity.P2,
            captain=alice,
            reporter=charlie,
            is_private=False,
        )
        inc5.affected_area_tags.add(database_tag)
        inc5.root_cause_tags.add(config_cause)
        inc5.participants.add(alice, charlie)

        ExternalLink.objects.create(
            incident=inc5,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C777888999",
        )

        # 6. Done P3
        inc6 = Incident.objects.create(
            title="Minor CSS Bug in Profile Page",
            description="Avatar images not rendering correctly on mobile Safari.",
            impact="Visual issue only, no functionality impact.",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P3,
            captain=bob,
            reporter=bob,
            is_private=False,
        )
        inc6.affected_area_tags.add(frontend_tag)
        inc6.participants.add(bob)

        # 7. Private incident (for testing privacy)
        inc7 = Incident.objects.create(
            title="Security Vulnerability - PRIVATE",
            description="Potential security issue under investigation.",
            impact="No user impact yet. Under embargo.",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=alice,
            reporter=alice,
            is_private=True,
        )
        inc7.affected_area_tags.add(api_tag, auth_tag)
        inc7.participants.add(alice)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully created {Incident.objects.count()} incidents!"
            )
        )
        self.stdout.write(f"- {alice.get_full_name()} (alice@example.com)")
        self.stdout.write(f"- {bob.get_full_name()} (bob@example.com)")
        self.stdout.write(f"- {charlie.get_full_name()} (charlie@example.com)")
        self.stdout.write("\nIncidents created:")

        for inc in Incident.objects.all().order_by("-id"):
            privacy = " [PRIVATE]" if inc.is_private else ""
            self.stdout.write(
                f"  {inc.incident_number} - {inc.get_severity_display()} - "
                f"{inc.get_status_display()} - {inc.title}{privacy}"
            )
