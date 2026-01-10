"""Test token counting in isolation."""

from cortex.core.token_counter import TokenCounter


def test_token_counting():
    """Test basic token counting functionality."""
    print("Creating TokenCounter...")
    tc = TokenCounter()

    print("Counting tokens in test text...")
    text = "This is a test of the token counting system."
    count = tc.count_tokens(text)

    print(f"Token count: {count}")
    print("✅ Done!")

    assert count > 0
