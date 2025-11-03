import time
from typing import Dict, Iterable

import pytest

from hq_command.gui.caching import PaginatedResult, PaginationController, StaleWhileRevalidateCache
from hq_command.gui.virtualization import VirtualizedSequence
from hq_command.performance import PerformanceMetrics
from hq_command.tasking_engine import ResponderStatus, TaskingOrder, schedule_tasks_for_field_units

try:  # pragma: no cover - import guard for headless environments
    from hq_command.gui.controller import HQCommandController
    from hq_command.gui.data_table import DataTableModel, SortOrder
    HAS_QT = True
except ImportError:  # pragma: no cover - exercised when PySide6 is missing
    HAS_QT = False


def test_virtualized_sequence_paginates_and_caches() -> None:
    rows = [{"id": idx, "value": idx * 2} for idx in range(500)]
    page_calls: list[int] = []

    def fetch_page(page: int, size: int) -> Iterable[Dict[str, int]]:
        page_calls.append(page)
        start = page * size
        end = min(start + size, len(rows))
        return rows[start:end]

    sequence = VirtualizedSequence(fetch_page, total_count=len(rows), page_size=100, cache_pages=2)
    assert sequence[0]["id"] == 0
    assert sequence[150]["id"] == 150
    # Accessing the same page again should hit the cache and not record an
    # additional fetch call.
    _ = sequence[120]
    assert page_calls.count(1) == 1
    sequence.prefetch(300, 350)
    metrics = sequence.metrics()
    assert metrics["cache_size"] <= 2


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not available")
def test_data_table_virtualized_source_round_trips_qmodelindex() -> None:
    rows = [{"id": idx, "value": idx} for idx in range(300)]

    def fetch_page(page: int, size: int) -> Iterable[Dict[str, int]]:
        start = page * size
        end = min(start + size, len(rows))
        return rows[start:end]

    model = DataTableModel(["id", "value"])
    sequence = VirtualizedSequence(fetch_page, total_count=len(rows), page_size=50)
    model.set_virtualized_source(sequence)

    index = model.index(10, 0)
    assert model.data(index) == 10
    model.prefetch_rows(100, 150)
    with pytest.raises(RuntimeError):
        model.sort(0, SortOrder.ASCENDING)


def test_stale_while_revalidate_cache_refreshes() -> None:
    cache = StaleWhileRevalidateCache[str, int](ttl_seconds=0.01, max_age_seconds=0.05)
    calls = 0

    def loader() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert cache.get("alpha", loader) == 1
    assert cache.get("alpha", loader) == 1
    time.sleep(0.02)
    assert cache.get("alpha", loader) == 1  # stale value returned
    assert calls >= 2  # refresh executed
    time.sleep(0.04)
    assert cache.get("alpha", loader) == calls
    snapshot = cache.snapshot()
    assert snapshot["hits"] >= 2
    assert snapshot["misses"] >= 1


def test_pagination_controller_batches_pages() -> None:
    data = list(range(105))

    def fetch(page: int, size: int) -> PaginatedResult[int]:
        start = page * size
        end = min(start + size, len(data))
        return PaginatedResult(data[start:end], total=len(data), page=page, page_size=size)

    controller = PaginationController(fetch, page_size=50)
    assert controller.page(0) == data[:50]
    assert controller.next_page() == data[50:100]
    controller.prefetch(2)
    assert controller.next_page() == data[100:]


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not available")
def test_controller_caching_reuses_schedule_and_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = HQCommandController()
    payload = {
        "tasks": [
            {"task_id": "a", "priority": 2},
        ],
        "responders": [
            {"unit_id": "unit", "capabilities": ["general"], "status": "available"},
        ],
        "telemetry": {"pings": 10},
    }

    schedule_calls = 0

    original_schedule = schedule_tasks_for_field_units

    def schedule_stub(*args, **kwargs):
        nonlocal schedule_calls
        schedule_calls += 1
        return original_schedule(*args, **kwargs)

    telemetry_calls = 0

    def telemetry_stub(payload):
        nonlocal telemetry_calls
        telemetry_calls += 1
        return {"pings": payload.get("pings", 0)}

    monkeypatch.setattr("hq_command.gui.controller.schedule_tasks_for_field_units", schedule_stub)
    monkeypatch.setattr("hq_command.gui.controller.summarize_field_telemetry", telemetry_stub)

    controller.load_from_payload(payload)
    assert schedule_calls == 1
    assert telemetry_calls == 1

    controller.refresh_models()
    assert schedule_calls == 1
    assert telemetry_calls == 1
    metrics = controller.performance_snapshot()
    assert "controller.refresh" in metrics

    payload["tasks"].append({"task_id": "b", "priority": 1})
    controller.load_from_payload(payload)
    assert schedule_calls >= 2


def test_parallel_scoring_records_audit() -> None:
    tasks = [TaskingOrder(task_id="main", priority=5, capabilities_required=frozenset({"medic"}))]
    responders = [
        ResponderStatus(unit_id=f"unit-{idx}", capabilities=frozenset({"medic"}), max_concurrent_tasks=2)
        for idx in range(20)
    ]

    result = schedule_tasks_for_field_units(tasks, responders)
    assert result["audit"]["parallel_scoring"] is True
    assert result["audit"]["candidate_evaluations"] == len(responders)


def test_performance_metrics_capture_duration() -> None:
    metrics = PerformanceMetrics()
    with metrics.time_block("sample"):
        time.sleep(0.001)
    snapshot = metrics.snapshot()
    assert snapshot["sample"]["count"] == 1.0

