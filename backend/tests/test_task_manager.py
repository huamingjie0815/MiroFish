"""
Task manager regression tests.
"""

from datetime import datetime, timedelta

from app.models.task import TaskManager, TaskStatus


def reset_task_manager_singleton():
    """Force TaskManager to simulate a fresh process start."""
    TaskManager._instance = None


def test_task_manager_recovers_tasks_from_disk(tmp_path, monkeypatch):
    """Tasks should still be available after the singleton is recreated."""
    monkeypatch.setattr(TaskManager, "TASKS_DIR", str(tmp_path / "tasks"))
    reset_task_manager_singleton()

    manager = TaskManager()
    task_id = manager.create_task("report_generate", metadata={"simulation_id": "sim_1"})
    manager.update_task(
        task_id,
        status=TaskStatus.PROCESSING,
        progress=42,
        message="working",
        progress_detail={"stage": "analysis"},
    )
    manager.complete_task(task_id, {"report_id": "report_1"})

    reset_task_manager_singleton()
    reloaded = TaskManager()
    task = reloaded.get_task(task_id)

    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert task.progress == 100
    assert task.result == {"report_id": "report_1"}
    assert task.metadata == {"simulation_id": "sim_1"}
    assert [listed.task_id for listed in reloaded.list_tasks()] == [task_id]


def test_cleanup_old_tasks_removes_persisted_files(tmp_path, monkeypatch):
    """Cleaning old finished tasks should remove both memory and disk state."""
    monkeypatch.setattr(TaskManager, "TASKS_DIR", str(tmp_path / "tasks"))
    reset_task_manager_singleton()

    manager = TaskManager()
    old_task_id = manager.create_task("simulation_prepare")
    manager.fail_task(old_task_id, "boom")

    task = manager.get_task(old_task_id)
    assert task is not None
    task.created_at = datetime.now() - timedelta(hours=48)
    task.updated_at = task.created_at
    manager._save_task_unlocked(task)

    manager.cleanup_old_tasks(max_age_hours=24)

    assert manager.get_task(old_task_id) is None
    assert not (tmp_path / "tasks" / f"{old_task_id}.json").exists()

