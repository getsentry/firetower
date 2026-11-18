from math import ceil

from django.conf import settings


def test_worker_pool_and_prefetch_are_bounded():
    cluster = settings.Q_CLUSTER

    assert cluster["workers"] == 2
    assert cluster["queue_limit"] == cluster["workers"]
    assert cluster["bulk"] == 1


def test_retry_lease_covers_queued_tasks_and_execution():
    """The pusher leases a batch before blocking on a full local queue."""
    cluster = settings.Q_CLUSTER
    claimed_tasks = cluster["workers"] + cluster["queue_limit"] + cluster["bulk"]
    execution_waves = ceil(claimed_tasks / cluster["workers"])
    acknowledgement_margin = 60

    assert (
        cluster["retry"]
        >= execution_waves * cluster["timeout"] + acknowledgement_margin
    )
