import os
import subprocess
import tempfile
import unittest
from pathlib import Path


WRAPPER = Path(__file__).resolve().parents[1] / "engines" / "opencode-sandboxed.sh"
MODEL = "subq/subq-savant-1.4"
OP_REF = "op://Test/SubQ API/credential"
FAKE_KEY = "fake-subq-key"


class OpenCodeWrapperSubQTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.taskdir = self.root / "task"
        self.taskdir.mkdir()
        self.op_log = self.root / "op.log"
        self.env = {
            "PATH": str(self.root),
            "HOME": str(self.root),
            "OP_LOG": str(self.op_log),
            "FAKE_KEY": FAKE_KEY,
        }
        self.write_stub(
            "opencode",
            'printf "KEY=[%s]\\n" "${SUBQ_API_KEY:-}"\n'
            'for arg; do printf "ARG=[%s]\\n" "$arg"; done\n',
        )
        self.write_stub(
            "op",
            'printf "[%s]\\n" "$@" >> "$OP_LOG" || exit 1\n'
            'if [ "${OP_FAIL:-}" = "1" ]; then\n'
            '  printf "%s\\n" "$FAKE_KEY" >&2\n'
            '  exit 1\n'
            'fi\n'
            'printf "%s\\n\\n" "$FAKE_KEY"\n',
        )

    def write_stub(self, name, body):
        stub = self.root / name
        stub.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        stub.chmod(0o755)

    def run_wrapper(self, *args, sandboxed=False):
        command = ["/bin/bash", str(WRAPPER), str(self.taskdir)]
        env = self.env.copy()
        if sandboxed:
            env["PATH"] += ":/usr/bin:/bin"
        else:
            command.append("--no-sandbox")
        return subprocess.run(
            [*command, *args], env=env, capture_output=True, text=True, timeout=10
        )

    def assert_opencode(self, result, key, args):
        self.assertEqual(result.returncode, 0, result.stderr)
        expected_args = [f"ARG=[{arg}]" for arg in args]
        self.assertEqual(result.stdout.splitlines(), [f"KEY=[{key}]", *expected_args])
        self.assertEqual(result.stderr, "")

    def assert_op_called_once(self):
        self.assertEqual(self.op_log.read_text(encoding="utf-8"), f"[read]\n[{OP_REF}]\n")

    def assert_wrapper_error(self, result, *words):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        for word in words:
            self.assertIn(word, result.stderr)
        self.assertNotIn(FAKE_KEY, result.stderr)

    def test_reads_subq_key_and_preserves_arguments(self):
        self.env.update(SUBQ_OP_REF=OP_REF, SUBQ_API_KEY="")
        for model_args in [("-m", MODEL), ("--model", MODEL), (f"--model={MODEL}",)]:
            with self.subTest(model_args=model_args):
                self.op_log.unlink(missing_ok=True)
                args = ("run", *model_args, "one prompt with spaces *", "")
                self.assert_opencode(self.run_wrapper(*args), FAKE_KEY, args)
                self.assert_op_called_once()

    def test_preset_key_skips_op(self):
        self.env.update(SUBQ_API_KEY="preset-key", SUBQ_OP_REF=OP_REF)
        args = ("run", "-m", MODEL)
        self.assert_opencode(self.run_wrapper(*args), "preset-key", args)
        self.assertFalse(self.op_log.exists())

    def test_non_subq_model_skips_op(self):
        self.env["SUBQ_OP_REF"] = OP_REF
        args = ("run", "-m", "other/subq-savant-1.4")
        self.assert_opencode(self.run_wrapper(*args), "", args)
        self.assertFalse(self.op_log.exists())

    def test_model_argument_after_separator_skips_op(self):
        self.env["SUBQ_OP_REF"] = OP_REF
        args = ("run", "--", f"--model={MODEL}")
        self.assert_opencode(self.run_wrapper(*args), "", args)
        self.assertFalse(self.op_log.exists())

    def test_missing_reference_names_both_variables(self):
        for reference in (None, ""):
            with self.subTest(reference=reference):
                if reference is not None:
                    self.env["SUBQ_OP_REF"] = reference
                result = self.run_wrapper("run", "-m", MODEL)
                self.assert_wrapper_error(result, "SUBQ_API_KEY", "SUBQ_OP_REF")
                self.assertFalse(self.op_log.exists())

    def test_missing_op_names_1password_cli(self):
        self.env["SUBQ_OP_REF"] = OP_REF
        (self.root / "op").unlink()
        result = self.run_wrapper("run", "-m", MODEL)
        self.assert_wrapper_error(result, "1Password", " op ")
        self.assertFalse(self.op_log.exists())

    def test_failed_op_read_names_reference_variable(self):
        self.env.update(SUBQ_OP_REF=OP_REF, OP_FAIL="1")
        result = self.run_wrapper("run", "-m", MODEL)
        self.assert_wrapper_error(result, "SUBQ_OP_REF")
        self.assert_op_called_once()

    @unittest.skipUnless(os.path.exists("/usr/bin/sandbox-exec"), "requires sandbox-exec")
    def test_reads_subq_key_before_entering_sandbox(self):
        self.env["SUBQ_OP_REF"] = OP_REF
        args = ("run", "-m", MODEL)
        self.assert_opencode(self.run_wrapper(*args, sandboxed=True), FAKE_KEY, args)
        self.assert_op_called_once()
