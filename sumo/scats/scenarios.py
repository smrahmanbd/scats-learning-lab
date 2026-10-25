"""Standard scenarios used by the three learning levels."""
from .runner import Scenario


def foundation(end: float = 3600.0) -> Scenario:
    """One 2-phase intersection with an off-peak / peak / off-peak profile."""
    third = end / 3
    periods = [
        dict(begin=0, end=third, east=700, west=600, side=250, turn=50),
        dict(begin=third, end=2 * third, east=1900, west=1700, side=650, turn=80),
        dict(begin=2 * third, end=end, east=700, west=600, side=250, turn=50),
    ]
    return Scenario("foundation", n=1, phase_set="two", periods=periods,
                    subsystems=[[0]], ci=[0], end=end)


def advanced(end: float = 5400.0, bus_headway: float = 240.0) -> Scenario:
    """Four 3-phase intersections, two subsystems that can marry,
    eastbound AM peak then westbound PM peak, buses both ways."""
    q = end / 4.5
    periods = [
        dict(begin=0, end=q, east=500, west=450, side=150, turn=30),
        dict(begin=q, end=2.5 * q, east=1700, west=700, side=250, turn=50),
        dict(begin=2.5 * q, end=3.5 * q, east=700, west=1700, side=250, turn=50),
        dict(begin=3.5 * q, end=end, east=500, west=450, side=150, turn=30),
    ]
    return Scenario("advanced", n=4, spacing=300, phase_set="three", periods=periods,
                    bus_headway=bus_headway, subsystems=[[0, 1], [2, 3]], ci=[1, 2],
                    marriages=[(0, 1)], end=end)
