from datetime import datetime, timezone

import pytest

from sas.models import Finding, Flow, HumanDecision, Level, Signal, Source, State


def test_signal_is_hashable_and_frozen():
    s = Signal(name="demo", version="1.1", source=Source.CHECKS, level=Level.STRONG,
               kind="typosquat", evidence={"proche_de": "requests"})
    # evidence est un dict : le hash doit quand même fonctionner (il n'entre pas dans le hash)
    assert hash(s) == hash(Signal(name="demo", version="1.1", source=Source.CHECKS,
                                  level=Level.STRONG, kind="typosquat", evidence={}))
    with pytest.raises(AttributeError):
        s.level = Level.INFO  # type: ignore[misc]


def test_enums_round_trip_from_strings():
    assert State("approved") is State.APPROVED
    assert Level("block") is Level.BLOCK
    assert Source("egress") is Source.EGRESS


def test_level_order_is_by_severity():
    assert Level.INFO.rank < Level.MEDIUM.rank < Level.STRONG.rank < Level.BLOCK.rank


def test_state_order_is_by_permissiveness():
    # blocked < review < quarantine < fast_track < approved (utilisé par l'invariant de A2)
    order = [State.BLOCKED, State.REVIEW, State.QUARANTINE, State.FAST_TRACK, State.APPROVED]
    assert [s.permissiveness for s in order] == sorted(s.permissiveness for s in order)
    assert len({s.permissiveness for s in order}) == 5


def test_other_contracts_build():
    now = datetime.now(timezone.utc)
    Finding(kind="exec_in_setup", file="setup.py", line=42, excerpt="exec(...)")
    Flow(host="10.0.0.5", domain="example.test", port=443, started_at=now,
         bytes_up=10, bytes_down=20, duration_ms=5)
    HumanDecision(state=State.BLOCKED, actor="sam", reason="test", at=now)
