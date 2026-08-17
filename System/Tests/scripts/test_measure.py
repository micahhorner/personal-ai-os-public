"""Tests for `aios measure` — the transcript job (spec §4, ingest-and-connect 3a).

Every fixture here is synthetic. This vault is the generic master
(instance_role: generic-master) and personal data is prohibited in it, so the
real transcript that motivated the command is never committed as a fixture;
it is validated against separately, in the owner's instance, and recorded in
the Phase E report.
"""
import os
import sys
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report                       # noqa: E402
from cmd import measure as m                        # noqa: E402


class Args:
    json = False
    target = None
    terms = None
    extract = None


def run_on(text, **kw):
    """Measure a transcript written to a temp file inside the real vault root,
    so the profile/manifest lookups are the shipped ones."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=tempfile.gettempdir())
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    a = Args()
    a.target = path
    for k, v in kw.items():
        setattr(a, k, v)
    rep = Report("measure")
    m.run(VAULT, a, rep)
    os.unlink(path)
    return rep


BASIC = """## You

One two three four five.

## ChatGPT

Six seven eight nine ten eleven twelve thirteen fourteen fifteen.
"""


class TestVoiceSplit(unittest.TestCase):
    def test_counts_each_voice(self):
        rep = run_on(BASIC)
        self.assertTrue(rep.ok)
        self.assertIn("5 (33%)", rep.info["words_human"])
        self.assertIn("10 (67%)", rep.info["words_assistant"])

    def test_emits_the_source_note_line_ingest_3a_asks_for(self):
        rep = run_on(BASIC)
        self.assertEqual(rep.info["source_note_line"],
                         "- words: human 5 · assistant 10 (human 33%)")

    def test_warns_when_the_human_share_is_small(self):
        """The condition that produced DEC-063: an assistant outweighing the
        human several-to-one dominates any whole-transcript reading."""
        rep = run_on("## You\n\nOne two.\n\n## ChatGPT\n\n" + "word " * 100)
        self.assertTrue(any("read his turns in ISOLATION" in w for w in rep.warnings))

    def test_no_warning_when_the_split_is_balanced(self):
        rep = run_on(BASIC.replace("Six seven eight nine ten eleven twelve thirteen fourteen fifteen.",
                                   "Six seven four five."))
        self.assertEqual(rep.warnings, [])

    def test_recognises_human_assistant_dialect(self):
        rep = run_on("## Human\n\nA b c.\n\n## Assistant\n\nD e.\n")
        self.assertIn("3", rep.info["words_human"])
        self.assertIn("2", rep.info["words_assistant"])

    def test_no_markers_is_an_error_not_a_silent_zero(self):
        rep = run_on("Just a plain document with nobody speaking.\n")
        self.assertFalse(rep.ok)
        self.assertIn("no voice markers", rep.errors[0])


class TestThirdVoiceTrap(unittest.TestCase):
    """A pasted article inside a human turn is neither voice. Crediting it to him
    inflates his share and puts another person's thesis in his mouth."""

    QUOTED = """## You

My own two words.

> This is a long pasted article by somebody else entirely and it goes on.

## ChatGPT

Reply here.
"""

    def test_blockquoted_paste_is_credited_to_no_speaker(self):
        rep = run_on(self.QUOTED)
        self.assertIn("4", rep.info["words_human"])          # "My own two words"
        self.assertIn("credited to NO speaker", rep.info["words_quoted_third_voice"])

    def test_quoted_words_are_not_added_to_any_voice(self):
        rep = run_on(self.QUOTED)
        human = int(rep.info["words_human"].split()[0])
        self.assertEqual(human, 4, "the pasted article must not count as his")

    def test_a_turn_that_is_only_a_paste_is_not_substantive(self):
        rep = run_on("## You\n\n> Only a paste, no words of his own here.\n\n"
                     "## ChatGPT\n\nOne two.\n")
        self.assertIn("0 substantive of 1 marked", rep.info["turns_human"])


class TestFences(unittest.TestCase):
    def test_colon_fence_content_belongs_to_the_speaker(self):
        """The ChatGPT export wraps its drafts in `:::writing`. Treating that as
        a third voice cost the assistant ~7,400 of its own words on the first run."""
        rep = run_on("## You\n\nOne.\n\n## ChatGPT\n\n:::writing\nTwo three four five.\n:::\n")
        self.assertIn("4", rep.info["words_assistant"])

    def test_a_voice_marker_inside_a_fence_is_not_a_turn(self):
        rep = run_on("## You\n\nOne.\n\n## ChatGPT\n\n```\n## You\nfake turn\n```\n")
        self.assertIn("1 substantive of 1 marked", rep.info["turns_human"])


class TestAnnotationBlock(unittest.TestCase):
    """The vault's own header about a source is nobody's turn — and it discusses
    the transcript in the transcript's vocabulary, so scanning it gives a term
    the wrong origin."""

    ANNOTATED = """# Random Ideas Capture (export)
- origin: an export, downloaded 2026-07-14
- note: the assistant coined the phrase widget tax in this chat

---

## You

I had an idea about backlogs.

## ChatGPT

Call it the widget tax.
"""

    def test_annotation_is_excluded_from_counts(self):
        rep = run_on(self.ANNOTATED)
        self.assertIn("annotation_excluded", rep.info)
        self.assertIn("5", rep.info["words_human"])   # only his turn

    def test_term_origin_ignores_the_annotation(self):
        """The regression that mattered: 'widget tax' appears first in the
        vault's own note ABOUT the coinage. Scanning it would report the term as
        pre-existing and clear the very coinage the check exists to catch."""
        rep = run_on(self.ANNOTATED, terms="widget tax")
        self.assertIn("first said by assistant", rep.info["term_origin"][0])


class TestTermOrigin(unittest.TestCase):
    """The check that caught 11 of 18 note titles built on the assistant's coinages."""

    TRANSCRIPT = """## You

I think the backlog matters.

## ChatGPT

That is the legibility tax at work.

## You

Yes, the legibility tax exactly.
"""

    def test_attributes_a_coinage_to_the_assistant_who_said_it_first(self):
        rep = run_on(self.TRANSCRIPT, terms="legibility tax")
        self.assertIn("first said by assistant", rep.info["term_origin"][0])

    def test_attributes_the_humans_own_word_to_him(self):
        rep = run_on(self.TRANSCRIPT, terms="backlog")
        self.assertIn("first said by human", rep.info["term_origin"][0])

    def test_missing_term_says_so(self):
        rep = run_on(self.TRANSCRIPT, terms="nonexistent phrase")
        self.assertIn("not found", rep.info["term_origin"][0])

    def test_multiple_terms(self):
        rep = run_on(self.TRANSCRIPT, terms="legibility tax, backlog")
        self.assertEqual(len(rep.info["term_origin"]), 2)


class TestExtract(unittest.TestCase):
    def _vault(self, tmp):
        os.makedirs(os.path.join(tmp, "System", "Runtime Profiles"), exist_ok=True)
        with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as stream:
            stream.write("runtime:\n  ai_writes_enabled: true\n"
                         "  active_profile: System/Runtime Profiles/p.yaml\n"
                         "protected_objects:\n"
                         "  - SYSTEM-MANIFEST.yaml\n"
                         "  - System/Runtime Profiles/\n"
                         "  - 80 User/privacy*\n")
        with open(os.path.join(tmp, "System", "Runtime Profiles", "p.yaml"), "w") as stream:
            stream.write("hosted: false\n")
        source = os.path.join(tmp, "transcript.md")
        with open(source, "w", encoding="utf-8") as stream:
            stream.write(TestThirdVoiceTrap.QUOTED)
        return source

    def _run(self, tmp, output):
        source = self._vault(tmp)
        args = Args()
        args.target = source
        args.extract = output
        rep = Report("measure")
        m.run(tmp, args, rep)
        return rep

    def test_writes_only_the_humans_own_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._run(tmp, "00 Inbox/isolated.md")
            self.assertTrue(rep.ok)
            out = os.path.join(tmp, "00 Inbox", "isolated.md")
            with open(out, encoding="utf-8") as stream:
                body = stream.read()
            self.assertIn("My own two words", body)
            self.assertNotIn("pasted article", body)   # third voice excluded
            self.assertNotIn("Reply here", body)       # assistant excluded

    def test_absolute_output_is_refused_without_external_write(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            dest = os.path.join(outside, "isolated.md")
            rep = self._run(tmp, dest)
            self.assertFalse(rep.ok)
            self.assertIn("contained relative", " ".join(rep.errors))
            self.assertFalse(os.path.exists(dest))

    def test_parent_traversal_output_is_refused(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = os.path.join(outer, "vault")
            os.makedirs(tmp)
            rep = self._run(tmp, "../escaped.md")
            self.assertFalse(rep.ok)
            self.assertIn("contained relative", " ".join(rep.errors))
            self.assertFalse(os.path.exists(os.path.join(outer, "escaped.md")))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_symlink_output_parent_is_refused_without_external_write(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            self._vault(tmp)
            os.symlink(outside, os.path.join(tmp, "redirect"))
            args = Args()
            args.target = "transcript.md"
            args.extract = "redirect/isolated.md"
            rep = Report("measure")
            m.run(tmp, args, rep)
            self.assertFalse(rep.ok)
            self.assertIn("symlink", " ".join(rep.errors).lower())
            self.assertEqual([], os.listdir(outside))

    def test_case_collision_output_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            os.makedirs(os.path.join(tmp, "Results"))
            args = Args()
            args.target = "transcript.md"
            args.extract = "results/isolated.md"
            rep = Report("measure")
            m.run(tmp, args, rep)
            self.assertFalse(rep.ok)
            self.assertIn("collision", " ".join(rep.errors).lower())

    def test_unicode_collision_output_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            os.makedirs(os.path.join(tmp, "Cafe\u0301"))
            args = Args()
            args.target = "transcript.md"
            args.extract = "Caf\u00e9/isolated.md"
            rep = Report("measure")
            m.run(tmp, args, rep)
            self.assertFalse(rep.ok)
            self.assertIn("collision", " ".join(rep.errors).lower())

    def test_existing_output_is_refused_and_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            os.makedirs(os.path.join(tmp, "00 Inbox"))
            dest = os.path.join(tmp, "00 Inbox", "isolated.md")
            with open(dest, "wb") as stream:
                stream.write(b"keep exactly\n")
            rep = self._run(tmp, "00 Inbox/isolated.md")
            self.assertFalse(rep.ok)
            self.assertIn("already exists", " ".join(rep.errors))
            with open(dest, "rb") as stream:
                self.assertEqual(b"keep exactly\n", stream.read())


class TestContentNeverReachesStdout(unittest.TestCase):
    """The privacy contract: measurements are facts ABOUT the text and may be
    returned; the text itself never is. This is what lets the command measure a
    Local Only transcript (DEC-065) that its hosted caller may not read."""

    def test_report_carries_no_transcript_text(self):
        rep = run_on("## You\n\nDistinctivesecretphrase here.\n\n## ChatGPT\n\nReply.\n")
        blob = repr(rep.info) + repr(rep.warnings) + repr(rep.errors)
        self.assertNotIn("Distinctivesecretphrase", blob)

    def test_term_origin_returns_no_surrounding_text(self):
        rep = run_on("## You\n\nfoo.\n\n## ChatGPT\n\nThe term here plus othersecretword.\n",
                     terms="term")
        blob = repr(rep.info["term_origin"])
        self.assertNotIn("othersecretword", blob)


class TestConfigurableVoiceMarkers(unittest.TestCase):
    """DEC-109 — the human-voice labels are user-owned config, not shipped code.

    SEEDED FAILURE: every assertion here fails against the pre-fix measure.py.
    `test_no_personal_identifier_in_shipped_patterns` fails because the shipped
    regex carried a real given name; the alias tests fail because there was no
    config surface at all, so a user's own speaker label could not be taught.
    """

    def _vault(self, tmp, config=None):
        """A minimal vault root: a manifest measure can read a profile from,
        plus an optional 80 User hook."""
        os.makedirs(os.path.join(tmp, "80 User"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "System", "Runtime Profiles"), exist_ok=True)
        with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as stream:
            stream.write("system: {system_version: 0.0.0}\n"
                         "runtime: {active_profile: System/Runtime Profiles/p.yaml}\n")
        with open(os.path.join(tmp, "System", "Runtime Profiles", "p.yaml"), "w") as stream:
            stream.write("hosted: true\n")
        if config is not None:
            with open(os.path.join(tmp, m.CONFIG_REL.replace("/", os.sep)
                                   if os.sep in m.CONFIG_REL else m.CONFIG_REL), "w") as stream:
                stream.write(config)
        return tmp

    def _measure(self, tmp, text, **kw):
        path = os.path.join(tmp, "t.md")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)
        a = Args()
        a.target = "t.md"
        for k, v in kw.items():
            setattr(a, k, v)
        rep = Report("measure")
        m.run(tmp, a, rep)
        return rep

    def test_no_personal_identifier_in_shipped_patterns(self):
        """The shipped vocabulary is generic. A name in it is personal data in a
        tree whose manifest forbids personal data."""
        import re as _re
        shipped = " ".join(p for p, _ in m.VOICE_PATTERNS).lower()
        for generic in ("you", "human", "user", "me", "assistant"):
            self.assertIn(generic, shipped)
        # Every alternative in the shipped patterns must be a ROLE word, not a
        # name. Asserted as a whitelist rather than by naming the identifier that
        # used to be here — a test that spells the name reintroduces it.
        allowed = {"you", "human", "user", "me", "chatgpt", "assistant", "claude",
                   "ai", "gpt"}
        words = set(_re.findall(r"[a-z]{2,}", _re.sub(r"\\[sd*+?]|gpt-\\?", " ", shipped)))
        self.assertTrue(words <= allowed,
                        f"non-role tokens in the shipped voice vocabulary: {words - allowed}")

    def test_unconfigured_vault_uses_shipped_defaults_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            rep = self._measure(tmp, BASIC)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("shipped defaults", rep.info["voice_markers"])
            self.assertEqual(rep.info["voices"], "assistant, human")

    def test_configured_alias_is_attributed_to_the_human(self):
        """The behaviour the hardcoded name provided, now earned by config."""
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, "human: [alex]\n")
            rep = self._measure(tmp, "## Alex\n\nOne two three.\n\n## ChatGPT\n\nFour five.\n")
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["voices"], "assistant, human")
            self.assertIn("words_human", rep.info)
            self.assertIn("alex", rep.info["voice_markers"])

    def test_unconfigured_alias_is_not_a_turn(self):
        """Without the hook, a personal label is not a marker — which is exactly
        why removing the name outright was refused and configuration chosen."""
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            rep = self._measure(tmp, "## Alex\n\nOne two three.\n\n## ChatGPT\n\nFour five.\n")
            self.assertEqual(rep.info["voices"], "assistant")

    def test_alias_also_works_in_bold_dialect(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, "human: [alex]\n")
            rep = self._measure(tmp, "**Alex**\n\nOne two three.\n\n**ChatGPT**\n\nFour five.\n")
            self.assertEqual(rep.info["voices"], "assistant, human")

    def test_assistant_aliases_are_configurable_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, "assistant: [copilot]\n")
            rep = self._measure(tmp, "## You\n\nOne two.\n\n## Copilot\n\nThree four five.\n")
            self.assertEqual(rep.info["voices"], "assistant, human")

    def test_malformed_config_is_reported_never_fatal(self):
        """A silently ignored config is worse than none: the caller would read a
        split computed with markers they believe they replaced."""
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, "human: [alex\n  bad: ][\n")
            rep = self._measure(tmp, BASIC)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("IGNORED", rep.info["voice_markers"])

    def test_config_is_not_a_regex_injection_surface(self):
        """Labels are escaped and shape-checked; a user's typo cannot corrupt
        the marker set or crash the run."""
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, 'human: ["(((", "alex"]\n')
            rep = self._measure(tmp, "## Alex\n\nOne two three.\n\n## ChatGPT\n\nFour five.\n")
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["voices"], "assistant, human")
            self.assertIn("rejected", rep.info["voice_markers"])

    def test_annotation_split_honours_configured_markers(self):
        """The split runs before parsing; a marker the splitter cannot see
        reclassifies the whole file, so it must use the same set."""
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp, "human: [alex]\n")
            rep = self._measure(
                tmp, "Vault annotation about the source.\n\n---\n\n"
                     "## Alex\n\nOne two three.\n\n## ChatGPT\n\nFour five.\n")
            self.assertEqual(rep.info["voices"], "assistant, human")
            self.assertIn("annotation_excluded", rep.info)


if __name__ == "__main__":
    unittest.main()
