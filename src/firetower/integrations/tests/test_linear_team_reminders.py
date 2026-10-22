from unittest.mock import patch

import pytest

from firetower.integrations.services.linear import LinearService


@pytest.fixture
def service(settings):
    settings.LINEAR = {"API_KEY": "test"}
    return LinearService()


def page(issues, has_next=False, cursor=None):
    return {
        "issues": {
            "nodes": issues,
            "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        }
    }


def test_filters_by_child_team_parent_team_number_and_existing_comments(service):
    with patch.object(service, "_graphql", return_value=page([])) as graphql:
        assert service.get_misfiled_action_items("team-id", "reminder-marker") == []

    query, variables = graphql.call_args.args
    assert variables == {
        "filter": {
            "team": {"id": {"eq": "team-id"}},
            "number": {"gte": 2000},
            "parent": {"team": {"id": {"eq": "team-id"}}},
            "comments": {"every": {"body": {"notContains": "reminder-marker"}}},
        },
        "after": None,
    }
    assert "includeArchived: true" in query
    assert "creator {" in query
    assert "displayName" in query


def test_paginates_all_candidates_before_posting(service):
    first = {"id": "issue-1", "creator": None}
    second = {"id": "issue-2", "creator": {"id": "user-1", "displayName": "Name"}}
    with patch.object(
        service,
        "_graphql",
        side_effect=[page([first], True, "cursor-1"), page([second])],
    ) as graphql:
        assert service.get_misfiled_action_items("team-id", "marker") == [first, second]

    assert graphql.call_args_list[1].args[1]["after"] == "cursor-1"


@pytest.mark.parametrize("response", [None, {}, {"issues": None}])
def test_returns_none_when_query_fails(service, response):
    with patch.object(service, "_graphql", return_value=response):
        assert service.get_misfiled_action_items("team-id", "marker") is None


def test_does_not_return_partial_results_on_failure(service):
    with patch.object(
        service,
        "_graphql",
        side_effect=[page([{"id": "issue-1"}], True, "cursor-1"), None],
    ):
        assert service.get_misfiled_action_items("team-id", "marker") is None


@pytest.mark.parametrize("cursor", [None, "cursor-1"])
def test_fails_closed_when_pagination_cannot_advance(service, cursor):
    with patch.object(
        service,
        "_graphql",
        side_effect=[page([], True, "cursor-1"), page([], True, cursor)],
    ):
        assert service.get_misfiled_action_items("team-id", "marker") is None


def test_fails_closed_at_page_limit(service):
    with patch.object(
        service,
        "_graphql",
        side_effect=[page([], True, f"cursor-{i}") for i in range(25)],
    ) as graphql:
        assert service.get_misfiled_action_items("team-id", "marker") is None

    assert graphql.call_count == 25


@pytest.mark.parametrize("comment_id", [None, "stable-comment-id"])
def test_passes_optional_comment_id_without_retrying_mutation(service, comment_id):
    with patch.object(
        service, "_graphql", return_value={"commentCreate": {"success": True}}
    ) as graphql:
        assert service.create_comment("issue-1", "body", comment_id=comment_id)

    expected_input = {"issueId": "issue-1", "body": "body"}
    if comment_id is not None:
        expected_input["id"] = comment_id
    assert graphql.call_args.args[1] == {"input": expected_input}
    assert graphql.call_args.kwargs == {"retryable": False}
