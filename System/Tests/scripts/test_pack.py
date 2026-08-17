"""aios pack — the mechanical core of pack install/update/remove (determinism
audit finding 1, DEC-077 recovery ordering as executable law). Run:
    python3 -m unittest System.Tests.scripts.test_pack

`TestMalformedManifestsReportNeverCrash` is the trust-boundary suite (DEC-108):
a pack ZIP is a stranger's artifact, and every malformed shape in it must come
back as an actionable error with a non-zero exit and an unchanged tree — never
a traceback. Each case below crashed before v1.53.0.
"""
import hashlib
import json
import os, sys, subprocess, tempfile, unittest, zipfile

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)


def aios(tmp, *argv, auto_review=True):
    # Existing install-behaviour tests model the owner's verify → approve →
    # apply flow. Boundary tests can disable this to prove missing/stale review
    # authority refuses before writes.
    if (auto_review and argv and argv[0] == "pack" and "--apply" in argv
            and "--review-sha256" not in argv):
        verify_argv = [arg for arg in argv if arg not in ("--apply", "--confirm")]
        verified = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "aios.py"), *verify_argv,
             "--verify", "--json", "--root", tmp],
            capture_output=True, text=True,
        )
        try:
            review = json.loads(verified.stdout)["info"]["plan"]["review_sha256"]
            argv = (*argv, "--review-sha256", review)
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "aios.py"),
                           *argv, "--root", tmp], capture_output=True, text=True)


def _vault(tmp, writes=True):
    for d in ("System/Schemas", "System/Registries", "System/Journal",
              "System/Generated", "20 Knowledge"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    import shutil
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(tmp, "System", "Schemas"))
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write("system:\n  name: Test Vault\n  id: test-vault\n"
                "  instance_role: personal-instance\n"
                "  system_version: 1.32.0\n  vault_profile_version: 1.0.0\n"
                "runtime:\n  ai_writes_enabled: %s\n  active_profile: profile.yaml\n"
                % str(writes).lower())
    with open(os.path.join(tmp, "profile.yaml"), "w") as f:
        f.write("hosted: false\n")
    with open(os.path.join(tmp, "System", "Journal", "change-journal.md"), "w") as f:
        f.write("# J\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "seed"], cwd=tmp, capture_output=True)


GOOD_MANIFEST = """id: pack-demo
name: Demo
version: 1.0.0
kind: capability
summary: demo pack
license: MIT
source: https://example.com/demo
components: {capabilities: [capabilities/demo/SKILL.md]}
"""

SKILL = """---
id: capability-pack-demo
name: pack-demo
component_type: capability
type: capability
status: active
version: 0.1.0
summary: demo pack capability
tests: [none]
created: 2026-07-25
updated: 2026-07-25
---
# demo
"""


def _make_zip(root, fname="demo.zip", manifest=GOOD_MANIFEST, skill=SKILL):
    zp = os.path.join(root, fname)
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("pack.yaml", manifest)
        z.writestr("capabilities/demo/SKILL.md", skill)
    return zp


class TestVerify(unittest.TestCase):
    def test_good_manifest_passes_and_plans_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            r = aios(tmp, "pack", "--verify")
            self.assertIn("manifest gate PASSED", r.stdout)
            self.assertIn("INSTALL", r.stdout)

    def test_bad_manifest_rejected_seven_clauses(self):
        bad = GOOD_MANIFEST.replace("pack-demo", "Demo Pack!").replace(
            "1.0.0", "one").replace("kind: capability", "kind: mystery").replace(
            "https://example.com/demo", "ftp://x")
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp, manifest=bad)
            r = aios(tmp, "pack", "--verify")
            for frag in ("must match pack-", "not semver", "not in vocabulary", "https URL"):
                self.assertIn(frag, r.stdout)
            self.assertIn("REJECTED", r.stdout)

    def test_listed_path_missing_from_zip_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            zp = os.path.join(tmp, "demo.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("pack.yaml", GOOD_MANIFEST)   # lists a SKILL.md it doesn't carry
            r = aios(tmp, "pack", "--verify")
            self.assertIn("listed path missing", r.stdout)

    def test_missing_core_primitive_rejected(self):
        man = GOOD_MANIFEST + "depends_on: {core_primitives: [doc-never-shipped]}\n"
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp, manifest=man)
            r = aios(tmp, "pack", "--verify")
            self.assertIn("not present in this vault", r.stdout)

    def test_min_system_version_gate(self):
        man = GOOD_MANIFEST + "depends_on: {min_system_version: '99.0.0'}\n"
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp, manifest=man)
            r = aios(tmp, "pack", "--verify")
            self.assertIn("needs system 99.0.0", r.stdout)

    def test_exact_attached_license_passes_including_extensionless_name(self):
        body = b"private license bytes\n"
        digest = hashlib.sha256(body).hexdigest()
        man = GOOD_MANIFEST.replace(
            "license: MIT",
            "license:\n  file: LICENSE\n  sha256: " + digest,
        )
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                z.writestr("LICENSE", body)
                z.writestr("capabilities/demo/SKILL.md", SKILL)
            self.assertIn("manifest gate PASSED", aios(tmp, "pack", "--verify").stdout)

    def test_attached_license_symlink_is_rejected(self):
        body = b"target"
        digest = hashlib.sha256(body).hexdigest()
        man = GOOD_MANIFEST.replace(
            "license: MIT",
            "license:\n  file: LICENSE\n  sha256: " + digest,
        )
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                link = zipfile.ZipInfo("LICENSE")
                link.create_system = 3
                link.external_attr = (0o120777 << 16)
                z.writestr(link, "target")
                z.writestr("capabilities/demo/SKILL.md", SKILL)
            self.assertIn(
                "license file is not a regular file",
                aios(tmp, "pack", "--verify").stdout,
            )


class TestApplyAndRemove(unittest.TestCase):
    def test_install_places_pack_and_removes_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); zp = _make_zip(tmp)
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("INSTALL OK", r.stdout)
            self.assertTrue(os.path.exists(os.path.join(
                tmp, "Packs", "demo", "capabilities", "demo", "SKILL.md")))
            self.assertFalse(os.path.exists(zp))       # source ZIP cleaned up

    def test_apply_without_confirm_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            r = aios(tmp, "pack", "--apply")
            self.assertIn("--confirm", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs")))

    def test_kill_switch_blocks_apply_but_not_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp, writes=False); _make_zip(tmp)
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("kill switch", r.stdout)
            r2 = aios(tmp, "pack", "--verify")
            self.assertIn("manifest gate PASSED", r2.stdout)

    def test_update_replaces_never_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            aios(tmp, "pack", "--apply", "--confirm")
            stray = os.path.join(tmp, "Packs", "demo", "old-file.md")
            with open(stray, "w") as stream:
                stream.write("left over\n")
            _make_zip(tmp, manifest=GOOD_MANIFEST.replace("1.0.0", "1.1.0"))
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("UPDATE OK", r.stdout)
            self.assertFalse(os.path.exists(stray))    # full replacement

    def test_failed_validate_recovers_dec077_order(self):
        """A pack whose component fails validation must vanish again, and the
        verdict must come from post-recovery validate, not rollback's OK."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            # WHY THIS FAILS, corrected 2026-07-27: not a duplicate id. `Packs/`
            # is pruned from the canon walk (DEC-067), so `validate` never sees
            # the pack's copy and there is no duplicate to find. What it sees is
            # THIS seed note: `id: capability-pack-demo` on `type: note`, which
            # violates the id/type-prefix rule. The test is correct and its
            # subject — placement fails, DEC-077 recovery runs — is unaffected;
            # the comment described a mechanism that DEC-067 makes impossible.
            with open(os.path.join(tmp, "20 Knowledge", "seed.md"), "w") as stream:
                stream.write("---\nid: capability-pack-demo\ntype: note\nstatus: active\n"
                             "created: 2026-07-01\nupdated: 2026-07-01\nsummary: s\n---\nbody\n")
            _make_zip(tmp)
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("recovering per DEC-077", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs", "demo")))

    def test_remove_leaves_no_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            aios(tmp, "pack", "--apply", "--confirm")
            r = aios(tmp, "pack", "demo", "--remove", "--confirm")
            self.assertIn("leave_no_trace", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs")))


def _tree(root):
    """Every file under root (minus .git) with its hash — the 'nothing was
    written' assertion."""
    out = []
    for dp, _dn, fn in os.walk(root):
        if ".git" in dp.split(os.sep):
            continue
        for f in sorted(fn):
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out.append(os.path.relpath(p, root) + ":" + hashlib.md5(fh.read()).hexdigest())
    return sorted(out)


BASE = ("id: pack-demo\nname: Demo\nversion: 1.0.0\nkind: capability\n"
        "summary: demo\nlicense: MIT\nsource: https://example.com/demo\n")

# label -> (pack.yaml body, extra zip members, fragment the error must contain)
MALFORMED = {
    "invalid YAML":
        ("id: pack-demo\n  bad: [unclosed\n", {}, "not valid YAML"),
    "manifest is a list, not a mapping":
        ("- id: pack-demo\n- kind: capability\n", {}, "must be a YAML mapping"),
    "manifest is a bare scalar":
        ("just a string\n", {}, "must be a YAML mapping"),
    "manifest is empty":
        ("", {}, "is empty"),
    "non-UTF-8 bytes":
        (b"id: pack-demo\nname: \xff\xfe bad\n", {}, "not valid UTF-8"),
    "depends_on is a list":
        (BASE + "depends_on:\n  - core_primitives\n", {}, "depends_on must be a mapping"),
    "core_primitives is a bare string":
        (BASE + "depends_on:\n  core_primitives: doc-nope\n", {},
         "core_primitives: must be a list of strings"),
    "core_primitives is a mapping":
        (BASE + "depends_on:\n  core_primitives: {a: b}\n", {},
         "core_primitives: must be a list of strings"),
    "path entry is a mapping":
        (BASE + "components:\n  capabilities:\n    - path: a.md\n      why: nested\n",
         {"a.md": "x"}, "path must be a string, got dict"),
    "path entry is a number":
        (BASE + "components: {capabilities: [42]}\n", {}, "path must be a string, got int"),
    "group value is a number":
        (BASE + "components:\n  capabilities: 7\n", {},
         "must be a list of paths or a mapping"),
    "group nested two deep":
        (BASE + "components:\n  a:\n    b:\n      - x.md\n", {}, "nested mapping"),
    "listed path is absolute":
        (BASE + "components: {c: ['/etc/passwd']}\n", {}, "must be relative"),
    "listed path escapes with ..":
        (BASE + "components: {c: ['../../escape.md']}\n", {}, "`..` segment"),
    "id is a list":
        (BASE.replace("id: pack-demo", "id: [pack-demo]"), {}, "id must be a string"),
    "version parsed as a date":
        (BASE.replace("version: 1.0.0", "version: 2026-07-27"), {}, "is not semver"),
    "min_system_version is a list":
        (BASE + "min_system_version: [1, 2, 3]\n", {}, "is not semver"),
    "duplicate top-level key":
        (BASE + "kind: role-pack\n", {}, "declared more than once"),
    "required key missing":
        (BASE.replace("license: MIT\n", ""), {}, "required key 'license' is missing"),
    "bare extensionless path is not SPDX":
        (BASE.replace("license: MIT", "license: LICENSE"), {},
         "not a supported SPDX identifier"),
    "bare extension path is not SPDX":
        (BASE.replace("license: MIT", "license: LICENSE.md"), {},
         "not a supported SPDX identifier"),
    "attached license file missing":
        (BASE.replace(
            "license: MIT",
            "license: {file: LICENSE.md, sha256: "
            + hashlib.sha256(b"missing").hexdigest() + "}"
         ), {}, "license file must appear exactly once"),
    "attached license malformed hash":
        (BASE.replace(
            "license: MIT", "license: {file: LICENSE.md, sha256: nope}"
         ), {"LICENSE.md": "x"}, "license.sha256 must be an exact lowercase SHA-256"),
    "attached license unknown mapping key":
        (BASE.replace(
            "license: MIT",
            "license: {file: LICENSE.md, sha256: " + "a" * 64 + ", url: x}"
         ), {"LICENSE.md": "x"}, "must contain exactly file and sha256"),
    "attached license path escape":
        (BASE.replace(
            "license: MIT",
            "license: {file: ../LICENSE, sha256: " + "a" * 64 + "}"
         ), {}, "must not contain empty, `.` or `..`"),
    "attached license absolute path":
        (BASE.replace(
            "license: MIT",
            "license: {file: /LICENSE, sha256: " + "a" * 64 + "}"
         ), {}, "must be relative"),
    "attached license noncanonical path":
        (BASE.replace(
            "license: MIT",
            "license: {file: legal//LICENSE, sha256: " + "a" * 64 + "}"
         ), {}, "must not contain empty, `.` or `..`"),
    "PMM cannot inherit SPDX":
        (BASE.replace("id: pack-demo", "id: pack-pmm"), {},
         "pack-pmm must attach its approved proprietary license"),
    "PMM cannot declare another proprietary hash":
        (BASE.replace(
            "id: pack-demo", "id: pack-pmm"
         ).replace(
            "license: MIT",
            "license: {file: LICENSE.md, sha256: " + "a" * 64 + "}"
         ), {"LICENSE.md": "x"}, "does not match the approved proprietary"),
}


class TestMalformedManifestsReportNeverCrash(unittest.TestCase):
    """Every case: clear error, non-zero exit, no traceback, tree unchanged."""

    def _run(self, manifest, extra, argv):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            zp = os.path.join(tmp, "demo.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("pack.yaml", manifest)
                for k, v in extra.items():
                    z.writestr(k, v)
            before = _tree(tmp)
            r = aios(tmp, *argv)
            return r, before, _tree(tmp), tmp

    def test_every_malformed_shape_reports_and_writes_nothing(self):
        for label, (manifest, extra, fragment) in MALFORMED.items():
            with self.subTest(label):
                r, before, after, _ = self._run(manifest, extra, ("pack", "--verify"))
                self.assertNotIn("Traceback", r.stderr, f"{label}: crashed instead of reporting")
                self.assertEqual(1, r.returncode, f"{label}: expected a non-zero exit")
                self.assertIn(fragment, r.stdout, f"{label}: no actionable message")
                self.assertIn("REJECTED", r.stdout, f"{label}: no REJECTED verdict")
                self.assertEqual(before, after, f"{label}: the tree changed")

    def test_apply_confirm_on_malformed_also_writes_nothing(self):
        """The gate runs before the checkpoint, so --apply --confirm on a
        malformed manifest is as inert as --verify."""
        for label, (manifest, extra, fragment) in MALFORMED.items():
            with self.subTest(label):
                r, before, after, tmp = self._run(
                    manifest, extra, ("pack", "--apply", "--confirm"))
                self.assertNotIn("Traceback", r.stderr, f"{label}: crashed under --apply")
                self.assertEqual(1, r.returncode, label)
                self.assertIn(fragment, r.stdout, label)
                self.assertEqual(before, after, f"{label}: --apply wrote something")

    def test_corrupt_zip_named_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with open(os.path.join(tmp, "broken.zip"), "wb") as f:
                f.write(b"not a zip at all")
            before = _tree(tmp)
            r = aios(tmp, "pack", "broken.zip", "--verify")
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("not a readable ZIP archive", r.stdout)
            self.assertEqual(1, r.returncode)
            self.assertEqual(before, _tree(tmp))

    def test_encrypted_zip_reports(self):
        import shutil as _sh
        if _sh.which("zip") is None:
            self.skipTest("no `zip` binary to build an encrypted archive")
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            src = os.path.join(tmp, "src")
            os.makedirs(src)
            with open(os.path.join(src, "pack.yaml"), "w") as f:
                f.write(BASE)
            subprocess.run(["zip", "-q", "-P", "secret", "-j",
                            os.path.join(tmp, "enc.zip"), os.path.join(src, "pack.yaml")],
                           capture_output=True)
            _sh.rmtree(src)
            before = _tree(tmp)
            r = aios(tmp, "pack", "--verify")
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("cannot read pack.yaml", r.stdout)
            self.assertEqual(before, _tree(tmp))

    def test_zip_member_escaping_the_pack_folder_is_rejected_at_the_gate(self):
        """Caught at verify, before the checkpoint — placement is too late to
        be a report. This is the case that used to delete the installed pack,
        write half the new one, and then raise."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", BASE)
                z.writestr("../../pwned.md", "evil\n")
            before = _tree(tmp)
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("escapes the pack folder", r.stdout)
            self.assertEqual(before, _tree(tmp))
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs")))

    def test_update_from_a_hostile_zip_leaves_the_installed_pack_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _make_zip(tmp)
            aios(tmp, "pack", "--apply", "--confirm")
            good = os.path.join(tmp, "Packs", "demo", "capabilities", "demo", "SKILL.md")
            self.assertTrue(os.path.exists(good))
            with open(good, encoding="utf-8") as f:
                original = f.read()
            with zipfile.ZipFile(os.path.join(tmp, "v2.zip"), "w") as z:
                z.writestr("pack.yaml", GOOD_MANIFEST.replace("1.0.0", "2.0.0"))
                z.writestr("capabilities/demo/SKILL.md", "replaced\n")
                z.writestr("../../pwned.md", "evil\n")
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertNotIn("Traceback", r.stderr)
            self.assertEqual(1, r.returncode)
            with open(good, encoding="utf-8") as f:
                self.assertEqual(original, f.read())   # v1 untouched, not half-replaced
            self.assertTrue(os.path.exists(os.path.join(tmp, "v2.zip")))   # ZIP kept


class TestBothManifestShapesAccepted(unittest.TestCase):
    """The estate ships two real packs that declare their paths differently, and
    the gate's only question is whether a path exists in the ZIP — so both
    shapes are canonical. Refusing either would break a shipped pack."""

    def test_flat_top_level_resources_list_pmm_shape(self):
        man = (BASE.replace("kind: capability", "kind: role-pack")
               + "components: {capabilities: [capabilities/demo/SKILL.md]}\n"
               + 'resources:\n  - "01 Messaging Hub"\n  - README.md\n')
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                z.writestr("capabilities/demo/SKILL.md", SKILL)
                z.writestr("01 Messaging Hub/positioning.md", "x")   # no dir entry
                z.writestr("README.md", "x")
            r = aios(tmp, "pack", "--verify")
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("manifest gate PASSED", r.stdout)

    def test_resources_nested_under_components_content_engine_shape(self):
        man = BASE + ("components:\n  capabilities: [capabilities/demo/SKILL.md]\n"
                      "  resources:\n    - components/guard.md\n")
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                z.writestr("capabilities/demo/SKILL.md", SKILL)
                z.writestr("components/guard.md", "x")
            r = aios(tmp, "pack", "--verify")
            self.assertIn("manifest gate PASSED", r.stdout)

    def test_components_as_a_flat_list(self):
        man = BASE + "components:\n  - capabilities/demo/SKILL.md\n"
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                z.writestr("capabilities/demo/SKILL.md", SKILL)
            self.assertIn("manifest gate PASSED", aios(tmp, "pack", "--verify").stdout)

    def test_a_listed_folder_is_satisfied_without_a_directory_entry(self):
        """PMM lists '01 Messaging Hub'; a ZIP need not store directory entries.
        This used to report the folder missing and reject a valid pack."""
        man = BASE + 'resources: ["05 PMM Wiki"]\n'
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            with zipfile.ZipFile(os.path.join(tmp, "demo.zip"), "w") as z:
                z.writestr("pack.yaml", man)
                z.writestr("05 PMM Wiki/page.md", "x")
            self.assertIn("manifest gate PASSED", aios(tmp, "pack", "--verify").stdout)


class TestRemoveTargetIsAPackName(unittest.TestCase):
    def test_remove_refuses_a_path_and_deletes_nothing_outside_packs(self):
        """`aios pack ../../x --remove --confirm` resolved outside the vault,
        rmtree'd it, and reported 'leave_no_trace: validate green'."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = os.path.join(outer, "vault")
            os.makedirs(tmp)
            _vault(tmp)
            os.makedirs(os.path.join(tmp, "Packs"))
            victim = os.path.join(outer, "precious")
            os.makedirs(victim)
            with open(os.path.join(victim, "important.txt"), "w") as f:
                f.write("do not delete\n")
            r = aios(tmp, "pack", "../../precious", "--remove", "--confirm")
            self.assertNotIn("Traceback", r.stderr)
            self.assertEqual(1, r.returncode)
            self.assertIn("is not a pack name", r.stdout)
            self.assertTrue(os.path.exists(os.path.join(victim, "important.txt")))


class TestManifestContractSchema(unittest.TestCase):
    def test_schema_carries_no_top_level_schema_key(self):
        """A top-level `schema:` would make validate.load_schemas register this
        contract as a phantom note class and inflate every schema census."""
        import yaml
        p = os.path.join(VAULT, "System", "Schemas", "pack-manifest.yaml")
        with open(p, encoding="utf-8") as stream:
            d = yaml.safe_load(stream)
        self.assertNotIn("schema", d)
        self.assertNotIn("fields", d)      # doc-audit unions these across the folder
        self.assertNotIn("required", d)
        self.assertIn("pack_manifest", d)

    def test_schema_and_code_constants_agree(self):
        """The schema is the contract; the constants in pack.py are the fallback
        for a damaged vault. They must not drift apart."""
        import yaml
        sys.path.insert(0, SCRIPTS)
        from cmd import pack as pack_mod
        with open(os.path.join(VAULT, "System", "Schemas", "pack-manifest.yaml"),
                  encoding="utf-8") as stream:
            pm = yaml.safe_load(stream)["pack_manifest"]
        self.assertEqual(list(pack_mod.KINDS), pm["keys"]["kind"]["vocabulary"])
        self.assertEqual(pack_mod.ID_PATTERN, pm["keys"]["id"]["pattern"])
        self.assertEqual(pack_mod.SEMVER_PATTERN, pm["keys"]["version"]["pattern"])
        self.assertEqual(list(pack_mod.REQUIRED_KEYS), pm["required_keys"])
        self.assertEqual(
            list(pack_mod.SPDX_LICENSE_IDS),
            pm["keys"]["license"]["string_vocabulary"],
        )

    def test_gate_still_works_when_the_schema_file_is_missing(self):
        """A vault whose schema folder is damaged must still be able to refuse a
        bad pack — the contract falls back to the built-in constants, loudly."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            os.remove(os.path.join(tmp, "System", "Schemas", "pack-manifest.yaml"))
            _make_zip(tmp, manifest=GOOD_MANIFEST.replace("kind: capability", "kind: mystery"))
            r = aios(tmp, "pack", "--verify")
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("not in vocabulary", r.stdout)
            self.assertIn("unreadable", r.stdout)


if __name__ == "__main__":
    unittest.main()
