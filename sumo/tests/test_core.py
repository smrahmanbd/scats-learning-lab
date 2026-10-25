"""Unit tests for the SCATS algorithms (no SUMO needed)."""
import _path  # noqa: F401
import pytest

from scats import core


def test_ds_worked_example():
    # g=30, T=12, n=10, h=1 -> wasted 2 s, used 28 s, DS 0.933
    assert core.degree_of_saturation(30, 12, 10, 1.0) == pytest.approx(28 / 30)


def test_ds_saturated_and_empty():
    assert core.degree_of_saturation(40, 40, 0, 1.6) == 0.0
    # perfectly saturated: gaps exactly n*h
    assert core.degree_of_saturation(40, 20 * 1.6, 20, 1.6) == pytest.approx(1.0)
    # gaps smaller than h -> DS above 1
    assert core.degree_of_saturation(40, 20, 20, 1.6) > 1.0


def test_vk():
    assert core.reconstituted_flow(1.0, 36, 1800) == pytest.approx(18)


def test_cycle_bounded_steps():
    p = core.CycleParams()
    assert core.next_cycle_length(60, 1.2, p) == 69          # fast step +9
    assert core.next_cycle_length(60, 0.95, p) == pytest.approx(60 * 0.95 / 0.9)  # within +6
    assert core.next_cycle_length(60, 0.3, p) == 54          # -6
    assert core.next_cycle_length(40, 0.1, p) == 40          # LMIN
    assert core.next_cycle_length(140, 1.3, p) == 140        # LMAX


def test_allocate_greens_and_stretch():
    g = core.allocate_greens(90, {"A": 0.6, "B": 0.4}, {"A": 5, "B": 5}, {"A": 8, "B": 8})
    assert g["A"] + g["B"] == pytest.approx(80)
    g2 = core.allocate_greens(130, {"A": 0.6, "B": 0.4}, {"A": 5, "B": 5}, {"A": 8, "B": 8}, "A", 110)
    assert g2["B"] == pytest.approx(40)       # B frozen at its stretch-cycle share
    assert g2["A"] == pytest.approx(60 + 20)  # A takes the extra 20 s


def test_split_selection_balances_ds():
    ds = {"A": 1.0, "B": 0.5}
    g_now = {"A": 30, "B": 30}
    plans = [{"A": 30, "B": 30}, {"A": 40, "B": 20}]
    best, scores = core.select_split_plan(ds, g_now, plans)
    assert best == 1 and scores[1] == pytest.approx(0.75)


def test_voter():
    v = core.Voter(0, window=3, needed=2)
    assert v.vote(1) == 0
    assert v.vote(2) == 0
    assert v.vote(1) == 1


def test_offsets():
    xs = [0, 300, 600]
    assert core.offsets_for_plan(0, xs, 0, 12, 80) == pytest.approx([0, 25, 50])
    assert core.offsets_for_plan(1, xs, 0, 12, 80) == pytest.approx([0, 55, 30])
    assert core.select_offset_plan(100, 40, 25, 80) == 0
    assert core.select_offset_plan(40, 100, 25, 80) == 1
    assert core.select_offset_plan(0, 1, 25, 80) == 2


def test_marriage_hysteresis():
    m = core.MarriageLogic()
    for _ in range(2):
        assert not m.vote(30, 60, 60)
    assert m.vote(30, 60, 60)              # third consecutive vote marries
    assert m.vote(12, 60, 60)              # between thresholds: stays married
    for _ in range(3):
        m.vote(5, 60, 60)
    assert not m.married


def test_webster():
    assert core.webster_cycle(10, [0.35, 0.25]) == pytest.approx(50)
