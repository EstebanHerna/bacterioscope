"""Agent core: Persona 1 ownership (Token Factory client, routing, report contract).

This package is the integration boundary between the existing CV pipeline and
the Persona 2 deterministic rule tools. See docs/AGENT_ARCHITECTURE.md for the
end-to-end workflow and docs/contracts/agent-review-v1.schema.json for the
output contract this package must produce.
"""

from bacterioscope.agent.contract import (
    MeasurementObservation,
    NormalizedObservations,
    build_measurement_section,
    normalize_ast_observations,
)
from bacterioscope.agent.nemotron_client import (
    ChatCompletionResult,
    TokenFactoryClient,
    TokenFactoryConfigurationError,
    TokenFactoryRequestError,
)
from bacterioscope.agent.routing import (
    select_escalation_tier,
    select_report_tier,
    select_triage_tier,
)
from bacterioscope.agent.validator import ValidationResult, validate_and_render

__all__ = [
    "ChatCompletionResult",
    "MeasurementObservation",
    "NormalizedObservations",
    "TokenFactoryClient",
    "TokenFactoryConfigurationError",
    "TokenFactoryRequestError",
    "ValidationResult",
    "build_measurement_section",
    "normalize_ast_observations",
    "select_escalation_tier",
    "select_report_tier",
    "select_triage_tier",
    "validate_and_render",
]
