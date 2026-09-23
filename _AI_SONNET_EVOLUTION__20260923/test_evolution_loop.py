"""Tests for evolution_loop.py.

stdlib ``unittest`` only, no third-party dependencies, no network access, no
real repository content. Run with either:

    python -m unittest test_evolution_loop -v
    pytest test_evolution_loop.py -v

Every test creates its own temp directories and cleans them up; nothing here
writes outside the OS temp directory.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import evolution_loop as el


def make_fixture_tree(root: Path) -> None:
    """A tiny synthetic repo: one module with a test, one module without."""

    (root / "pkg").mkdir(parents=True, exist_ok=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "covered.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "pkg" / "test_covered.py").write_text(
        "import unittest\nfrom covered import f\n\nclass T(unittest.TestCase):\n"
        "    def test_f(self):\n        self.assertEqual(f(), 1)\n",
        encoding="utf-8",
    )
    (root / "pkg" / "uncovered.py").write_text("def g():\n    return 2\n", encoding="utf-8")


class CanonicalHashingTests(unittest.TestCase):
    def test_canonical_json_is_order_independent(self) -> None:
        a = el.canonical_json({"b": 1, "a": 2})
        b = el.canonical_json({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_content_hash_stable_for_equal_structures(self) -> None:
        self.assertEqual(el.content_hash({"x": [1, 2, 3]}), el.content_hash({"x": [1, 2, 3]}))

    def test_content_hash_changes_with_content(self) -> None:
        self.assertNotEqual(el.content_hash({"x": 1}), el.content_hash({"x": 2}))


class SandboxGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rejects_parent_traversal(self) -> None:
        with self.assertRaises(el.SandboxEscape):
            el.resolve_within(self.tmp, "../outside.txt")

    def test_rejects_absolute_path(self) -> None:
        with self.assertRaises(el.SandboxEscape):
            el.resolve_within(self.tmp, "/etc/passwd")

    def test_allows_nested_relative_path(self) -> None:
        result = el.resolve_within(self.tmp, "a/b/c.txt")
        self.assertTrue(str(result).startswith(str(self.tmp.resolve())))


class ObserveProposeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        make_fixture_tree(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_untested_module_only(self) -> None:
        untested = el.find_untested_modules(self.tmp)
        self.assertIn("uncovered", untested)
        self.assertNotIn("covered", untested)

    def test_observe_never_reads_file_contents(self) -> None:
        observations = el.observe(self.tmp)
        self.assertTrue(observations)
        for obs in observations:
            self.assertNotIn("def g()", json.dumps(obs.evidence))

    def test_propose_is_deterministic_given_same_observations(self) -> None:
        observations = el.observe(self.tmp)
        p1 = el.propose(observations)
        p2 = el.propose(observations)
        self.assertEqual(
            [p.proposal_id for p in p1],
            [p.proposal_id for p in p2],
        )
        self.assertEqual(
            [p.content_fields() for p in p1],
            [p.content_fields() for p in p2],
        )

    def test_empty_repo_yields_no_observations(self) -> None:
        empty = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(el.observe(empty), [])
        finally:
            shutil.rmtree(empty, ignore_errors=True)


def _base_ctx(**overrides) -> el.PrioritizeContext:
    defaults = dict(
        current_baseline_hash="baseline-x",
        max_cost_units=1.0,
        min_reversibility=0.5,
        ledger_terminal_proposal_ids=frozenset(),
    )
    defaults.update(overrides)
    return el.PrioritizeContext(**defaults)


def _make_proposal(**overrides) -> el.ImprovementProposal:
    defaults = dict(
        proposal_id="prop-test",
        title="t",
        category="test_coverage",
        evidence={"target_module": "x"},
        value=0.6,
        risk=0.1,
        cost=0.2,
        reversibility=0.95,
        confidence=0.7,
        requested_autonomy=el.AutonomyLevel.L2_ISOLATED,
        baseline_hash="baseline-x",
        source_observation_id="obs-1",
        created_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return el.ImprovementProposal(**defaults)


class HardVetoTests(unittest.TestCase):
    def test_clean_proposal_has_no_vetoes(self) -> None:
        reasons = el.apply_hard_vetoes(_make_proposal(), _base_ctx())
        self.assertEqual(reasons, ())

    def test_veto_autonomy_above_ceiling(self) -> None:
        p = _make_proposal(requested_autonomy=el.AutonomyLevel.L4_EXTERNAL_ACTION)
        reasons = el.apply_hard_vetoes(p, _base_ctx())
        self.assertTrue(any("autonomy" in r for r in reasons))

    def test_veto_forbidden_category(self) -> None:
        p = _make_proposal(category="client_evidence")
        reasons = el.apply_hard_vetoes(p, _base_ctx())
        self.assertTrue(any("forbidden" in r for r in reasons))

    def test_veto_all_forbidden_categories(self) -> None:
        for category in el.FORBIDDEN_CATEGORIES:
            p = _make_proposal(category=category)
            reasons = el.apply_hard_vetoes(p, _base_ctx())
            self.assertTrue(reasons, f"category {category} should be vetoed")

    def test_veto_low_reversibility(self) -> None:
        p = _make_proposal(reversibility=0.1)
        reasons = el.apply_hard_vetoes(p, _base_ctx(min_reversibility=0.8))
        self.assertTrue(any("reversibility" in r for r in reasons))

    def test_veto_low_confidence_high_risk(self) -> None:
        p = _make_proposal(confidence=0.1, risk=0.9)
        reasons = el.apply_hard_vetoes(p, _base_ctx())
        self.assertTrue(any("confidence" in r for r in reasons))

    def test_veto_budget_exceeded(self) -> None:
        p = _make_proposal(cost=0.9)
        reasons = el.apply_hard_vetoes(p, _base_ctx(max_cost_units=0.5))
        self.assertTrue(any("cost" in r for r in reasons))

    def test_veto_stale_baseline(self) -> None:
        p = _make_proposal(baseline_hash="stale")
        reasons = el.apply_hard_vetoes(p, _base_ctx(current_baseline_hash="fresh"))
        self.assertTrue(any("baseline" in r for r in reasons))

    def test_veto_duplicate_terminal_proposal(self) -> None:
        p = _make_proposal(proposal_id="prop-dup")
        ctx = _base_ctx(ledger_terminal_proposal_ids=frozenset({"prop-dup"}))
        reasons = el.apply_hard_vetoes(p, ctx)
        self.assertTrue(any("terminal receipt" in r for r in reasons))

    def test_veto_out_of_bounds_value(self) -> None:
        p = _make_proposal(value=1.5)
        reasons = el.apply_hard_vetoes(p, _base_ctx())
        self.assertTrue(any("out of bounds" in r for r in reasons))

    def test_prioritize_sorts_eligible_first_then_by_score(self) -> None:
        good = _make_proposal(proposal_id="prop-good", value=0.9)
        bad = _make_proposal(proposal_id="prop-bad", category="client_evidence")
        ranked = el.prioritize([bad, good], _base_ctx())
        self.assertEqual(ranked[0].proposal.proposal_id, "prop-good")
        self.assertTrue(ranked[0].eligible)
        self.assertFalse(ranked[1].eligible)


class AuthorizeAndEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_authorize_never_exceeds_l2(self) -> None:
        p = el.PrioritizedProposal(proposal=_make_proposal(), score=1.0, veto_reasons=())
        auth = el.authorize(p, self.tmp)
        self.assertEqual(auth.autonomy_level, el.AutonomyLevel.L2_ISOLATED)
        self.assertLessEqual(el.autonomy_rank(auth.autonomy_level), el.autonomy_rank(el.MAX_AUTONOMY_LEVEL))

    def test_authorize_refuses_vetoed_proposal(self) -> None:
        p = el.PrioritizedProposal(proposal=_make_proposal(), score=1.0, veto_reasons=("nope",))
        with self.assertRaises(el.EvolutionLoopError):
            el.authorize(p, self.tmp)

    def test_authorize_refuses_above_ceiling_request(self) -> None:
        proposal = _make_proposal(requested_autonomy=el.AutonomyLevel.L3_PRIVATE_CANARY)
        p = el.PrioritizedProposal(proposal=proposal, score=1.0, veto_reasons=())
        with self.assertRaises(el.EvolutionLoopError):
            el.authorize(p, self.tmp)

    def test_authorization_single_use(self) -> None:
        p = el.PrioritizedProposal(proposal=_make_proposal(), score=1.0, veto_reasons=())
        auth = el.authorize(p, self.tmp)
        auth.consume()
        with self.assertRaises(el.AuthorizationReuse):
            auth.consume()

    def test_authorization_expiry(self) -> None:
        p = el.PrioritizedProposal(proposal=_make_proposal(), score=1.0, veto_reasons=())
        auth = el.authorize(p, self.tmp, ttl_seconds=0.01)
        time.sleep(0.05)
        self.assertTrue(auth.is_expired())

    def test_envelope_is_bound_to_hashes(self) -> None:
        proposal = _make_proposal()
        p = el.PrioritizedProposal(proposal=proposal, score=1.0, veto_reasons=())
        auth = el.authorize(p, self.tmp)
        envelope = el.compile_task_envelope(proposal, auth)
        self.assertEqual(envelope.proposal_hash, proposal.proposal_hash)
        self.assertEqual(envelope.authorization_hash, auth.authorization_hash)
        self.assertEqual(envelope.allowlist_write, (str(self.tmp),))

    def test_envelope_hash_is_deterministic(self) -> None:
        proposal = _make_proposal()
        p = el.PrioritizedProposal(proposal=proposal, score=1.0, veto_reasons=())
        auth = el.authorize(p, self.tmp)
        e1 = el.compile_task_envelope(proposal, auth)
        e2 = el.compile_task_envelope(proposal, auth)
        self.assertEqual(e1.envelope_hash, e2.envelope_hash)


class BuildTestAdversarialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.proposal = _make_proposal()
        prioritized = el.PrioritizedProposal(proposal=self.proposal, score=1.0, veto_reasons=())
        self.authorization = el.authorize(prioritized, self.tmp)
        self.envelope = el.compile_task_envelope(self.proposal, self.authorization)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_writes_only_inside_sandbox(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        sandbox_dir = Path(artifact.sandbox_dir)
        self.assertTrue(str(sandbox_dir.resolve()).startswith(str(self.tmp.resolve())))
        for rel in artifact.files:
            self.assertTrue((sandbox_dir / rel).exists())

    def test_build_consumes_authorization(self) -> None:
        self.assertIsNone(self.authorization.consumed_at)
        el.build_synthetic_canary(self.envelope, self.authorization)
        self.assertIsNotNone(self.authorization.consumed_at)

    def test_build_refuses_reused_authorization(self) -> None:
        el.build_synthetic_canary(self.envelope, self.authorization)
        with self.assertRaises(el.AuthorizationReuse):
            el.build_synthetic_canary(self.envelope, self.authorization)

    def test_build_refuses_expired_authorization(self) -> None:
        prioritized = el.PrioritizedProposal(proposal=self.proposal, score=1.0, veto_reasons=())
        short_auth = el.authorize(prioritized, self.tmp, ttl_seconds=0.01)
        envelope = el.compile_task_envelope(self.proposal, short_auth)
        time.sleep(0.05)
        with self.assertRaises(el.EvolutionLoopError):
            el.build_synthetic_canary(envelope, short_auth)

    def test_synthetic_canary_never_contains_real_target_bytes(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        sandbox_dir = Path(artifact.sandbox_dir)
        text = (sandbox_dir / "synthetic_target.py").read_text(encoding="utf-8")
        self.assertIn("Provenance:", text)
        self.assertNotIn("import os", text)

    def test_canary_test_passes(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        outcome = el.run_canary_tests(artifact)
        self.assertTrue(outcome.passed, outcome.summary)

    def test_adversarial_probes_all_pass_on_clean_build(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        outcome = el.run_adversarial_probes(artifact, self.envelope, self.authorization)
        self.assertTrue(outcome.passed, [p for p in outcome.probes if not p.passed])

    def test_adversarial_secret_scan_flags_injected_secret(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        sandbox_dir = Path(artifact.sandbox_dir)
        poisoned = sandbox_dir / "synthetic_target.py"
        poisoned.write_text(
            poisoned.read_text(encoding="utf-8") + "\nAWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n",
            encoding="utf-8",
        )
        result = el._probe_secret_scan(
            el.BuildArtifact(
                build_id=artifact.build_id,
                envelope_id=artifact.envelope_id,
                sandbox_dir=artifact.sandbox_dir,
                files=artifact.files,
                git_commit=artifact.git_commit,
            )
        )
        self.assertFalse(result.passed)

    def test_rollback_rehearsal_removes_sandbox_without_residue(self) -> None:
        artifact = el.build_synthetic_canary(self.envelope, self.authorization)
        result = el._probe_rollback_rehearsal(artifact)
        self.assertTrue(result.passed, result.note)
        self.assertFalse(Path(artifact.sandbox_dir).exists())


class ReceiptLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.ledger_path = self.tmp / "receipts.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _receipt(self, state: el.TerminalState = el.TerminalState.NO_ELIGIBLE_PROPOSAL) -> el.Receipt:
        return el.build_receipt(
            cycle_id="cycle-test",
            terminal_state=state,
            previous_receipt_hash=None,
        )

    def test_append_and_verify_empty_then_nonempty(self) -> None:
        ledger = el.ReceiptLedger(self.ledger_path)
        self.assertTrue(ledger.verify_chain())
        ledger.append(self._receipt())
        self.assertTrue(ledger.verify_chain())
        ledger.append(self._receipt())
        self.assertTrue(ledger.verify_chain())

    def test_chain_breaks_on_tamper(self) -> None:
        ledger = el.ReceiptLedger(self.ledger_path)
        ledger.append(self._receipt())
        ledger.append(self._receipt())
        # Tamper: edit a byte inside the first line's receipt payload.
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        tampered = lines[0].replace("NO_ELIGIBLE_PROPOSAL", "PROMOTED_DRAFT_PR_ELIGIBLE")
        self.ledger_path.write_text("\n".join([tampered] + lines[1:]) + "\n", encoding="utf-8")

        tampered_ledger = el.ReceiptLedger(self.ledger_path)
        self.assertFalse(tampered_ledger.verify_chain())

    def test_append_refuses_when_chain_already_broken(self) -> None:
        ledger = el.ReceiptLedger(self.ledger_path)
        ledger.append(self._receipt())
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        tampered = lines[0].replace("NO_ELIGIBLE_PROPOSAL", "PROMOTED_DRAFT_PR_ELIGIBLE")
        self.ledger_path.write_text(tampered + "\n", encoding="utf-8")

        broken_ledger = el.ReceiptLedger(self.ledger_path)
        with self.assertRaises(el.AuditChainCompromised):
            broken_ledger.append(self._receipt())

    def test_terminal_proposal_ids_tracks_dedup(self) -> None:
        ledger = el.ReceiptLedger(self.ledger_path)
        proposal = _make_proposal(proposal_id="prop-dedupe")
        receipt = el.build_receipt(
            cycle_id="c1",
            terminal_state=el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE,
            previous_receipt_hash=None,
            proposal=proposal,
        )
        ledger.append(receipt)
        self.assertIn("prop-dedupe", ledger.terminal_proposal_ids())


class LearnStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.memory_path = self.tmp / "memory.jsonl"
        self.quarantine_path = self.tmp / "quarantine.jsonl"
        self.receipt = el.build_receipt(
            cycle_id="cycle-1",
            terminal_state=el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE,
            previous_receipt_hash=None,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unreviewed_record_is_quarantined_not_learned(self) -> None:
        record = el.learn(
            self.receipt, memory_path=self.memory_path, quarantine_path=self.quarantine_path
        )
        self.assertEqual(record.status, "quarantined")
        self.assertFalse(self.memory_path.exists())
        self.assertTrue(self.quarantine_path.exists())

    def test_reviewed_record_is_persisted_to_memory(self) -> None:
        record = el.learn(
            self.receipt,
            memory_path=self.memory_path,
            quarantine_path=self.quarantine_path,
            reviewed_by="human-reviewer",
            review_note="Coverage gap confirmed; canary pattern generalizes.",
        )
        self.assertEqual(record.status, "reviewed")
        self.assertEqual(record.lesson_summary, "Coverage gap confirmed; canary pattern generalizes.")
        self.assertTrue(self.memory_path.exists())

    def test_non_learnable_terminal_state_always_quarantined(self) -> None:
        receipt = el.build_receipt(
            cycle_id="cycle-2",
            terminal_state=el.TerminalState.AUDIT_CHAIN_COMPROMISED,
            previous_receipt_hash=None,
        )
        record = el.learn(
            receipt,
            memory_path=self.memory_path,
            quarantine_path=self.quarantine_path,
            reviewed_by="human-reviewer",
            review_note="anything",
        )
        self.assertEqual(record.status, "quarantined")

    def test_reviewed_by_without_note_is_still_quarantined(self) -> None:
        record = el.learn(
            self.receipt,
            memory_path=self.memory_path,
            quarantine_path=self.quarantine_path,
            reviewed_by="human-reviewer",
            review_note=None,
        )
        self.assertEqual(record.status, "quarantined")


class SingleCycleLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.lock_path = self.tmp / "cycle.lock"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_concurrent_lock_is_refused(self) -> None:
        lock1 = el.SingleCycleLock(self.lock_path)
        with lock1:
            lock2 = el.SingleCycleLock(self.lock_path)
            with self.assertRaises(el.CycleAlreadyRunning):
                with lock2:
                    pass

    def test_lock_released_after_context_exit(self) -> None:
        with el.SingleCycleLock(self.lock_path):
            pass
        self.assertFalse(self.lock_path.exists())

    def test_fence_token_increases_across_cycles(self) -> None:
        with el.SingleCycleLock(self.lock_path) as lock1:
            token1 = lock1.fence_token
        with el.SingleCycleLock(self.lock_path) as lock2:
            token2 = lock2.fence_token
        self.assertGreater(token2, token1)

    def test_stale_lock_can_be_taken_over(self) -> None:
        lock1 = el.SingleCycleLock(self.lock_path, stale_after_seconds=0.01)
        with lock1:
            pass
        # Manually recreate a "stuck" lock file older than the staleness window.
        self.lock_path.write_text("{}", encoding="utf-8")
        old_time = time.time() - 10
        import os

        os.utime(self.lock_path, (old_time, old_time))
        lock2 = el.SingleCycleLock(self.lock_path, stale_after_seconds=0.01)
        with lock2:
            pass  # should not raise


class FullCycleEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_tmp = Path(tempfile.mkdtemp())
        make_fixture_tree(self.repo_tmp)
        self.runtime_tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.repo_tmp, ignore_errors=True)
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def test_observe_propose_mode_performs_no_writes(self) -> None:
        before = list(self.runtime_tmp.rglob("*"))
        result = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="observe-propose")
        after = list(self.runtime_tmp.rglob("*"))
        self.assertEqual(before, after)
        self.assertIn(
            result.terminal_state,
            (el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE, el.TerminalState.NO_ELIGIBLE_PROPOSAL),
        )

    def test_full_cycle_on_synthetic_fixture_promotes_and_writes_receipt(self) -> None:
        result = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        self.assertEqual(result.terminal_state, el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE)
        self.assertTrue((self.runtime_tmp / "receipts.jsonl").exists())
        ledger = el.ReceiptLedger(self.runtime_tmp / "receipts.jsonl")
        self.assertTrue(ledger.verify_chain())

    def test_full_cycle_leaves_no_sandbox_residue_after_promotion(self) -> None:
        result = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        self.assertEqual(result.terminal_state, el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE)
        sandboxes = self.runtime_tmp / "sandboxes"
        remaining = [p for p in sandboxes.rglob("*") if p.is_file()] if sandboxes.exists() else []
        self.assertEqual(remaining, [], "rollback rehearsal should have removed all build files")

    def test_full_cycle_never_touches_source_repo(self) -> None:
        before = {p: p.read_bytes() for p in self.repo_tmp.rglob("*.py")}
        el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        after = {p: p.read_bytes() for p in self.repo_tmp.rglob("*.py")}
        self.assertEqual(before, after)

    def test_second_cycle_dedupes_the_same_proposal(self) -> None:
        first = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        self.assertEqual(first.terminal_state, el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE)
        second = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        self.assertEqual(second.terminal_state, el.TerminalState.VETOED)
        self.assertTrue(any("terminal receipt" in note for note in second.notes))

    def test_empty_repo_yields_no_eligible_proposal_terminal_state(self) -> None:
        empty_repo = Path(tempfile.mkdtemp())
        try:
            result = el.run_cycle(empty_repo, self.runtime_tmp, mode="full")
            self.assertEqual(result.terminal_state, el.TerminalState.NO_ELIGIBLE_PROPOSAL)
        finally:
            shutil.rmtree(empty_repo, ignore_errors=True)

    def test_cycle_result_serializes_to_json(self) -> None:
        result = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        payload = json.loads(result.to_json())
        self.assertEqual(payload["terminal_state"], "PROMOTED_DRAFT_PR_ELIGIBLE")
        self.assertIn("receipt", payload)

    def test_learning_record_quarantined_by_default_even_after_promotion(self) -> None:
        result = el.run_cycle(self.repo_tmp, self.runtime_tmp, mode="full")
        self.assertEqual(result.terminal_state, el.TerminalState.PROMOTED_DRAFT_PR_ELIGIBLE)
        self.assertIsNotNone(result.learning_record)
        self.assertEqual(result.learning_record.status, "quarantined")

    def test_learning_record_reviewed_when_review_supplied(self) -> None:
        result = el.run_cycle(
            self.repo_tmp,
            self.runtime_tmp,
            mode="full",
            reviewed_by="qa-lead",
            review_note="Synthetic canary pattern approved for reuse.",
        )
        self.assertEqual(result.learning_record.status, "reviewed")
        self.assertTrue((self.runtime_tmp / "learning_memory.jsonl").exists())


class CliTests(unittest.TestCase):
    def test_main_observe_propose_writes_nothing_and_returns_zero(self) -> None:
        repo_tmp = Path(tempfile.mkdtemp())
        try:
            make_fixture_tree(repo_tmp)
            out_path = repo_tmp / "out.json"
            rc = el.main(["--repo-root", str(repo_tmp), "--mode", "observe-propose", "--out", str(out_path)])
            self.assertEqual(rc, 0)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn(payload["terminal_state"], ("PROMOTED_DRAFT_PR_ELIGIBLE", "NO_ELIGIBLE_PROPOSAL"))
        finally:
            shutil.rmtree(repo_tmp, ignore_errors=True)

    def test_main_full_mode_uses_runtime_dir(self) -> None:
        repo_tmp = Path(tempfile.mkdtemp())
        runtime_tmp = Path(tempfile.mkdtemp())
        try:
            make_fixture_tree(repo_tmp)
            out_path = runtime_tmp / "out.json"
            rc = el.main(
                [
                    "--repo-root", str(repo_tmp),
                    "--mode", "full",
                    "--runtime-dir", str(runtime_tmp),
                    "--out", str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((runtime_tmp / "receipts.jsonl").exists())
        finally:
            shutil.rmtree(repo_tmp, ignore_errors=True)
            shutil.rmtree(runtime_tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
