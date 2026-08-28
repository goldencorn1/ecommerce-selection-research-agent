from src.evaluation.p1_runner import run_p1_evaluation


def test_p1_deterministic_runner_measures_the_fixed_dataset() -> None:
    result = run_p1_evaluation(judge="deterministic")

    assert result.status == "measured"
    assert result.mode == "mock"
    assert result.total_case_count == 50
    assert result.measured_case_count == 50
    assert result.external_request_count == 0
    assert result.summary["mode"] == "mock"


def test_p1_llm_judge_without_adapter_is_blocked_without_fake_scores() -> None:
    result = run_p1_evaluation(judge="llm")

    assert result.status == "blocked"
    assert result.measured_case_count == 0
    assert result.external_request_count == 0
    assert result.block_reason == "llm_judge_requires_an_explicit_configured_adapter"


def test_p1_live_without_explicit_provider_is_blocked() -> None:
    result = run_p1_evaluation(mode="live")

    assert result.status == "blocked"
    assert (
        result.block_reason == "live_evaluation_requires_an_explicit_provider_adapter"
    )
