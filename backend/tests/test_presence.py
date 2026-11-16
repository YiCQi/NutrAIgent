from app.presence import Presence


def test_never_stops_before_first_ping():
    p = Presence(timeout=10, grace=2)
    assert p.should_stop(0, busy=False) is False
    assert p.should_stop(100, busy=False) is False


def test_stops_after_bye_and_grace():
    p = Presence(timeout=10, grace=2)
    p.ping("a", now=0)
    assert p.should_stop(1, busy=False) is False
    p.bye("a")
    assert p.should_stop(1, busy=False) is False  # grace starts
    assert p.should_stop(2.5, busy=False) is False
    assert p.should_stop(3.5, busy=False) is True


def test_reload_cancels_stop():
    p = Presence(timeout=10, grace=2)
    p.ping("a", now=0)
    p.bye("a")
    assert p.should_stop(1, busy=False) is False
    p.ping("a", now=2)  # new page after reload
    assert p.should_stop(10, busy=False) is False


def test_other_open_tab_keeps_server():
    p = Presence(timeout=10, grace=2)
    p.ping("a", now=0)
    p.ping("b", now=0)
    p.bye("a")
    assert p.should_stop(1, busy=False) is False  # b still open
    assert p.should_stop(9, busy=False) is False  # b still pinging within timeout


def test_stops_when_tab_silent_past_timeout():
    p = Presence(timeout=10, grace=2)
    p.ping("a", now=0)
    assert p.should_stop(10, busy=False) is False  # still within timeout
    assert p.should_stop(11, busy=False) is False  # timed out, grace starts
    assert p.should_stop(13.5, busy=False) is True


def test_never_stops_while_busy():
    p = Presence(timeout=10, grace=2)
    p.ping("a", now=0)
    p.bye("a")
    assert p.should_stop(1, busy=True) is False
    assert p.should_stop(100, busy=True) is False
    assert p.should_stop(100, busy=False) is False  # grace restarts after busy ends
    assert p.should_stop(103, busy=False) is True
