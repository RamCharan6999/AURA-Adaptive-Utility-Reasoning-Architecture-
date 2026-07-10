"""Explanation formatting — renders an AuraExplanation as the standard
human-readable AURA box. Pure presentation: no analysis happens here, so
the format can evolve (or be replaced by an LLM verbalizer in Phase 3)
without touching any reasoning code.
"""

from __future__ import annotations

from aura_core.engine.explanation import AuraExplanation


class ExplanationFormatter:
    """Renders explanations in the standard AURA box format."""

    BAR = "\u2501" * 39

    def format(self, exp: AuraExplanation) -> str:
        """Return the multi-line explanation text for one decision."""
        lines = [self.BAR, "AURA EXPLANATION", self.BAR]
        lines.append(f"Trigger:     {exp.trigger_event}")
        if exp.trigger_description:
            lines.append(f"             {exp.trigger_description}")

        if exp.conflict_detected:
            lines.append(
                f"Conflict:    {exp.conflict_qas}"
                + ("  [THREE-WAY]" if exp.three_way_conflict else "")
            )
            lines.append(f"             {exp.conflict_description}")
        else:
            lines.append("Conflict:    none")

        lines.append(f"Decision:    {exp.selected_policy}")
        lines.append(
            f"             Score: {exp.selected_score:.3f}"
            + ("   (UNCERTAIN — close call)" if exp.uncertain_decision else "")
        )
        lines.append(f"Rejected:    {exp.rejected_policy}")
        lines.append(f"             Score: {exp.rejected_score:.3f}")
        lines.append(f"             Gap:   {exp.score_gap:.3f}")
        lines.append(f"Dominant QA: {exp.dominant_qa} (w={exp.dominant_weight:.2f})")
        lines.append(f"             {exp.dominant_reason}")
        lines.append(f"Benefit:     {exp.benefit_value:+.3f} utility — "
                     f"{exp.benefit_description}")
        lines.append(f"Cost:        {-exp.cost_value:+.3f} utility — "
                     f"{exp.cost_description}")

        if exp.policy_changed:
            lines.append(f"Previous:    {exp.previous_policy}")
            lines.append(
                f"Changed by:  {exp.changed_context_variable}"
                + (
                    f" (delta {exp.changed_context_delta:+.2f})"
                    if exp.changed_context_variable
                    not in ("operator_weights", "mission_priority")
                    else ""
                )
            )
            if exp.context_unchanged:
                lines.append(
                    "             NOTE: context unchanged — operator "
                    "accepted this tradeoff explicitly"
                )
        lines.append(self.BAR)
        return "\n".join(lines)
