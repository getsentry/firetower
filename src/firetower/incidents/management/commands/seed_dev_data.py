"""
Management command to seed realistic incident data for local development.

Usage:
    python manage.py seed_dev_data
    python manage.py seed_dev_data --clear   # wipe existing incidents first
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus, Tag, TagType

# ---------------------------------------------------------------------------
# Seed data definition
# ---------------------------------------------------------------------------

# (title, description, impact, severity, status, downtime_minutes, regions, date_offset_days)
# date_offset_days: days before today the incident was created (positive = further in past)
# downtime_minutes: None = not recorded (active/mitigated incidents and some edge cases)

INCIDENTS: list[tuple] = [
    # ── Active (5) ─────────────────────────────────────────────────────────
    (
        "Elevated error rates in API gateway",
        "The API gateway is returning elevated 5xx errors for requests originating from the de region. Root cause under investigation.",
        "Customers in de experiencing degraded API responses. Estimated 15% of requests failing.",
        IncidentSeverity.P1, IncidentStatus.ACTIVE, None,
        ["de", "us"], 0,
    ),
    (
        "Database read replica lag",
        "Read replicas in the s4s2 cluster are falling behind the primary by 45+ seconds, causing stale reads for reporting queries.",
        "Dashboard and reporting features are showing data that is up to 45 seconds delayed for s4s2 customers.",
        IncidentSeverity.P2, IncidentStatus.ACTIVE, None,
        ["s4s2"], 0,
    ),
    (
        "Intermittent auth failures for goldman-sachs",
        "OAuth token validation is intermittently failing for goldman-sachs users. Appears to affect ~5% of login attempts.",
        "Some goldman-sachs users unable to log in. Workaround: retry login.",
        IncidentSeverity.P2, IncidentStatus.ACTIVE, None,
        ["goldman-sachs"], 1,
    ),
    (
        "CDN cache poisoning causing stale assets",
        "A misconfigured cache rule is causing some static assets to be served stale across multiple regions.",
        "Customers may see outdated UI on first load. Hard refresh resolves it.",
        IncidentSeverity.P3, IncidentStatus.ACTIVE, None,
        ["us", "de", "ly"], 1,
    ),
    (
        "Webhook delivery delays",
        "Webhook delivery queue is backing up. Events are being delivered with 10-20 minute delays across all regions.",
        "Customers relying on real-time webhook delivery are seeing delayed events. No data loss.",
        IncidentSeverity.P3, IncidentStatus.ACTIVE, None,
        ["us", "de", "disney", "geico", "goldman-sachs", "control", "s4s2", "ly"], 2,
    ),
    # ── Mitigated (3) ──────────────────────────────────────────────────────
    (
        "Memory pressure on worker nodes",
        "Worker nodes in the control cluster experienced OOM events due to a memory leak in the job processor. Nodes were recycled and monitoring increased.",
        "Background jobs were delayed by up to 30 minutes for control region customers.",
        IncidentSeverity.P2, IncidentStatus.MITIGATED, None,
        ["control"], 3,
    ),
    (
        "Elevated latency on Payments gateway",
        "Payment processing latency spiked to 8s p99 (up from 200ms baseline) due to a slow downstream provider. Traffic has been shifted to secondary provider.",
        "Checkout and payment flows experienced slowdowns for disney and geico customers.",
        IncidentSeverity.P1, IncidentStatus.MITIGATED, None,
        ["disney", "geico"], 4,
    ),
    (
        "Certificate renewal failure",
        "An automated certificate renewal failed silently, causing a cert to expire for an internal service endpoint. Manually renewed.",
        "Internal service-to-service calls were failing for ~12 minutes. No customer-facing impact.",
        IncidentSeverity.P3, IncidentStatus.MITIGATED, None,
        ["us"], 5,
    ),
    # ── Done – February 2026 (15) ───────────────────────────────────────────
    (
        "Full outage: us region database primary failover",
        "The primary PostgreSQL node for the us region became unresponsive due to disk I/O saturation. Automatic failover to replica completed but took longer than expected.",
        "All us region customers experienced complete service unavailability for 47 minutes.",
        IncidentSeverity.P0, IncidentStatus.DONE, 47,
        ["us"], 7,
    ),
    (
        "Auth service crash loop in de",
        "A bad deployment of the auth service caused a crash loop due to an incompatible config change. Rollback resolved the issue.",
        "de customers were unable to log in for 22 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 22,
        ["de"], 8,
    ),
    (
        "Search index rebuild causing query timeouts",
        "A scheduled search index rebuild consumed excessive CPU, degrading query performance across s4s2 and ly.",
        "Search features were unavailable or extremely slow for 35 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 35,
        ["s4s2", "ly"], 8,
    ),
    (
        "goldman-sachs data pipeline stall",
        "An upstream schema change in the data pipeline caused ingestion to halt for goldman-sachs. Required a manual schema migration and restart.",
        "goldman-sachs reporting data was 4 hours stale. No data loss.",
        IncidentSeverity.P2, IncidentStatus.DONE, 240,
        ["goldman-sachs"], 9,
    ),
    (
        "control region: Redis cluster split-brain",
        "Network partition caused a Redis cluster split-brain event. Sentinel failed to elect a new primary correctly for ~18 minutes.",
        "Session data and caching unavailable for control region customers for 18 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 18,
        ["control"], 10,
    ),
    (
        "geico API rate limit misconfiguration",
        "A config deploy incorrectly set the geico API rate limits 10x too low, causing legitimate requests to be rejected.",
        "geico customers experienced HTTP 429 errors for API calls for 28 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 28,
        ["geico"], 11,
    ),
    (
        "disney SSO provider outage",
        "Disney's SSO provider experienced an outage, preventing disney customers from authenticating via SSO.",
        "disney SSO users were unable to log in for 55 minutes. Users with password auth were unaffected.",
        IncidentSeverity.P1, IncidentStatus.DONE, 55,
        ["disney"], 11,
    ),
    (
        "Kubernetes node group scaling failure",
        "Auto-scaling failed to provision new nodes in time during a traffic surge, causing pod scheduling failures.",
        "Intermittent 503 errors for us and de customers over 12 minutes during peak hours.",
        IncidentSeverity.P2, IncidentStatus.DONE, 12,
        ["us", "de"], 12,
    ),
    (
        "ly region: object storage misconfiguration",
        "A misconfigured bucket policy blocked the application from reading user-uploaded files in the ly region.",
        "File uploads were accepted but could not be retrieved for ly customers for 40 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 40,
        ["ly"], 13,
    ),
    (
        "s4s2 deployment rollout failure",
        "A canary deployment to s4s2 introduced a nil pointer dereference that was not caught in staging. Required rollback.",
        "s4s2 API requests were returning 500 errors for 15 minutes until rollback completed.",
        IncidentSeverity.P1, IncidentStatus.DONE, 15,
        ["s4s2"], 14,
    ),
    (
        "Cross-region replication lag spike",
        "Replication lag between us and de spiked to 8 minutes due to a large batch write, causing inconsistent reads.",
        "Data inconsistency for customers with cross-region presence for approximately 20 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 20,
        ["us", "de"], 14,
    ),
    (
        "goldman-sachs: VPN tunnel instability",
        "The dedicated VPN tunnel for goldman-sachs experienced repeated drops due to an ISP issue on their end.",
        "goldman-sachs users on the VPN integration experienced intermittent connectivity issues for 65 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 65,
        ["goldman-sachs"], 15,
    ),
    (
        "control region: message queue consumer crash",
        "Message queue consumers crashed due to a malformed message with a missing required field. Dead-letter queue filled up.",
        "Async processing (emails, notifications) was paused for control customers for 25 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 25,
        ["control"], 16,
    ),
    (
        "Full outage: geico and disney – config service unavailable",
        "A bad config deploy to the config service rendered it unable to serve configs, causing dependent services to fail-closed.",
        "geico and disney experienced complete service outage for 30 minutes.",
        IncidentSeverity.P0, IncidentStatus.DONE, 30,
        ["geico", "disney"], 17,
    ),
    (
        "ly region: DNS propagation delay post-migration",
        "After migrating ly to a new IP range, DNS TTL was not lowered in advance, causing prolonged propagation delays.",
        "Some ly customers experienced connection failures for up to 90 minutes depending on their DNS resolver.",
        IncidentSeverity.P1, IncidentStatus.DONE, 90,
        ["ly"], 18,
    ),
    (
        "de region: CPU throttling due to noisy neighbor",
        "A large batch job on a shared node caused CPU throttling for adjacent workloads in the de region.",
        "de API p99 latency degraded to 4s for 18 minutes.",
        IncidentSeverity.P3, IncidentStatus.DONE, 18,
        ["de"], 19,
    ),
    # ── Done – January 2026 (20) ────────────────────────────────────────────
    (
        "us region: complete database failure",
        "Primary and all replicas became unavailable simultaneously due to a cascading failure triggered by a storage controller fault.",
        "Total us region outage for 72 minutes. All us customers were unable to use the service.",
        IncidentSeverity.P0, IncidentStatus.DONE, 72,
        ["us"], 28,
    ),
    (
        "s4s2: load balancer config regression",
        "A Terraform apply incorrectly updated the s4s2 load balancer health check path, causing healthy instances to be marked down.",
        "s4s2 service was unavailable for 33 minutes before the config was reverted.",
        IncidentSeverity.P1, IncidentStatus.DONE, 33,
        ["s4s2"], 29,
    ),
    (
        "goldman-sachs: encryption key rotation failure",
        "Automated encryption key rotation failed midway, leaving some records encrypted with the old key and others with the new, causing decryption errors.",
        "goldman-sachs experienced errors accessing encrypted records for 45 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 45,
        ["goldman-sachs"], 30,
    ),
    (
        "control region: full disk on log aggregator",
        "The log aggregator disk filled to 100%, causing log shipping to block and eventually causing the application process to hang.",
        "control region was completely unavailable for 20 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 20,
        ["control"], 30,
    ),
    (
        "de region: DDoS-like traffic spike",
        "A misconfigured client was sending requests in a tight loop, generating 50x normal traffic and overloading the de API cluster.",
        "de customers experienced severe degradation for 38 minutes while the offending client was identified and blocked.",
        IncidentSeverity.P1, IncidentStatus.DONE, 38,
        ["de"], 31,
    ),
    (
        "disney: feature flag service outage",
        "The feature flag service became unavailable, causing all flags to default to 'off', disabling several key product features for disney.",
        "Multiple features (A/B tests, gradual rollouts) were disabled for disney customers for 22 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 22,
        ["disney"], 32,
    ),
    (
        "geico: webhook signing key mismatch",
        "A key rotation deployed without coordinating with geico caused all inbound webhooks from geico to fail signature validation.",
        "geico's inbound integration was broken for 4 hours until the key was re-synced.",
        IncidentSeverity.P2, IncidentStatus.DONE, 240,
        ["geico"], 33,
    ),
    (
        "ly region: cold start latency storm",
        "A region-wide deployment caused all ly instances to restart simultaneously, creating a cold start storm and overloading dependencies.",
        "ly experienced high latency and partial outage for 16 minutes post-deployment.",
        IncidentSeverity.P2, IncidentStatus.DONE, 16,
        ["ly"], 33,
    ),
    (
        "Multi-region: TLS cert expiry for wildcard domain",
        "A wildcard TLS certificate expired without renewal due to a missed alert. Affected all regions using the *.internal domain.",
        "Internal service mesh communications were failing across all regions for 28 minutes until cert was manually renewed.",
        IncidentSeverity.P1, IncidentStatus.DONE, 28,
        ["us", "de", "s4s2", "control", "ly"], 34,
    ),
    (
        "goldman-sachs: read timeout on reporting API",
        "A missing index on a reporting query caused full table scans at scale, triggering read timeouts for goldman-sachs.",
        "goldman-sachs reporting API was timing out for 50 minutes. Read-only data; no writes affected.",
        IncidentSeverity.P2, IncidentStatus.DONE, 50,
        ["goldman-sachs"], 35,
    ),
    (
        "control region: scheduler double-firing jobs",
        "A scheduler bug caused jobs to fire twice, resulting in duplicate processing and data integrity warnings.",
        "Duplicate side effects (emails, billing events) triggered for control customers for 35 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 35,
        ["control"], 36,
    ),
    (
        "us region: S3 ListObjects throttling",
        "An overly aggressive S3 lifecycle policy scan caused AWS to throttle ListObjects calls, degrading file-related features.",
        "File listing and search features were severely degraded for us customers for 42 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 42,
        ["us"], 36,
    ),
    (
        "disney and geico: shared auth service OOM",
        "The shared authentication service for disney and geico ran out of memory due to a session cache leak. Pod was restarted.",
        "disney and geico customers were logged out and unable to re-authenticate for 8 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 8,
        ["disney", "geico"], 37,
    ),
    (
        "de region: misconfigured network ACL blocking egress",
        "A network ACL change blocked egress to a third-party email provider, causing email delivery failures.",
        "Transactional emails (password resets, notifications) were not delivered for de customers for 3 hours.",
        IncidentSeverity.P2, IncidentStatus.DONE, 180,
        ["de"], 38,
    ),
    (
        "s4s2: database connection pool exhaustion",
        "A connection leak in a new service version exhausted the database connection pool over several hours.",
        "s4s2 customers experienced intermittent database errors for 55 minutes before the service was rolled back.",
        IncidentSeverity.P2, IncidentStatus.DONE, 55,
        ["s4s2"], 39,
    ),
    (
        "ly region: upstream CDN provider outage",
        "The CDN provider used for the ly region experienced an outage in their edge nodes, causing asset delivery failures.",
        "ly customers saw broken images and assets for 48 minutes. APIs were unaffected.",
        IncidentSeverity.P2, IncidentStatus.DONE, 48,
        ["ly"], 40,
    ),
    (
        "control: gRPC service mesh certificate rotation outage",
        "Automated cert rotation for the service mesh issued certificates with wrong SANs, breaking all gRPC calls in the control region.",
        "All internal gRPC communication in control was broken for 25 minutes.",
        IncidentSeverity.P1, IncidentStatus.DONE, 25,
        ["control"], 41,
    ),
    (
        "Full outage: goldman-sachs – dedicated cluster upgrade failure",
        "An in-place cluster upgrade failed halfway, leaving the goldman-sachs dedicated cluster in an inconsistent state.",
        "goldman-sachs was completely unavailable for 95 minutes while the cluster was rebuilt.",
        IncidentSeverity.P0, IncidentStatus.DONE, 95,
        ["goldman-sachs"], 42,
    ),
    (
        "us region: NTP drift causing JWT validation failures",
        "Clock drift on several us nodes exceeded the JWT expiry tolerance, causing valid tokens to be rejected.",
        "us customers were being logged out unexpectedly and could not re-authenticate for 10 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 10,
        ["us"], 43,
    ),
    (
        "geico: rate limiter false positives after config push",
        "A rate limiter config push used incorrect customer IDs, causing geico's account to be throttled at 1 req/s.",
        "geico API integrations were severely throttled for 30 minutes.",
        IncidentSeverity.P2, IncidentStatus.DONE, 30,
        ["geico"], 44,
    ),
]


class Command(BaseCommand):
    help = "Seed the database with realistic incident data for local development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing incidents before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count, _ = Incident.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing incidents"))

        user = User.objects.first()
        if not user:
            self.stderr.write("No users found. Create a superuser first.")
            return

        tags_by_name = {
            t.name: t for t in Tag.objects.filter(type=TagType.AFFECTED_AREA)
        }

        now = timezone.now()
        created = 0

        for (
            title, description, impact, severity, status,
            downtime_minutes, region_names, days_ago,
        ) in INCIDENTS:
            # Use update_fields bypass to set auto_now_add created_at
            incident = Incident(
                title=title,
                description=description,
                impact=impact,
                severity=severity,
                status=status,
                total_downtime=downtime_minutes * 60 if downtime_minutes is not None else None,
                is_private=False,
                captain=user,
            )
            # Bypass full_clean's auto_now_add restriction by saving then updating
            incident.save()

            target_date = now - timedelta(days=days_ago)
            Incident.objects.filter(pk=incident.pk).update(created_at=target_date)

            for name in region_names:
                tag = tags_by_name.get(name)
                if tag:
                    incident.affected_area_tags.add(tag)

            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {created} incidents successfully.")
        )
