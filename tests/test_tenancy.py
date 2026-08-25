from llm_cost_tracker.tenancy import bearer_token, generate_api_key, hash_api_key


def test_generates_and_hashes_high_entropy_api_key() -> None:
    first = generate_api_key()
    second = generate_api_key()
    assert first.startswith("llmct_")
    assert len(first) > 40
    assert first != second
    assert len(hash_api_key(first)) == 64
    assert hash_api_key(first) != hash_api_key(second)


def test_parses_bearer_token_strictly() -> None:
    assert bearer_token("Bearer secret") == "secret"
    assert bearer_token("bearer secret") == "secret"
    assert bearer_token("Basic secret") is None
    assert bearer_token(None) is None
