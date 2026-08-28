from src.server.workspace_security import (
    issue_workspace_token,
    verify_workspace_token,
)


def test_workspace_token_is_bound_and_expires():
    token = issue_workspace_token("workspace-a", secret="unit-secret", now=1000)
    assert token
    assert verify_workspace_token("workspace-a", token, secret="unit-secret", now=1000)
    assert not verify_workspace_token("workspace-b", token, secret="unit-secret", now=1000)
    assert not verify_workspace_token("workspace-a", token, secret="other-secret", now=1000)

    payload, signature = token.split(".", 1)
    expired = f"{payload}.{signature}"
    assert not verify_workspace_token("workspace-a", expired, secret="unit-secret", now=100000)


def test_workspace_token_rejects_malformed_values():
    assert not verify_workspace_token("workspace-a", None, secret="unit-secret")
    assert not verify_workspace_token("workspace-a", "bad-token", secret="unit-secret")
