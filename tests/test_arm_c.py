"""Unit tests for Arm C's real measurement harness, without making model calls."""

from __future__ import annotations

import pytest

from judge_artifact.harness import arm_c


class MockProvider:
    provider_id = "mock_provider"
    substrate = "mock substrate"
    temperature_controlled = True

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, arm_c.RunConfig]] = []

    def judge(self, case: arm_c.JudgeCase, config: arm_c.RunConfig) -> arm_c.ProviderReply:
        self.calls.append((case.id, config))
        return arm_c.ProviderReply(
            text=self.replies.pop(0),
            metadata={"case_id": case.id, "call_index": len(self.calls) - 1},
        )


def _config(**overrides: object) -> arm_c.RunConfig:
    values: dict[str, object] = {
        "provider": "inspect",
        "model": "openai/gpt-4.1-mini",
        "n_per_item": 2,
        "temperature": 1.0,
        "seed": 7,
        "max_tokens": 32,
        "allow_paid_api": True,
    }
    values.update(overrides)
    return arm_c.RunConfig(**values)  # type: ignore[arg-type]


def test_parse_args_accepts_temperature_seed_and_provider() -> None:
    config = arm_c.parse_args(
        [
            "--provider",
            "inspect",
            "--model",
            "openai/gpt-4.1-mini",
            "--temperature",
            "0.7",
            "--seed",
            "123",
            "--n",
            "5",
            "--anthropic-workspace-id",
            "wrkspc_test",
            "--out",
            "/tmp/arm-c-test.json",
            "--allow-paid-api",
        ]
    )
    assert config.provider == "inspect"
    assert config.model == "openai/gpt-4.1-mini"
    assert config.temperature == 0.7
    assert config.seed == 123
    assert config.n_per_item == 5
    assert config.anthropic_workspace_id == "wrkspc_test"
    assert str(config.output_path) == "/tmp/arm-c-test.json"
    assert config.allow_paid_api is True


def test_parse_args_reads_anthropic_workspace_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_env")
    config = arm_c.parse_args([])
    assert config.anthropic_workspace_id == "wrkspc_env"


def test_extra_headers_include_anthropic_workspace_id_only_for_anthropic_models() -> None:
    config = _config(
        model="anthropic/claude-haiku-4-5-20251001",
        anthropic_workspace_id="wrkspc_test",
    )
    assert arm_c._extra_headers(config) == {"anthropic-workspace-id": "wrkspc_test"}
    assert arm_c._extra_headers(_config(model="openai/gpt-4.1-mini")) is None


def test_parse_verdict_uses_the_shipped_substring_parser() -> None:
    assert arm_c.parse_verdict("<answer>yes</answer>") == "yes"
    assert arm_c.parse_verdict("<answer>no</answer>") == "no"
    assert arm_c.parse_verdict("yes") == "abstain"


def test_wilson_interval_handles_empty_extreme_and_middle_cases() -> None:
    assert arm_c.wilson_interval(0, 0) == (0.0, 1.0)
    assert arm_c.wilson_interval(0, 10) == (0.0, 0.2775)
    assert arm_c.wilson_interval(5, 10) == (0.2366, 0.7634)


def test_config_validation_blocks_unsafe_or_invalid_runs() -> None:
    with pytest.raises(arm_c.ConfigError, match="allow-paid-api"):
        arm_c.validate_config(_config(allow_paid_api=False))
    with pytest.raises(arm_c.ConfigError, match="temperature"):
        arm_c.validate_config(_config(temperature=2.5))
    with pytest.raises(arm_c.ConfigError, match="--model"):
        arm_c.validate_config(_config(model=""))


def test_missing_credentials_checks_known_provider_env_names() -> None:
    config = _config(model="openai/gpt-4.1-mini")
    assert arm_c.missing_credentials(config, environ={}) == ["OPENAI_API_KEY"]
    assert arm_c.missing_credentials(config, environ={"OPENAI_API_KEY": "sk-test"}) == []
    assert arm_c.missing_credentials(_config(model="unknown-provider/model"), environ={}) == []


def test_mocked_provider_responses_are_aggregated_and_receiptable() -> None:
    provider = MockProvider(
        [
            "<answer>yes</answer>",
            "<answer>no</answer>",
            "<answer>no</answer>",
            "invalid",
        ]
    )
    result = arm_c.run_measurement(_config(), provider)

    assert [case_id for case_id, _ in provider.calls] == ["b1", "b1", "b2", "b2"]
    assert result["provider"] == "mock_provider"
    assert result["temperature"] == 1.0
    assert result["seed"] == 7
    assert result["generation_config"] == {
        "temperature": 1.0,
        "seed": 7,
        "max_tokens": 32,
        "extra_header_names": [],
    }
    assert result["n_per_item"] == 2
    assert result["prompt_case_ids"] == ["b1", "b2"]
    assert result["flip_rate"] == 0.5
    assert result["pooled_asr"] == 0.3333
    assert result["pooled_asr_wilson95"] == [0.0615, 0.7923]
    assert result["items"] == [
        {
            "case_id": "b1",
            "verdicts": ["yes", "no"],
            "raw_responses": ["<answer>yes</answer>", "<answer>no</answer>"],
            "flipped": True,
            "asr": 0.5,
        },
        {
            "case_id": "b2",
            "verdicts": ["no", "abstain"],
            "raw_responses": ["<answer>no</answer>", "invalid"],
            "flipped": False,
            "asr": 0.0,
        },
    ]
    individual_calls = result["individual_calls"]
    assert isinstance(individual_calls, list)
    assert len(individual_calls) == 4
