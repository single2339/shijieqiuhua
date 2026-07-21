from __future__ import annotations

from backend.task_queue import CollectionJobQueue


def test_collection_job_survives_new_queue_instance_and_can_be_claimed(tmp_path):
    first = CollectionJobQueue(tmp_path)
    job_id = first.enqueue(hours=6)

    second = CollectionJobQueue(tmp_path)
    job = second.claim_next()

    assert job is not None
    assert job["job_id"] == job_id
    assert job["status"] == "running"
    assert job["attempts"] == 1

    second.complete(job_id)
    assert second.get(job_id)["status"] == "completed"
