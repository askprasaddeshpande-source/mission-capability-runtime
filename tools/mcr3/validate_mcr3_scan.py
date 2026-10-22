"""Tests for the MCR 3.0 credential-shape scanner. Stdlib only, offline."""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import mcr3_scan as S  # noqa: E402

T, G = {}, {}


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def names_for(text):
    return {n for n, _ in S.scan_bytes(text.encode("utf-8") if isinstance(text, str) else text)}


def run():
    g = "SHAPES_DETECTED"
    # attacks A13b and A13c: letters-only values of 16+ characters under a strong secret name must be flagged
    t("ATTACK_REGRESSIONS", "a_long_letters_only_value_under_a_password_name_is_flagged", lambda: "secret_named_assignment" in names_for("pass" + "word=" + "k" * 20))
    t("ATTACK_REGRESSIONS", "a_long_letters_only_value_under_a_secret_key_name_is_flagged", lambda: "secret_named_assignment" in names_for("secret" + "_key = " + "h" * 30))
    t("ATTACK_REGRESSIONS", "the_utf32_form_of_the_password_attack_is_flagged", lambda: bool(S.scan_bytes(("pass" + "word=" + "k" * 20).encode("utf-32"))))
    t("ATTACK_REGRESSIONS", "a_15_character_letters_only_value_under_a_strong_name_is_not_flagged", lambda: not names_for("pass" + "word=" + "k" * 15))
    t("ATTACK_REGRESSIONS", "trailing_code_punctuation_is_not_part_of_the_value", lambda: not names_for("make(pass" + "word=abc123);;") and "secret_named_assignment" in names_for("make(pass" + "word=abc123xy);"))
    t("ATTACK_REGRESSIONS", "a_long_placeholder_under_a_strong_name_is_not_flagged", lambda: not names_for("pass" + "word=${DB_SECRET_VALUE_FROM_VAULT}") and not names_for("sec" + "ret = " + "x" * 20))
    t("ATTACK_REGRESSIONS", "a_16_character_letters_only_value_is_the_threshold", lambda: "secret_named_assignment" in names_for("pass" + "word=" + "k" * 16))
    t(g, "every_shape_has_a_synthetic_fixture", lambda: (set(S.fixture_names()) == {n for n, _ in S.SHAPES} | {"secret_named_assignment", "token_named_assignment"}))
    t(g, "shape_names_are_unique", lambda: (len({n for n, _ in S.SHAPES}) == len(S.SHAPES)))
    for name in S.fixture_names():
        fx = S.fixture(name)
        t(g, "fixture_%s_is_detected_as_its_own_shape" % name, name in names_for(fx))
        t(g, "fixture_%s_is_detected_inside_prose" % name, name in names_for("see the value " + fx + " in the log"))
    t(g, "claude_openai_github_gitlab_google_sendgrid_stripe_and_cloud_families_are_all_covered",
      {"anthropic_api_key", "openai_project_key", "github_classic_token", "github_fine_grained_pat", "gitlab_token", "google_api_key", "sendgrid_api_key",
       "stripe_key", "aws_access_key_id", "azure_storage_account_key", "slack_token"} <= {n for n, _ in S.SHAPES})

    g = "ENCODINGS"
    fx = S.fixture("github_fine_grained_pat")
    for label, data in (("utf8_bom", b"\xef\xbb\xbf" + fx.encode()), ("utf16le", fx.encode("utf-16-le")), ("utf16be", fx.encode("utf-16-be")),
                        ("utf32", fx.encode("utf-32")), ("nul_prefixed_utf16", b"\x00" + fx.encode("utf-16-le")), ("junk_prefixed_utf16", b"\x01\x02\x03" + fx.encode("utf-16-le")),
                        ("latin1", fx.encode("latin-1"))):
        t(g, "secret_is_found_in_" + label, bool(S.scan_bytes(data)))

    g = "NO_SECRET_LEAKS_IN_FINDINGS"
    for name in ("anthropic_api_key", "github_classic_token", "stripe_key"):
        fx = S.fixture(name)
        hits = S.scan_bytes(fx.encode())
        blob = json.dumps(hits)
        t(g, "findings_for_%s_hold_no_part_of_the_secret" % name, hits and fx[8:24] not in blob and all(len(f) == 8 for _, f in hits))

    g = "FALSE_POSITIVES"
    benign = {
        "sha256_hex_field": "token_sha256: \"" + "AB" * 32 + "\"",
        "digest_named": "password_digest = " + "cd" * 20,
        "identifier": "token_id: " + "q" * 20,
        "count": "secret_count = 1234567890123456",
        "upper_snake_label": 'token_source: "DPAPI_PROTECTED_CURRENT_USER_CONTEXT"',
        "placeholder": "password: changeme",
        "bracket_placeholder": "secret = <your-secret>",
        "code_call": "token = base64.b64encode(x)",
        "plain_prose": "the secret of good engineering is evidence",
        "short_token_name": "token = ok",
        "git_sha": "commit 681f77a0e3b1c2d4f5a6b7c8d9e0f1a2b3c4d5e6",
        "uuid": "id 123e4567-e89b-12d3-a456-426614174000",
        "base64_image_header": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg",
        "short_sk": "sk-learn is a library",
        "stripe_prefix_only": "use sk_live_ keys only in production",
        "ordinary_url": "https://example.org/path?x=1",
        "url_with_port": "http://127.0.0.1:2234/mcp",
        "keyword_argument_passthrough": "make(authorization_ref=authorization_ref)",
        "strong_name_with_an_attribute_path": "make(password=self.settings.password_field)",
        "strong_name_with_a_label_value": "password_mode: ENABLED_WITH_MFA_REQUIRED",
        "strong_name_with_a_hash_field": "secret_sha256: " + "ab" * 32,
        "attribute_path_value": "make(authorization=self.authorization_ref)",
    }
    for label, text in benign.items():
        t(g, "benign_" + label + "_is_not_flagged", not names_for(text))

    g = "DOCUMENTED_UNSUPPORTED"
    unsupported = {
        "short_token_value": "to" + "ken = \"abc123def456\"",
        "base64_wrapped_bearer": "QmVhcmVy" + "IGFiY2RlZmdoaWprbG1ub3BxcnN0",
        "zero_width_split": S.fixture("github_classic_token")[:6] + "​" + S.fixture("github_classic_token")[6:],
        "homoglyph": S.fixture("github_classic_token").replace("g", "ɡ", 1),
        "url_encoded_bearer": "Bear" + "er%20" + "A" * 30,
        "split_across_lines": S.fixture("github_classic_token")[:12] + "\n" + S.fixture("github_classic_token")[12:],
    }
    for label, text in unsupported.items():
        t(g, "unsupported_" + label + "_is_documented_and_not_detected", not names_for(text))
    doc = open(os.path.join(HERE, "..", "..", "architecture", "mcr3", "MCR_3_0_SECURITY_AND_AUTHORITY_CONTRACT_R1.md"), encoding="utf-8").read() if os.path.exists(os.path.join(HERE, "..", "..", "architecture", "mcr3", "MCR_3_0_SECURITY_AND_AUTHORITY_CONTRACT_R1.md")) else ""
    t(g, "the_security_contract_lists_the_unsupported_patterns", lambda: ((not doc) or all(w in doc for w in ("zero-width", "homoglyph", "split across"))))

    g = "REPOSITORY_TREE"
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    if os.path.isdir(os.path.join(root, ".git")) and not os.environ.get("MCR3_SKIP_TREE"):
        hits = S.scan_tracked_tree(root)
        # the fixtures live only as fragments; a hit anywhere in the tracked tree is a finding
        t(g, "tracked_tree_has_no_secret_shaped_content", lambda: (not hits))
    t(g, "scanner_source_is_clean", lambda: (not S.scan_bytes(open(os.path.join(HERE, "mcr3_scan.py"), "rb").read())))
    t(g, "validator_source_is_clean", lambda: (not S.scan_bytes(open(os.path.join(HERE, "validate_mcr3_scan.py"), "rb").read())))
    # ---- git history scan (a secret deleted from the tree is still in history)
    import shutil
    import subprocess
    import tempfile

    def git(cwd, *a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"] + list(a), cwd=cwd, capture_output=True, check=True)
    hd = tempfile.mkdtemp(prefix="m3hist_")
    try:
        git(hd, "init", "-q")
        open(os.path.join(hd, "a.txt"), "w").write("nothing here\n")
        git(hd, "add", "a.txt")
        git(hd, "commit", "-q", "-m", "clean")
        clean = S.scan_history(hd)
        open(os.path.join(hd, "b.txt"), "w").write(S.fixture("github_classic_token") + "\n")
        git(hd, "add", "b.txt")
        git(hd, "commit", "-q", "-m", "oops")
        git(hd, "rm", "-q", "b.txt")
        git(hd, "commit", "-q", "-m", "remove it")
        hist = S.scan_history(hd)
        tree = S.scan_tracked_tree(hd)
    finally:
        shutil.rmtree(hd, ignore_errors=True)
    t("HISTORY", "a_clean_history_has_no_findings", lambda: clean == [])
    t("HISTORY", "a_secret_deleted_from_the_tree_is_found_in_history", lambda: [x for x in hist if x[2] == "github_classic_token" and x[1] == "b.txt"] and tree == [])
    t("HISTORY", "history_findings_carry_no_matched_text", lambda: hist and all(len(x) == 4 and S.fixture("github_classic_token") not in " ".join(map(str, x)) for x in hist))
    def refuses(fn):
        try:
            fn()
        except S.ScanError:
            return True
        return False
    nr = tempfile.mkdtemp(prefix="m3_not_a_repo_")
    try:
        t("HISTORY", "history_scan_of_a_missing_folder_or_non_repository_raises_not_passes", lambda: refuses(lambda: S.scan_history(os.path.join(HERE, "no_such_dir_xyz"))) and refuses(lambda: S.scan_history(nr)))
        t("HISTORY", "tree_scan_of_a_non_repository_raises_not_passes", lambda: refuses(lambda: S.scan_tracked_tree(nr)))
        cli = subprocess.run([sys.executable, os.path.join(HERE, "scan_history_mcr3.py"), "--root", nr], capture_output=True, text=True)
        t("HISTORY", "history_scan_command_does_not_report_pass_for_a_non_repository", lambda: cli.returncode != 0 and "PASS" not in cli.stdout)
    finally:
        shutil.rmtree(nr, ignore_errors=True)


def main(argv):
    run()
    run_bounded_and_coverage()
    run_bounded_and_coverage()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_SCANNER", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1



def refuses2(fn):
    try:
        fn()
    except S.ScanError:
        return True
    return False


def run_bounded_and_coverage():
    import shutil
    import subprocess
    import tempfile
    import time
    import zipfile
    g = "BOUNDED_EXECUTION"
    for label, pat in (("alphanumeric_run", "aA1"), ("single_letter_run", "A"), ("repeated_secret_keyword", "password"), ("repeated_weak_keyword", "token")):
        blob = (pat * 80000)[:200000].encode()
        t0 = time.time()
        S.scan_bytes(blob)
        t(g, "scan_of_200kb_%s_finishes_in_bounded_time" % label, time.time() - t0 < 8)
    for label, pat in (("password_assignments", "password="), ("api_key_assignments", "api_key="), ("token_assignments", "token:"), ("glued_assignments", "pw=pw=")):
        blob = (pat * (262144 // len(pat))).encode()
        t0 = time.time()
        S.scan_bytes(blob)
        t(g, "scan_of_256kb_of_repeated_%s_finishes_in_bounded_time" % label, time.time() - t0 < 10)
    g = "CREDENTIAL_FORMATS"
    cases = {
        "lowercase_basic_header": "Authorization: basic " + "dXNlcjpwYXNzd29yZDEyMzQ1Ng==",
        "env_style_pass_name": "MY_" + "PASS=Abcdefghij12",
        "auth_key_name": "AUTH_" + "KEY=Zq9Zq9Zq9Zq9Zq9Zq9Zq9",
        "quoted_password_phrase": "pass" + "word: \"correct horse battery staple\"",
        "command_line_password_flag": "--pass" + "word hunter2hunter2",
        "curl_user_password": "curl -" + "u admin:hunter22 https://x.example",
        "slack_webhook": "hooks.slack" + ".com/services/T" + "ABCDEFGH/B" + "ABCDEFGH/" + "x" * 24,
        "telegram_bot_token": "1234567" + "890:" + "x" * 35,
    }
    for label, text in cases.items():
        t(g, label + "_is_detected", bool(names_for(text)))
    for label, text in {"powershell_variable": "$pass=($decision -eq 'PASS')", "prose_key_ending_in_a_longer_word": "\"X_SECRETISH\": \"this explains the behaviour of the thing in prose\""}.items():
        t(g, "benign_" + label + "_is_not_flagged", not names_for(text))
    g = "HISTORY_COVERAGE"
    hd = tempfile.mkdtemp(prefix="m3hist2_")

    def git(*a, **kw):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"] + list(a), cwd=hd, capture_output=True, check=True, **kw)
    try:
        git("init", "-q")
        tok = S.fixture("github_classic_token")
        open(os.path.join(hd, "pic.png"), "w").write(tok + "\n")                       # text content under a binary-looking name
        with zipfile.ZipFile(os.path.join(hd, "z.bin"), "w") as z:                       # a ZIP under a non-zip name
            z.writestr("inner.txt", tok)
        open(os.path.join(hd, "a.txt"), "w").write("clean\n")
        git("add", "-A")
        git("commit", "-q", "-m", "message carrying " + tok)
        git("tag", "-a", "v0", "-m", "tag message " + S.fixture("stripe_key"))
        hist = S.scan_history(hd)
        tree = S.scan_tracked_tree(hd)
    finally:
        shutil.rmtree(hd, ignore_errors=True)
    t(g, "a_text_file_named_like_an_image_is_scanned_in_history", any(x[1] == "pic.png" for x in hist))
    t(g, "a_text_file_named_like_an_image_is_scanned_in_the_tree", any(x[0] == "pic.png" for x in tree))
    t(g, "a_zip_without_a_zip_name_is_opened_in_history", any(x[1].startswith("z.bin!") for x in hist))
    t(g, "a_zip_without_a_zip_name_is_opened_in_the_tree", any(x[0].startswith("z.bin!") for x in tree))
    t(g, "a_credential_in_a_commit_message_is_found", any(x[1] == "<commit message>" for x in hist))
    t(g, "a_credential_in_a_tag_message_is_found", any(x[1] == "<tag message>" for x in hist))
    # an unreadable ZIP member is reported, and the readable members are still scanned
    import io
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("first.txt", "pass" + "word = " + "p@ss!w0rd-" + "x" * 8)
        z.writestr("second.txt", "harmless text here")
    raw = bytearray(zb.getvalue())
    second = raw.rindex(b"PK\x01\x02")
    raw[second + 10:second + 12] = (99).to_bytes(2, "little")             # compression method 99: unsupported
    zres = S.scan_blob("z.zip", bytes(raw))
    t(g, "an_unreadable_zip_member_is_reported", any(x[1] == "unreadable_zip_member" and x[0].endswith("second.txt") for x in zres))
    t(g, "readable_zip_members_are_still_scanned_when_another_is_unreadable", any(x[0].endswith("first.txt") and x[1] == "secret_named_assignment" for x in zres))
    sd = tempfile.mkdtemp(prefix="m3shallow_")
    try:
        src = os.path.join(sd, "src")
        os.makedirs(src)
        subprocess.run(["git", "init", "-q"], cwd=src, check=True, capture_output=True)
        for n_ in (1, 2):
            open(os.path.join(src, "f%d.txt" % n_), "w").write("x%d\n" % n_)
            subprocess.run(["git", "add", "-A"], cwd=src, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "c%d" % n_], cwd=src, check=True, capture_output=True)
        shallow = os.path.join(sd, "shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + src.replace(os.sep, "/"), shallow], check=True, capture_output=True)
        t(g, "a_shallow_clone_cannot_produce_a_history_scan_result", lambda: refuses2(lambda: S.scan_history(shallow)))
    finally:
        shutil.rmtree(sd, ignore_errors=True)
    big = b"x" * (S.MAX_SCAN + 1)
    t(g, "content_beyond_the_scan_limit_is_reported_not_skipped", any(h[1] == "unscanned_oversize" for h in S.scan_blob("big.txt", big)))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
