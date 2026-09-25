"""Decision providers: typed, calibrated judgments over Ringer's own state.

Beside `engines/`, which swaps the worker that DOES a task, this swaps the
provider that JUDGES one. An engine is autoregressive, produces an artifact,
and is verified by an executed check. A decision provider answers typed
questions about a state, produces no artifact, and carries its own certainty
instead of a check.

Importing this package registers the offline `heuristic` provider, which is
the fallback whenever a judgment vendor is absent, unauthenticated, rate
limited or overloaded.

This file was reconstructed after the original was lost to a clobbered
export; it re-exports exactly the names `decisions.provider.__all__`
declares.
"""
from decisions.provider import (  # noqa: F401
    Answer,
    Answers,
    Choice,
    ChoiceAnswer,
    DecisionProvider,
    Description,
    Noul,
    NoulAnswer,
    ProviderFactory,
    Question,
    Questions,
    Score,
    ScoreAnswer,
    get_provider,
    register_provider,
)

# Registers "heuristic" as a side effect of import, so get_provider finds it.
from decisions import heuristic as _heuristic  # noqa: F401,E402

__all__ = [
    "Noul", "Choice", "Score", "Question", "Questions", "Description",
    "NoulAnswer", "ChoiceAnswer", "ScoreAnswer", "Answer", "Answers",
    "DecisionProvider", "ProviderFactory", "register_provider",
    "get_provider",
]
