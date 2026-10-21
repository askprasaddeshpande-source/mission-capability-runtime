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
        "attribute_path_value": "make(authorization=self.authorization_ref)",
    }
    for label, text in benign.items():
        t(g, "benign_" + label + "_is_not_flagged", not names_for(text))

    g = "DOCUMENTED_UNSUPPORTED"
    unsupported = {
        "short_token_value": "to" + "ken = \"abc123def456\"",
        "quoted_password_with_spaces": "pass" + "word = \"correct horse battery staple\"",
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


def main(argv):
    run()
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
