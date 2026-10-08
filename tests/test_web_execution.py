"""Web calculations are bounded: they time out, cancel build analysis, and leave no threads.

The slow path is simulated by replacing the realized-build analysis with one that waits
for its cancellation check, so each test controls exactly when work starts and ends.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("fastapi")

from filter_lib.shared.build_types import BuildAnalysisCancelled  # noqa: E402
from filter_lib.web.execution import CalculationRunner, CalculationTimeout  # noqa: E402
from filter_lib.web.settings import WebSettings  # noqa: E402
from tests.web_helpers import HTMX, pool_threads, web_client  # noqa: E402

LP = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}
BUILD = {**LP, "sim_build": "on"}
TIMEOUT_MESSAGE = (
    "Calculation stopped after 0.2 s. Try fewer extra random tolerance cases or frequency points."
)


def _wait_until(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


@pytest.fixture
def cancellable_analysis(monkeypatch):
    """Replace the build analysis with one that runs until it is cancelled."""
    state = {"started": threading.Event(), "cancelled": threading.Event()}

    def analysis(_result, _category, _config, *, should_cancel=None):
        state["started"].set()
        # Bounded so a regression that never cancels fails instead of hanging the suite.
        if not _wait_until(should_cancel, timeout=5.0):
            raise AssertionError("the build analysis was never asked to cancel")
        state["cancelled"].set()
        raise BuildAnalysisCancelled()

    monkeypatch.setattr("filter_lib.shared.build_simulation.analyze_build", analysis)
    return state


def test_timeout_returns_503_and_cancels_the_analysis(cancellable_analysis):
    baseline = len(pool_threads())

    with web_client(calculation_timeout_s=0.2, max_workers=1) as client:
        response = client.post("/api/design/lowpass", data=BUILD)

        assert response.status_code == 503
        assert response.json() == {"error": TIMEOUT_MESSAGE}
        assert cancellable_analysis["cancelled"].wait(5)

    assert _wait_until(lambda: len(pool_threads()) == baseline)


def test_timeout_in_the_design_view_is_an_html_notice(cancellable_analysis):
    with web_client(calculation_timeout_s=0.2) as client:
        response = client.post("/design/lowpass", data=BUILD, headers=HTMX)

    assert response.status_code == 503
    assert TIMEOUT_MESSAGE in response.text
    assert 'role="alert"' in response.text


def test_a_cancelled_analysis_is_reported_as_unavailable(monkeypatch):
    def cancelled(*_args, **_kwargs):
        raise BuildAnalysisCancelled()

    monkeypatch.setattr("filter_lib.shared.build_simulation.analyze_build", cancelled)
    with web_client() as client:
        page = client.post("/design/lowpass", data=BUILD, headers=HTMX)
        api = client.post("/api/design/lowpass", data=BUILD)

    assert page.status_code == api.status_code == 503
    assert "Calculation stopped" in page.text
    assert api.json() == {"error": "Calculation stopped"}


def test_shutdown_cancels_running_work_and_joins_the_pool():
    baseline = len(pool_threads())
    runner = CalculationRunner(WebSettings(calculation_timeout_s=30, max_workers=1))
    started = threading.Event()
    observed = []

    def work(should_cancel):
        started.set()
        if _wait_until(should_cancel, timeout=5.0):
            observed.append("cancelled")
        return "stopped"

    async def scenario():
        task = asyncio.ensure_future(runner.run(work))
        await asyncio.get_running_loop().run_in_executor(None, started.wait, 5)
        await asyncio.get_running_loop().run_in_executor(None, runner.shutdown)
        return await task

    assert asyncio.run(scenario()) == "stopped"
    assert observed == ["cancelled"]
    assert len(pool_threads()) == baseline


def test_requests_beyond_the_pool_size_queue_instead_of_failing():
    runner = CalculationRunner(WebSettings(max_workers=1))
    release = threading.Event()
    order = []

    def blocking(_should_cancel):
        release.wait(5)
        order.append("first")
        return 1

    def quick(_should_cancel):
        order.append("second")
        return 2

    async def scenario():
        first = asyncio.ensure_future(runner.run(blocking))
        second = asyncio.ensure_future(runner.run(quick))
        await asyncio.sleep(0.05)
        assert not second.done()
        release.set()
        return await asyncio.gather(first, second)

    try:
        assert asyncio.run(scenario()) == [1, 2]
        assert order == ["first", "second"]
    finally:
        runner.shutdown()


def test_queued_work_that_times_out_never_starts():
    runner = CalculationRunner(WebSettings(calculation_timeout_s=0.2, max_workers=1))
    occupied, release = threading.Event(), threading.Event()
    ran = []

    def hold(_should_cancel):
        occupied.set()
        release.wait(5)

    async def scenario():
        holder = asyncio.ensure_future(runner.run(hold))
        await asyncio.get_running_loop().run_in_executor(None, occupied.wait, 5)
        with pytest.raises(CalculationTimeout):
            await runner.run(lambda _c: ran.append("queued"))
        release.set()
        # The holder waited past its own budget too, so it is reported the same way.
        with pytest.raises(CalculationTimeout):
            await holder

    try:
        asyncio.run(scenario())
    finally:
        runner.shutdown()
    assert ran == []


def test_an_abandoned_request_cancels_its_work():
    runner = CalculationRunner(WebSettings(calculation_timeout_s=30, max_workers=1))
    started, finished = threading.Event(), threading.Event()
    seen = []

    def work(should_cancel):
        started.set()
        seen.append(_wait_until(should_cancel, timeout=5.0))
        finished.set()

    async def scenario():
        task = asyncio.ensure_future(runner.run(work))
        await asyncio.get_running_loop().run_in_executor(None, started.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(scenario())
        assert finished.wait(5)
    finally:
        runner.shutdown()
    assert seen == [True]


def test_concurrent_requests_all_succeed_with_one_worker():
    with web_client(max_workers=1) as client, ThreadPoolExecutor(3) as pool:
        responses = list(pool.map(lambda _i: client.post("/api/design/lowpass", data=LP), range(3)))

    assert [r.status_code for r in responses] == [200, 200, 200]
    assert len({r.content for r in responses}) == 1


def test_exports_write_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with web_client() as client:
        for kind in (
            "json",
            "csv",
            "spice-exact",
            "spice-nominal",
            "response-json",
            "response-csv",
        ):
            assert client.post(f"/export/lowpass/{kind}", data=LP).status_code == 200

    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    "settings, message",
    [
        ({"calculation_timeout_s": 0}, "Calculation timeout must be between 0 and 3600 seconds"),
        ({"max_workers": 0}, "Worker count must be 1-32"),
        ({"port": 70000}, "Port must be 1-65535"),
    ],
)
def test_settings_reject_out_of_range_limits(settings, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        WebSettings(**settings)
