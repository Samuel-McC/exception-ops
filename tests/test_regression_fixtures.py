from __future__ import annotations

from exception_ops.replay import load_replay_corpus


def test_v1_replay_fixture_corpus_is_small_and_representative() -> None:
    corpus = load_replay_corpus()

    assert corpus.corpus_version == "v1"
    assert len(corpus.fixtures) == 5
    assert {fixture.fixture_id for fixture in corpus.fixtures} == {
        "approval-required-provider-failure",
        "no-approval-required-missing-document",
        "incomplete-evidence-duplicate-record-risk",
        "ai-provider-configuration-failure",
        "execution-adapter-configuration-failure",
    }
