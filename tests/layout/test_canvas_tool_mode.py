from gui.layout.canvas_widget import CanvasWidget


def test_knife_two_click_state(qapp):
    c = CanvasWidget()
    c.set_tool_mode("knife")
    assert c.tool_mode() == "knife"
    assert c._register_knife_point(10.0, 20.0) is None       # first click stored
    assert c._register_knife_point(30.0, 40.0) == (10.0, 20.0, 30.0, 40.0)


def test_set_tool_mode_resets_and_validates(qapp):
    c = CanvasWidget()
    c.set_tool_mode("knife")
    c._register_knife_point(1.0, 1.0)        # half-entered knife
    c.set_tool_mode("bogus")                 # invalid -> "none" + reset
    assert c.tool_mode() == "none"
    assert c._knife_first is None
