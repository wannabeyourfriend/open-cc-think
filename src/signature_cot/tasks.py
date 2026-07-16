"""Checked-in synthetic tasks used by the CLI and ACL experiment fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    question: str
    expected_answer: str
    kind: str = "qa"
    required_answer_facts: Tuple[str, ...] = ()


REFERENCE_TASKS: Dict[str, TaskSpec] = {
    "walking-rates": TaskSpec(
        task_id="walking-rates",
        title="AIME Walking / Running / Bicycling Rates",
        question=(
            "Patrick started walking at a constant rate along a straight road from school to the park. "
            "One hour after Patrick left, Tanya started running along the same road from school to the "
            "park. One hour after Tanya left, Jose started bicycling along the same road from school to "
            "the park. Tanya ran at a constant rate of 2 miles per hour faster than Patrick walked, Jose "
            "bicycled at a constant rate of 7 miles per hour faster than Tanya ran, and all three arrived "
            "at the park at the same time. The distance from the school to the park is m/n miles, where m "
            "and n are relatively prime positive integers. Find m + n."
        ),
        expected_answer="277",
        required_answer_facts=("277",),
    ),
    "cubic-roots": TaskSpec(
        task_id="cubic-roots",
        title="Cubic With Squared Roots",
        question=(
            "Find the greatest integer n such that the cubic polynomial "
            "x^3 - (n/6)x^2 + (n-11)x - 400 has roots alpha^2, beta^2, gamma^2, where "
            "alpha, beta, gamma are complex numbers, and there are exactly seven different possible "
            "values for alpha + beta + gamma."
        ),
        expected_answer="132",
        required_answer_facts=("132",),
    ),
}


AGENTIC_TASK = TaskSpec(
    task_id="procurement-agent",
    title="Deterministic Procurement Agent",
    kind="agentic",
    question=(
        "Prepare a quote for 7 units of SENSOR-A and 3 units of CASE-R. Look up each authoritative "
        "unit price and stock, calculate the subtotal with the calculator tool, retrieve the shipping "
        "and approval policy, then report: subtotal, shipping, grand total, and whether manager "
        "approval is required. Use every relevant tool and keep the final response to one compact line."
    ),
    expected_answer="subtotal $1,048.25; shipping $0.00; grand total $1,048.25; manager approval: no",
    required_answer_facts=("1,048.25", "$0.00", "approval", "not required"),
)


def evaluate_answer(task: TaskSpec, answer: str) -> bool:
    low = answer.casefold()
    required = task.required_answer_facts or (task.expected_answer,)
    return all(fact.casefold() in low for fact in required)
