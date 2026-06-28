from replaygate.capture.adapters import DirectAdapter, Scenario


def test_direct_adapter_yields_user_messages_per_turn():
    scenario = Scenario(name="booking", user_turns=[["hi", "book a slot"], ["yes"]])
    adapter = DirectAdapter()
    turns = list(adapter.user_turns(scenario))
    assert adapter.name == "direct"
    assert len(turns) == 2
    assert [m.content for m in turns[0]] == ["hi", "book a slot"]
    assert turns[0][0].channel_meta.order_index == 0
    assert turns[0][1].channel_meta.order_index == 1
    assert all(m.role == "user" for t in turns for m in t)
