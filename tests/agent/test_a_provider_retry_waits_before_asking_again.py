"""Three attempts in one blink are one observation, repeated.

The loop already retries a failed provider attempt rather than ending a
session on one transport error, and its reasoning is sound: a failed
attempt never mutated session state, so asking again is safe. What it
did not do is wait.

Observed live: three 30 s connect timeouts inside about 90 seconds ended
a session that had made 73 tool calls, planned four workflows and
composed both of its transition-state guess geometries. Nothing was
resumable, because no run had been recorded yet. Minutes later the same
endpoint answered a probe in 2.7 s, and the harness's own bounded
transport answered in 2.9 s -- the code was fine and the burst simply
sat inside one outage.

Spacing, never volume: the attempt budget is unchanged, so a provider
that is genuinely down still ends the session. The registered lesson
from a self-inflicted 429 is that a retry loop must read the error and
wait, not ask harder.
"""

from __future__ import annotations

from chemsmart.agent.loop import (
    _PROVIDER_FAILURE_CONSECUTIVE_RETRIES,
    _PROVIDER_RETRY_BACKOFF_SECONDS,
    ToolLoopRunner,
)


def test_a_wait_is_scheduled_for_every_retry_the_budget_allows():
    """One backoff value per retry, so no retry is unspaced."""

    assert (
        len(_PROVIDER_RETRY_BACKOFF_SECONDS)
        >= _PROVIDER_FAILURE_CONSECUTIVE_RETRIES
    )


def test_the_waits_increase_and_stay_bounded():
    values = list(_PROVIDER_RETRY_BACKOFF_SECONDS)

    assert values == sorted(values), values
    assert all(value > 0 for value in values)
    # A session must not be able to hang on backoff alone.
    assert sum(values) <= 60.0, values


def test_the_burst_now_outlives_the_outage_that_ended_a_session():
    """The observed failure was three 30 s timeouts in about 90 s.

    With the attempt cost unchanged, the added waits have to push the
    window materially past that, or the repair is cosmetic.
    """

    attempt_seconds = 30.0
    attempts = _PROVIDER_FAILURE_CONSECUTIVE_RETRIES + 1
    window = attempts * attempt_seconds + sum(_PROVIDER_RETRY_BACKOFF_SECONDS)

    assert window >= 110.0, window


def test_the_runner_takes_an_injectable_sleep():
    """Tests must never wait in real seconds, and neither must a fake."""

    waited: list[float] = []
    runner = ToolLoopRunner(
        host=object(),
        event_store=object(),
        clock=lambda: 0.0,
        sleep=waited.append,
    )

    runner.sleep(3.0)

    assert waited == [3.0]
