import json
from pathlib import Path

import pytest

from replaygate.capture.llm import request_key

FIXTURES = sorted((Path(__file__).parent.parent / "fixtures").glob("*/llm_recording.json"))


def test_the_fixtures_are_found():
    # A check over an empty glob passes, so prove it is looking at something.
    assert len(FIXTURES) >= 2


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.parent.name)
def test_every_committed_request_body_hashes_to_its_key(path):
    for entry in json.loads(path.read_text()):
        req = entry["request"]
        assert request_key(req["model"], req["system"], req["messages"], req["tools"]) == entry["request_key"]
