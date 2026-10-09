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

__all__ = [
    "MeasurementObservation",
    "NormalizedObservations",
    "build_measurement_section",
    "normalize_ast_observations",
]
