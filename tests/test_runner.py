from pentai.ui.runner import TurnController

def test_submit_idle_begins_turn():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("scan 10.0.0.5")
    assert started == ["scan 10.0.0.5"] and c.busy is True

def test_submit_while_busy_enqueues():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("first")
    c.submit("second")
    assert started == ["first"]            # second not started yet
    assert c.queue.pending == ["second"]

def test_finish_drains_next():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("first"); c.submit("second")
    c.finish()
    assert started == ["first", "second"]  # finish began the queued one
    assert c.busy is True

def test_finish_when_empty_goes_idle():
    c = TurnController(start_turn=lambda t: None)
    c.submit("only"); c.finish()
    assert c.busy is False and c.queue.pending == []

def test_confirm_routing():
    answers = []
    c = TurnController(start_turn=lambda t: None)
    c.submit("scan")                       # busy now
    c.request_confirm(answers.append)
    assert c.awaiting_confirm is True
    c.submit("yes")                        # this is the answer, not a new turn/queue item
    assert answers == [True]
    assert c.awaiting_confirm is False
    assert c.queue.pending == []           # not enqueued

def test_confirm_no_variant():
    answers = []
    c = TurnController(start_turn=lambda t: None)
    c.submit("scan"); c.request_confirm(answers.append)
    c.submit("n")
    assert answers == [False]

def test_stop_only_when_busy():
    c = TurnController(start_turn=lambda t: None)
    c.stop()
    assert c.stopped is False
    c.submit("scan")
    c.stop()
    assert c.stopped is True

def test_stop_resolves_pending_confirm_as_no():
    answers = []
    c = TurnController(start_turn=lambda t: None)
    c.submit("scan")
    c.request_confirm(answers.append)
    c.stop()
    assert answers == [False]
    assert c.awaiting_confirm is False
    assert c.stopped is True

def test_blank_submit_ignored():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("   ")
    assert started == [] and c.busy is False
