import os

import pytest


pytestmark = pytest.mark.live


@pytest.mark.skipif(
    os.environ.get("PRC_QWEN_RUN_LIVE_TESTS") != "1",
    reason="live Qwen integration tests are opt-in via PRC_QWEN_RUN_LIVE_TESTS=1",
)
def test_live_tests_are_opt_in_placeholder() -> None:
    assert os.environ.get("DASHSCOPE_API_KEY")
