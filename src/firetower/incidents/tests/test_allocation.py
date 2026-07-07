from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured

from firetower.incidents.allocation import (
    LEGACY_PLACEHOLDER_TITLE,
    PLACEHOLDER_TITLE,
    AllocatedIdentity,
    LinearUnavailable,
    _create_and_adopt_placeholder,
    _looks_like_placeholder,
    adopt_on_create_enabled,
    allocate_incident_identity,
)
from firetower.incidents.hooks import (
    _populate_linear_parent,
    create_linear_parent_issue,
)
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentCounter,
    IncidentSeverity,
)
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.integrations.services.linear import LinearError


def _identifier(n: int) -> str:
    return f"{django_settings.PROJECT_KEY}-{n}"


def _placeholder(n: int, *, title: str = PLACEHOLDER_TITLE) -> dict:
    return {
        "id": f"uuid-{n}",
        "identifier": _identifier(n),
        "title": title,
        "url": f"https://linear.app/issue/{_identifier(n)}",
        "state_type": "backlog",
    }


def _set_counter(next_id: int) -> None:
    IncidentCounter.objects.update_or_create(pk=1, defaults={"next_id": next_id})


def _make_linear(
    get_issue_map: dict[str, dict | None] | None = None,
    *,
    get_issue_side_effect=None,
    created_issue: dict | None = None,
) -> MagicMock:
    linear = MagicMock()
    if get_issue_side_effect is not None:
        linear.get_issue.side_effect = get_issue_side_effect
    else:
        mapping = get_issue_map or {}

        def _get_issue(identifier, *, raise_on_error=False):
            return mapping.get(identifier)

        linear.get_issue.side_effect = _get_issue
    linear.create_issue.return_value = created_issue
    return linear


@pytest.fixture
def adopt_enabled(settings):
    settings.LINEAR = {
        "SYNC_IDENTIFIERS": True,
        "INCIDENT_ADOPT_ON_CREATE": True,
        "TEAM_ID": "team-1",
        "PROJECT_ID": "proj-1",
    }
    return settings


def _patch_linear(linear: MagicMock):
    return patch(
        "firetower.incidents.allocation.LinearService.for_allocation",
        return_value=linear,
    )


class TestAdoptOnCreateEnabled:
    def test_disabled_when_linear_unset(self, settings):
        settings.LINEAR = None
        assert adopt_on_create_enabled() is False

    def test_disabled_without_sync_identifiers(self, settings):
        settings.LINEAR = {"INCIDENT_ADOPT_ON_CREATE": True}
        assert adopt_on_create_enabled() is False

    def test_disabled_without_adopt_flag(self, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": True}
        assert adopt_on_create_enabled() is False

    def test_enabled_when_both_set(self, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": True, "INCIDENT_ADOPT_ON_CREATE": True}
        assert adopt_on_create_enabled() is True


class TestLooksLikePlaceholder:
    def test_accepts_current_title(self):
        assert _looks_like_placeholder({"title": PLACEHOLDER_TITLE}) is True

    def test_accepts_legacy_title(self):
        assert _looks_like_placeholder({"title": LEGACY_PLACEHOLDER_TITLE}) is True

    def test_rejects_other_title(self):
        assert _looks_like_placeholder({"title": "Real incident"}) is False


@pytest.mark.django_db
class TestAllocateFlagOff:
    def test_returns_counter_id_and_empty_linear(self, settings):
        settings.LINEAR = None
        _set_counter(2100)

        identity = allocate_incident_identity()

        assert identity == AllocatedIdentity(2100, "", "")
        assert IncidentCounter.objects.get(pk=1).next_id == 2101


@pytest.mark.django_db
class TestAllocateClaim:
    def test_claims_clean_matching_placeholder(self, adopt_enabled):
        _set_counter(2334)
        linear = _make_linear({_identifier(2334): _placeholder(2334)})

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity == AllocatedIdentity(
            2334, "uuid-2334", f"https://linear.app/issue/{_identifier(2334)}"
        )
        assert IncidentCounter.objects.get(pk=1).next_id == 2335
        linear.create_issue.assert_not_called()

    def test_claims_legacy_titled_placeholder(self, adopt_enabled):
        _set_counter(2334)
        linear = _make_linear(
            {_identifier(2334): _placeholder(2334, title=LEGACY_PLACEHOLDER_TITLE)}
        )

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2334


@pytest.mark.django_db
class TestAllocateSkips:
    def test_alias_skip_then_claim(self, adopt_enabled):
        _set_counter(2334)
        aliased = {
            "id": "uuid-moved",
            "identifier": "PRODENG-1404",
            "title": "Moved issue",
            "url": "https://linear.app/issue/PRODENG-1404",
            "state_type": "started",
        }
        linear = _make_linear(
            {_identifier(2334): aliased, _identifier(2335): _placeholder(2335)}
        )

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2335
        assert IncidentCounter.objects.get(pk=1).next_id == 2336

    def test_used_id_skip_then_claim(self, adopt_enabled):
        _set_counter(2400)
        Incident.objects.create(id=2400, title="Existing", severity=IncidentSeverity.P2)
        linear = _make_linear(
            {
                _identifier(2400): _placeholder(2400),
                _identifier(2401): _placeholder(2401),
            }
        )

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2401
        assert IncidentCounter.objects.get(pk=1).next_id == 2402

    def test_stray_non_placeholder_skip_then_claim(self, adopt_enabled):
        _set_counter(2350)
        stray = _placeholder(2350, title="A real incident that lives at this id")
        linear = _make_linear(
            {_identifier(2350): stray, _identifier(2351): _placeholder(2351)}
        )

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2351
        assert IncidentCounter.objects.get(pk=1).next_id == 2352


@pytest.mark.django_db
class TestAllocateCreateAdopt:
    def test_not_found_creates_and_adopts_equal_id(self, adopt_enabled):
        _set_counter(2353)
        created = {
            "id": "uuid-new",
            "identifier": _identifier(2353),
            "url": "https://linear.app/issue/new",
        }
        linear = _make_linear({}, created_issue=created)

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity == AllocatedIdentity(
            2353, "uuid-new", "https://linear.app/issue/new"
        )
        assert IncidentCounter.objects.get(pk=1).next_id == 2354
        linear.create_issue.assert_called_once_with(
            PLACEHOLDER_TITLE, "", "team-1", "proj-1"
        )

    def test_not_found_creates_and_adopts_higher_id(self, adopt_enabled):
        _set_counter(2353)
        created = {
            "id": "uuid-new",
            "identifier": _identifier(2360),
            "url": "https://linear.app/issue/new",
        }
        linear = _make_linear({}, created_issue=created)

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2360
        assert IncidentCounter.objects.get(pk=1).next_id == 2361

    def test_skip_budget_valve_falls_through_to_create(self, adopt_enabled):
        _set_counter(2400)
        aliased = {
            "id": "uuid-moved",
            "identifier": "PRODENG-9",
            "title": "Moved",
            "url": "https://linear.app/issue/PRODENG-9",
            "state_type": "started",
        }
        created = {
            "id": "uuid-new",
            "identifier": _identifier(2500),
            "url": "https://linear.app/issue/new",
        }
        # Every identifier resolves to an aliased issue, exhausting the budget.
        linear = _make_linear(
            get_issue_side_effect=lambda identifier, *, raise_on_error=False: aliased,
            created_issue=created,
        )

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2500
        assert IncidentCounter.objects.get(pk=1).next_id == 2501
        linear.create_issue.assert_called_once()

    def test_full_landmine_walk_then_adopt(self, adopt_enabled):
        _set_counter(2334)
        aliased_map: dict[str, dict | None] = {}
        for n in range(2334, 2340):
            aliased_map[_identifier(n)] = {
                "id": f"uuid-moved-{n}",
                "identifier": f"PRODENG-{n}",
                "title": "Moved issue",
                "url": f"https://linear.app/issue/PRODENG-{n}",
                "state_type": "started",
            }
        # INC-2340 is genuinely absent -> create+adopt whatever Linear mints.
        created = {
            "id": "uuid-new",
            "identifier": _identifier(2353),
            "url": "https://linear.app/issue/new",
        }
        linear = _make_linear(aliased_map, created_issue=created)

        with _patch_linear(linear):
            identity = allocate_incident_identity()

        assert identity.inc_id == 2353
        assert IncidentCounter.objects.get(pk=1).next_id == 2354


@pytest.mark.django_db
class TestAllocateUnavailable:
    def test_get_issue_error_raises_and_leaves_counter(self, adopt_enabled):
        _set_counter(2334)
        linear = _make_linear(get_issue_side_effect=LinearError("boom"))

        with _patch_linear(linear), pytest.raises(LinearUnavailable):
            allocate_incident_identity()

        assert IncidentCounter.objects.get(pk=1).next_id == 2334

    def test_create_failure_raises_and_leaves_counter(self, adopt_enabled):
        _set_counter(2353)
        linear = _make_linear({}, created_issue=None)

        with _patch_linear(linear), pytest.raises(LinearUnavailable):
            allocate_incident_identity()

        assert IncidentCounter.objects.get(pk=1).next_id == 2353

    def test_minted_below_counter_raises(self, adopt_enabled):
        _set_counter(2360)
        created = {
            "id": "uuid-new",
            "identifier": _identifier(2355),
            "url": "https://linear.app/issue/new",
        }
        linear = _make_linear({}, created_issue=created)

        with _patch_linear(linear), pytest.raises(LinearUnavailable):
            allocate_incident_identity()

        assert IncidentCounter.objects.get(pk=1).next_id == 2360

    def test_non_project_identifier_raises(self, adopt_enabled):
        _set_counter(2353)
        created = {
            "id": "uuid-new",
            "identifier": "RENAMED-5",
            "url": "https://linear.app/issue/new",
        }
        linear = _make_linear({}, created_issue=created)

        with _patch_linear(linear), pytest.raises(LinearUnavailable):
            allocate_incident_identity()

        assert IncidentCounter.objects.get(pk=1).next_id == 2353


@pytest.mark.django_db
class TestAllocateAtomicTripwire:
    def test_asserts_when_run_inside_enclosing_transaction(
        self, adopt_enabled, monkeypatch
    ):
        # Drop the pytest marker so the tripwire is armed; the test itself runs
        # inside pytest's wrapping transaction, standing in for an enclosing
        # atomic() in production.
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        _set_counter(2334)
        linear = _make_linear({_identifier(2334): _placeholder(2334)})

        with _patch_linear(linear), pytest.raises(AssertionError):
            allocate_incident_identity()


@pytest.mark.django_db
class TestAllocateSerialization:
    def test_consecutive_allocations_get_distinct_ids(self, adopt_enabled):
        _set_counter(2334)
        linear = _make_linear(
            {
                _identifier(2334): _placeholder(2334),
                _identifier(2335): _placeholder(2335),
            }
        )

        with _patch_linear(linear):
            first = allocate_incident_identity()
            second = allocate_incident_identity()

        assert first.inc_id == 2334
        assert second.inc_id == 2335
        assert first.inc_id != second.inc_id
        assert IncidentCounter.objects.get(pk=1).next_id == 2336


@pytest.mark.django_db
class TestCreateAndAdoptPlaceholderNoSideEffects:
    def test_no_db_or_counter_writes(self, adopt_enabled):
        _set_counter(2400)
        linear = _make_linear(
            {},
            created_issue={
                "id": "uuid-new",
                "identifier": _identifier(2400),
                "url": "https://linear.app/issue/new",
            },
        )

        before = Incident.objects.count()
        minted, uuid, url = _create_and_adopt_placeholder(linear, "team-1", "proj-1")

        assert (minted, uuid) == (2400, "uuid-new")
        assert Incident.objects.count() == before
        assert IncidentCounter.objects.get(pk=1).next_id == 2400


@pytest.mark.django_db
class TestSaveGuard:
    def test_raises_when_adopt_enabled_and_id_missing(self, adopt_enabled):
        incident = Incident(title="Test", severity=IncidentSeverity.P1)
        with pytest.raises(ImproperlyConfigured):
            incident.save()

    def test_uses_counter_when_adopt_disabled(self, settings):
        settings.LINEAR = None
        _set_counter(2200)
        incident = Incident(title="Test", severity=IncidentSeverity.P1)
        incident.save()
        assert incident.id == 2200

    def test_explicit_id_bypasses_guard_when_adopt_enabled(self, adopt_enabled):
        incident = Incident(id=2500, title="Test", severity=IncidentSeverity.P1)
        incident.save()
        assert incident.id == 2500


@pytest.mark.django_db
class TestSerializerAllocation:
    def _serializer_data(self) -> dict:
        return {
            "title": "Serializer Incident",
            "severity": "P2",
            "captain": "cap@example.com",
            "reporter": "rep@example.com",
        }

    @patch("firetower.incidents.serializers.allocate_incident_identity")
    def test_injects_id_uuid_and_stashes_identity(self, mock_allocate, adopt_enabled):
        identity = AllocatedIdentity(2500, "uuid-abc", "https://linear.app/issue/x")
        mock_allocate.return_value = identity

        serializer = IncidentWriteSerializer(
            data=self._serializer_data(), context={"skip_hooks": True}
        )
        assert serializer.is_valid(), serializer.errors
        incident = serializer.save()

        assert incident.id == 2500
        assert incident.linear_parent_issue_id == "uuid-abc"
        assert incident._allocated_identity is identity

    @patch("firetower.incidents.serializers.allocate_incident_identity")
    def test_flag_off_identity_leaves_no_linear_parent(self, mock_allocate, settings):
        settings.LINEAR = None
        mock_allocate.return_value = AllocatedIdentity(2600, "", "")

        serializer = IncidentWriteSerializer(
            data=self._serializer_data(), context={"skip_hooks": True}
        )
        assert serializer.is_valid(), serializer.errors
        incident = serializer.save()

        assert incident.id == 2600
        assert incident.linear_parent_issue_id is None

    @patch(
        "firetower.incidents.serializers.allocate_incident_identity",
        side_effect=LinearUnavailable,
    )
    def test_linear_unavailable_propagates(self, mock_allocate, adopt_enabled):
        serializer = IncidentWriteSerializer(
            data=self._serializer_data(), context={"skip_hooks": True}
        )
        assert serializer.is_valid(), serializer.errors
        with pytest.raises(LinearUnavailable):
            serializer.save()


@pytest.mark.django_db
class TestPopulateLinearParent:
    def _incident(self, settings) -> Incident:
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = Incident.objects.create(
            title="Populate me", severity=IncidentSeverity.P2
        )
        incident.linear_parent_issue_id = "uuid-verified"
        return incident

    @patch("firetower.incidents.hooks._slack_service")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_updates_by_uuid_never_by_identifier(
        self, mock_get_linear, mock_slack, settings
    ):
        incident = self._incident(settings)
        linear = mock_get_linear.return_value
        linear.get_workflow_states.return_value = {"started": "state-started"}
        linear.update_issue.return_value = True

        _populate_linear_parent(
            incident, "https://linear.app/issue/x", channel_id="C123"
        )

        linear.get_issue.assert_not_called()
        assert linear.update_issue.call_args[0][0] == "uuid-verified"
        assert linear.update_issue.call_args[1]["state_id"] == "state-started"
        linear.create_attachment.assert_called_once()
        assert linear.create_attachment.call_args[0][0] == "uuid-verified"
        mock_slack.add_bookmark.assert_called_once_with(
            "C123", "Linear Issue", "https://linear.app/issue/x"
        )

    @patch("firetower.incidents.hooks._slack_service")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_idempotent_external_link(self, mock_get_linear, mock_slack, settings):
        incident = self._incident(settings)
        mock_get_linear.return_value.get_workflow_states.return_value = {}

        _populate_linear_parent(incident, "https://linear.app/issue/x")
        _populate_linear_parent(incident, "https://linear.app/issue/y")

        links = ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.LINEAR
        )
        assert links.count() == 1
        assert links.first().url == "https://linear.app/issue/y"

    @patch("firetower.incidents.hooks._slack_service")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_non_fatal_when_update_raises(self, mock_get_linear, mock_slack, settings):
        incident = self._incident(settings)
        linear = mock_get_linear.return_value
        linear.get_workflow_states.return_value = {}
        linear.update_issue.side_effect = RuntimeError("boom")

        _populate_linear_parent(incident, "https://linear.app/issue/x")

        link = ExternalLink.objects.get(incident=incident, type=ExternalLinkType.LINEAR)
        assert link.url == "https://linear.app/issue/x"

    @patch("firetower.incidents.hooks._slack_service")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_no_bookmark_without_channel(self, mock_get_linear, mock_slack, settings):
        incident = self._incident(settings)
        mock_get_linear.return_value.get_workflow_states.return_value = {}

        _populate_linear_parent(incident, "https://linear.app/issue/x")

        mock_slack.add_bookmark.assert_not_called()


@pytest.mark.django_db
class TestCreateLinearParentIssueAdoptPath:
    def _incident(self) -> Incident:
        incident = Incident.objects.create(
            id=2500, title="Adopt me", severity=IncidentSeverity.P2
        )
        incident.linear_parent_issue_id = "uuid-verified"
        return incident

    @patch("firetower.incidents.hooks._populate_linear_parent")
    def test_uses_stashed_identity_url(self, mock_populate, adopt_enabled):
        incident = self._incident()
        incident._allocated_identity = AllocatedIdentity(
            2500, "uuid-verified", "https://linear.app/issue/x"
        )

        create_linear_parent_issue(incident, channel_id="C1")

        mock_populate.assert_called_once_with(
            incident, "https://linear.app/issue/x", channel_id="C1"
        )

    @patch("firetower.incidents.hooks._populate_linear_parent")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_falls_back_to_get_issue_for_url(
        self, mock_get_linear, mock_populate, adopt_enabled
    ):
        incident = self._incident()
        mock_get_linear.return_value.get_issue.return_value = {
            "url": "https://linear.app/issue/fallback"
        }

        create_linear_parent_issue(incident, channel_id="C1")

        mock_get_linear.return_value.get_issue.assert_called_once_with("uuid-verified")
        mock_populate.assert_called_once_with(
            incident, "https://linear.app/issue/fallback", channel_id="C1"
        )

    @patch("firetower.incidents.hooks._populate_linear_parent")
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_legacy_path_when_no_parent_id(
        self, mock_get_linear, mock_populate, adopt_enabled
    ):
        mock_get_linear.return_value.get_issue.return_value = None
        mock_get_linear.return_value.create_issue.return_value = None
        incident = Incident.objects.create(
            id=2501, title="No parent", severity=IncidentSeverity.P2
        )

        create_linear_parent_issue(incident)

        mock_populate.assert_not_called()
