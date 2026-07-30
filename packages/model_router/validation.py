from __future__ import annotations

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan


class ResponsePlanValidationError(ValueError):
    pass


def validate_response_plan(value: object, expected_recipient: str | None = None) -> ResponsePlan:
    try:
        return ResponsePlan.from_dict(value.to_dict() if isinstance(value, ResponsePlan) else value, expected_recipient)
    except (TypeError, ValueError) as error:
        raise ResponsePlanValidationError(str(error)) from error
