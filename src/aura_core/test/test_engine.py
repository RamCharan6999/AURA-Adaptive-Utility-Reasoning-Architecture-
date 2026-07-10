"""Unit tests for the modular analyzers.

The most important tests here are the algebraic invariants: for a linear
utility, AURA's gap decomposition and benefit/cost figures must equal the
planner's own arithmetic exactly. This is what makes the explanations
faithful rather than narrative.

Run:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import itertools
import unittest

from aura_interfaces.context import RobotContext, QAWeights
from aura_core.engine.explanation_engine import ExplanationEngine
from aura_core.engine.analyzers import (
    TriggerAnalyzer,
    ConflictAnalyzer,
    DominantQAAnalyzer,
    TradeoffAnalyzer,
    QA_NAMES,
)
from aura_core.engine.policy import DEFAULT_POLICIES
from aura_core.engine.scoring import score_all_candidates




class UtilityPlanner:
    """Test shim: reproduces the planner node's decision cycle in pure Python."""
    def __init__(self, policies):
        self.policies = policies
        self._last = ""
    def make_decision(self, ctx, w):
        from aura_interfaces.evidence import AuraDecision
        ranked = sorted(score_all_candidates(self.policies, ctx, w),
                        key=lambda e: e.score, reverse=True)
        d = AuraDecision(selected=ranked[0], alternatives=ranked[1:],
                         policy_changed=(self._last not in ("", ranked[0].policy_name)),
                         previous_policy=self._last)
        self._last = ranked[0].policy_name
        return d
    def reset(self): self._last = ""

def make_context(**overrides) -> RobotContext:
    """A benign default context, overridable per test."""
    base = dict(battery_level=0.8, human_proximity=5.0, obstacle_density=0.1,
                localization_confidence=0.95, mission_priority="normal")
    base.update(overrides)
    return RobotContext(**base)


class TestTriggerAnalyzer(unittest.TestCase):
    """Question 1 — what happened?"""

    def setUp(self) -> None:
        self.analyzer = TriggerAnalyzer()
        self.weights = QAWeights(0.5, 0.3, 0.2)

    def test_steady_state_when_nothing_changes(self):
        ctx = make_context()
        event, _, _, _ = self.analyzer.analyze(ctx, ctx.copy(),
                                               self.weights, self.weights)
        self.assertEqual(event, "steady_state")

    def test_detects_largest_context_change(self):
        prev = make_context()
        curr = make_context(human_proximity=1.5, battery_level=0.79)
        event, value, unit, _ = self.analyzer.analyze(curr, prev,
                                                      self.weights, self.weights)
        self.assertEqual(event, "human_proximity")
        self.assertAlmostEqual(value, 1.5)
        self.assertEqual(unit, "m")

    def test_reports_threshold_crossing(self):
        prev = make_context(battery_level=0.25)
        curr = make_context(battery_level=0.18)
        event, _, _, desc = self.analyzer.analyze(curr, prev,
                                                  self.weights, self.weights)
        self.assertEqual(event, "battery_level")
        self.assertIn("threshold 0.2", desc)

    def test_operator_weight_change_outranks_context_drift(self):
        prev = make_context()
        curr = make_context(battery_level=0.5)   # a real context change too
        new_weights = QAWeights(0.2, 0.6, 0.2)
        event, _, unit, desc = self.analyzer.analyze(curr, prev,
                                                     new_weights, self.weights)
        self.assertEqual(event, "operator_weight_change")
        self.assertEqual(unit, "weight")
        self.assertIn("w_safety", desc)

    def test_mission_priority_change_detected(self):
        prev = make_context(mission_priority="normal")
        curr = make_context(mission_priority="emergency")
        event, value, _, _ = self.analyzer.analyze(curr, prev,
                                                   self.weights, self.weights)
        self.assertEqual(event, "mission_priority")
        self.assertEqual(value, 2.0)

    def test_no_previous_context_is_steady_state(self):
        event, _, _, _ = self.analyzer.analyze(make_context(), None,
                                               self.weights, None)
        self.assertEqual(event, "steady_state")


class TestConflictAnalyzer(unittest.TestCase):
    """Question 2 — what conflict was detected?"""

    def setUp(self) -> None:
        self.analyzer = ConflictAnalyzer()
        self.planner = UtilityPlanner(DEFAULT_POLICIES)

    def test_three_way_conflict_in_emergency_low_battery(self):
        # Emergency + low battery + human nearby: time wants EMERGENCY_RUSH,
        # energy wants ENERGY_SAVE, safety wants CAUTIOUS_EXPLORE.
        ctx = make_context(mission_priority="emergency", battery_level=0.15,
                           human_proximity=0.8)
        decision = self.planner.make_decision(ctx, QAWeights(0.4, 0.4, 0.2))
        detected, qas, _, three_way = self.analyzer.analyze(
            decision, QAWeights(0.4, 0.4, 0.2))
        self.assertTrue(detected)
        self.assertTrue(three_way)
        self.assertEqual(qas.count(" vs "), 2)

    def test_champions_cover_every_qa(self):
        ctx = make_context()
        decision = self.planner.make_decision(ctx, QAWeights(0.5, 0.3, 0.2))
        champions = self.analyzer.qa_champions(decision)
        self.assertEqual(set(champions.keys()), set(QA_NAMES))


class TestGapDecompositionInvariants(unittest.TestCase):
    """The algebraic heart of AURA: decomposition must be EXACT."""

    def setUp(self) -> None:
        self.planner = UtilityPlanner(DEFAULT_POLICIES)
        self.dominant = DominantQAAnalyzer()
        self.tradeoff = TradeoffAnalyzer()

    def _grid(self):
        """A small but adversarial grid of weights x contexts."""
        weight_grid = [QAWeights(0.6, 0.3, 0.1), QAWeights(0.2, 0.6, 0.2),
                       QAWeights(0.1, 0.1, 0.8), QAWeights(0.4, 0.4, 0.2),
                       QAWeights(1.0, 0.0, 0.0)]
        context_grid = itertools.product(
            [0.1, 0.35, 0.9],            # battery
            [0.5, 1.5, 5.0],             # human proximity
            [0.1, 0.9],                  # obstacle density
            [0.3, 0.9],                  # localization
            ["normal", "urgent", "emergency"],
        )
        for weights in weight_grid:
            for b, h, o, l, m in context_grid:
                yield weights, make_context(
                    battery_level=b, human_proximity=h, obstacle_density=o,
                    localization_confidence=l, mission_priority=m)

    def test_decomposition_sums_to_gap_exactly(self):
        for weights, ctx in self._grid():
            decision = self.planner.make_decision(ctx, weights)
            parts = DominantQAAnalyzer.decompose(decision, weights)
            gap = decision.selected.score - decision.runner_up.score
            self.assertAlmostEqual(sum(parts.values()), gap, places=9,
                                   msg=f"weights={weights} ctx={ctx}")

    def test_benefit_minus_cost_equals_gap_exactly(self):
        for weights, ctx in self._grid():
            decision = self.planner.make_decision(ctx, weights)
            benefit, _, cost, _, _ = self.tradeoff.analyze(decision, weights)
            gap = decision.selected.score - decision.runner_up.score
            self.assertAlmostEqual(benefit - cost, gap, places=9,
                                   msg=f"weights={weights} ctx={ctx}")
            self.assertGreaterEqual(benefit, 0.0)
            self.assertGreaterEqual(cost, 0.0)

    def test_dominant_qa_has_largest_contribution(self):
        for weights, ctx in self._grid():
            decision = self.planner.make_decision(ctx, weights)
            dominant, _, _, parts = self.dominant.analyze(decision, weights)
            self.assertEqual(parts[dominant], max(parts.values()))


class TestExplanationEngine(unittest.TestCase):
    """The orchestrator: end-to-end explanation properties."""

    def setUp(self) -> None:
        self.engine = ExplanationEngine()
        self.planner = UtilityPlanner(DEFAULT_POLICIES)

    def test_explanation_is_internally_consistent(self):
        ctx = make_context(human_proximity=0.8)
        weights = QAWeights(0.6, 0.3, 0.1)
        decision = self.planner.make_decision(ctx, weights)
        exp = self.engine.explain(decision, ctx, weights)
        self.assertEqual(exp.selected_policy, decision.selected.policy_name)
        self.assertAlmostEqual(exp.benefit_value - exp.cost_value,
                               exp.score_gap, places=9)
        self.assertAlmostEqual(sum(exp.gap_decomposition.values()),
                               exp.score_gap, places=5)
        self.assertIn(exp.selected_policy, exp.utility_scores)
        self.assertIn("AURA EXPLANATION", exp.explanation_text)

    def test_uncertain_flag_matches_threshold(self):
        ctx = make_context()
        weights = QAWeights(0.5, 0.3, 0.2)
        decision = self.planner.make_decision(ctx, weights)
        exp = self.engine.explain(decision, ctx, weights)
        self.assertEqual(exp.uncertain_decision, exp.score_gap < 0.1)

    def test_v10_public_interface_still_works(self):
        """The v1.0 per-question methods must keep their signatures."""
        ctx = make_context()
        weights = QAWeights(0.5, 0.3, 0.2)
        decision = self.planner.make_decision(ctx, weights)
        self.assertEqual(len(self.engine.detect_trigger(ctx, None, weights, None)), 4)
        self.assertEqual(len(self.engine.detect_conflict(decision, weights)), 4)
        self.assertEqual(len(self.engine.find_dominant_qa(decision, weights)), 3)
        self.assertEqual(len(self.engine.compute_tradeoff(decision, weights)), 4)
        self.assertEqual(
            len(self.engine.detect_transition(decision, "steady_state", ctx, None)), 6)


if __name__ == "__main__":
    unittest.main()
