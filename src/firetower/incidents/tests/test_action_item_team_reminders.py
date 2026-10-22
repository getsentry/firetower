from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from firetower.incidents.tasks.action_items import (
    MISFILED_ACTION_ITEM_REMINDER_MARKER,
    _remind_misfiled_action_item_creators,
    send_action_item_reminder,
)

LINEAR = {"TEAM_ID": "incident-team"}
ISSUE = {
    "id": "issue-1",
    "identifier": "INC-2508",
    "creator": {"id": "creator-id", "displayName": "Leander Rodrigues"},
}


@pytest.fixture
def service(settings):
    settings.PROJECT_KEY = "INC"
    settings.LINEAR = LINEAR
    service = MagicMock()
    service.get_misfiled_action_items.return_value = [ISSUE]
    service.create_comment.return_value = True
    with patch(
        "firetower.incidents.tasks.action_items.LinearService", return_value=service
    ):
        yield service


def test_mentions_creator_and_explains_move(service):
    _remind_misfiled_action_item_creators(LINEAR)

    service.get_misfiled_action_items.assert_called_once_with(
        "incident-team", MISFILED_ACTION_ITEM_REMINDER_MARKER
    )
    args, kwargs = service.create_comment.call_args
    assert args[0] == ISSUE["id"]
    assert "@[Leander Rodrigues](creator-id)" in args[1]
    assert MISFILED_ACTION_ITEM_REMINDER_MARKER in args[1]
    assert "created in the INC team" in args[1]
    assert "move it to the relevant actioning team" in args[1]
    assert "keeping it as a child" in args[1]
    assert UUID(kwargs["comment_id"]).version == 4


def test_skips_issues_with_existing_reminder_on_later_runs(service):
    service.get_misfiled_action_items.side_effect = [[ISSUE], []]

    _remind_misfiled_action_item_creators(LINEAR)
    _remind_misfiled_action_item_creators(LINEAR)

    service.create_comment.assert_called_once()


def test_comment_id_is_stable_across_retries(service):
    service.create_comment.side_effect = [TimeoutError("response lost"), True]

    _remind_misfiled_action_item_creators(LINEAR)
    _remind_misfiled_action_item_creators(LINEAR)

    calls = service.create_comment.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["comment_id"] == calls[1].kwargs["comment_id"]


def test_comment_ids_differ_between_issues(service):
    service.get_misfiled_action_items.return_value = [
        ISSUE,
        {**ISSUE, "id": "issue-2", "identifier": "INC-2509"},
    ]

    _remind_misfiled_action_item_creators(LINEAR)

    calls = service.create_comment.call_args_list
    assert calls[0].kwargs["comment_id"] != calls[1].kwargs["comment_id"]


def test_handles_missing_creator(service):
    service.get_misfiled_action_items.return_value = [{**ISSUE, "creator": None}]

    _remind_misfiled_action_item_creators(LINEAR)

    body = service.create_comment.call_args.args[1]
    assert "Hi, this action item" in body
    assert "@[" not in body


@pytest.mark.parametrize("config", [{}, {"TEAM_ID": ""}])
def test_skips_when_team_is_not_configured(service, config):
    _remind_misfiled_action_item_creators(config)

    service.get_misfiled_action_items.assert_not_called()
    service.create_comment.assert_not_called()


@pytest.mark.parametrize("failure", [None, RuntimeError("Linear unavailable")])
def test_does_not_post_when_lookup_fails(service, failure):
    if isinstance(failure, Exception):
        service.get_misfiled_action_items.side_effect = failure
    else:
        service.get_misfiled_action_items.return_value = failure

    _remind_misfiled_action_item_creators(LINEAR)

    service.create_comment.assert_not_called()


@pytest.mark.parametrize("failure", [False, RuntimeError("Linear unavailable")])
def test_continues_after_a_comment_failure(service, failure):
    service.get_misfiled_action_items.return_value = [
        ISSUE,
        {**ISSUE, "id": "issue-2", "identifier": "INC-2509"},
    ]
    service.create_comment.side_effect = [failure, True]

    _remind_misfiled_action_item_creators(LINEAR)

    assert service.create_comment.call_count == 2


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        {**ISSUE, "creator": {"id": "creator-id"}},
        {**ISSUE, "creator": {"displayName": "Leander Rodrigues"}},
    ],
)
def test_continues_after_malformed_issue_data(service, malformed):
    service.get_misfiled_action_items.return_value = [malformed, ISSUE]

    _remind_misfiled_action_item_creators(LINEAR)

    service.create_comment.assert_called_once()
    assert service.create_comment.call_args.args[0] == ISSUE["id"]


def test_initialization_failure_does_not_escape(service):
    with patch(
        "firetower.incidents.tasks.action_items.LinearService",
        side_effect=RuntimeError("initialization failed"),
    ):
        _remind_misfiled_action_item_creators(LINEAR)

    service.create_comment.assert_not_called()


def test_malformed_issue_does_not_block_slo_sweep(service, settings):
    settings.LINEAR = {**LINEAR, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY": "SLO nag"}
    service.get_misfiled_action_items.return_value = [
        {**ISSUE, "creator": {"id": "creator-id"}}
    ]
    incident = MagicMock()
    incident.action_items.filter.return_value = []
    with (
        patch("firetower.incidents.tasks.action_items.Incident") as incident_model,
        patch(
            "firetower.incidents.tasks.action_items.sync_action_items_from_linear"
        ) as sync,
    ):
        incident_model.objects.filter.return_value.exclude.return_value = [incident]

        send_action_item_reminder()

    sync.assert_called_once_with(incident)
    service.create_comment.assert_not_called()


def test_uses_configured_incident_team_key(service, settings):
    settings.PROJECT_KEY = "TESTINC"

    _remind_misfiled_action_item_creators(LINEAR)

    assert "created in the TESTINC team" in service.create_comment.call_args.args[1]


def test_cron_sweeps_even_without_slo_nag_configuration(service):
    send_action_item_reminder()

    service.create_comment.assert_called_once()
