"""Adversarial tests of verify_mcr3.py, including the six scanner attacks (A13a to A13f) that the R2.0 release could not run to
completion. Usage: python tools/mcr3/run_mcr3_verifier_attacks.py [--out PATH]

Memory-bounded by design: scenarios run strictly one at a time, each in a throwaway `git clone` of the committed HEAD, using
the verifier's --fast profile (no validator run, no mutation run), and each verifier process reports its own peak working
set. A scenario PASSES when the verifier FAILS for the intended reason (the named check is False). The one documented limit
(S05) must pass without an external anchor and fail with one. Payloads are assembled at run time so this file holds nothing
secret-shaped.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
BASELINE = "fd865c67c053431dc33297a0df2a3c9a02fd51fe"
WRAP = ("import runpy,sys,os\nsys.path.insert(0,sys.argv[1])\nscript=sys.argv[2]\nsys.argv=[script]+sys.argv[3:]\ncode=0\n"
        "try:\n    runpy.run_path(script,run_name='__main__')\nexcept SystemExit as e:\n    code=e.code if isinstance(e.code,int) else (0 if e.code is None else 1)\n"
        "finally:\n    import mcr3_measure\n    sys.stderr.write('\\nPEAK_BYTES=%d\\n'%mcr3_measure.peak_bytes())\nsys.exit(code)\n")


def rm(path):
    def onerr(func, p, exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass
    if os.path.exists(path):
        shutil.rmtree(path, onexc=onerr)


def git(cwd, *a):
    return subprocess.run(["git", "-c", "user.email=attack@example.org", "-c", "user.name=attack"] + list(a), cwd=cwd, capture_output=True, text=True)


def verify(cwd, *extra):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t0 = time.time()
    r = subprocess.run([sys.executable, "-c", WRAP, os.path.join(cwd, "tools", "mcr3"), os.path.join(cwd, "tools", "mcr3", "verify_mcr3.py"), "--fast"] + list(extra),
                       cwd=cwd, capture_output=True, text=True, timeout=900, env=env)
    peak = None
    for line in r.stderr.splitlines():
        if line.startswith("PEAK_BYTES="):
            peak = int(line.split("=", 1)[1])
    try:
        d = json.loads(r.stdout)
    except Exception:
        d = {"MCR3_VERIFY": "ERROR", "stderr": r.stderr[-300:]}
    return d, round(time.time() - t0, 2), peak


def regen_sums(c):
    subprocess.run([sys.executable, os.path.join(c, "tools", "mcr3", "verify_mcr3.py"), "--write-sums"], cwd=c, capture_output=True)


def commit(c, msg="attack"):
    git(c, "add", "-A")
    git(c, "commit", "-q", "-m", msg)


def main(argv):
    scratch = os.path.join(tempfile.gettempdir(), "mcr3_vattack")
    rm(scratch)
    os.makedirs(scratch)
    head = git(ROOT, "rev-parse", "HEAD").stdout.strip()
    jwt = ".".join(["ey" + "J" + "a" * 20, "b" * 20, "c" * 10])
    scenarios = []

    def sc(name, fn, expect_false=None, with_anchor=None, note=""):
        scenarios.append((name, fn, expect_false, with_anchor, note))

    P = lambda *parts: os.path.join(*parts)
    # --- integrity attacks
    sc("S01_edit_a_tracked_file_without_updating_sums", lambda c: open(P(c, "tools", "mcr3", "evc1.py"), "a").write("\n# tamper\n"), "sums_hashes_match")
    def s02(c):
        open(P(c, "tools", "mcr3", "zz_extra.py"), "w").write("x = 1\n")
        commit(c)
    sc("S02_add_an_unlisted_file_in_a_3_0_folder", s02, "sums_cover_every_tracked_file")

    def s03(c):
        with open(P(c, "reports", "r2.0", "MCR_R2_0_RESEARCH_SUMMARY_R1.md"), "a") as fh:
            fh.write("\nedited\n")
        commit(c)
    sc("S03_edit_a_frozen_r2_0_file_and_commit", s03, "frozen_history_untouched")

    def s04(c):
        os.remove(P(c, "evidence", "r2.0", "MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json"))
        commit(c)
    sc("S04_delete_the_frozen_live_result_and_commit", s04, "frozen_history_untouched")

    def s05(c):
        open(P(c, "zz_outside.txt"), "w").write("harmless\n")
        commit(c)
    sc("S05_add_a_file_outside_the_3_0_folders_and_commit", s05, "frozen_history_untouched")

    def s06(c):
        git(c, "tag", "-f", "v1.9.0", "HEAD")
    sc("S06_move_the_r1_9_tag", s06, "r1_9_tag_is_unchanged")

    def s07(c):
        open(P(c, "tools", "mcr3", "zz_unpinned.py"), "w").write("y = 2\n")
        commit(c)
        regen_sums(c)
        commit(c)
    sc("S07_documented_limit_new_file_with_regenerated_sums_passes_without_an_anchor", s07, None, with_anchor=True,
       note="must PASS without --expect-sums-sha256 and FAIL with it (self-attesting limit)")

    def s08(c):
        open(P(c, "tools", "mcr3", "zz_path.py"), "w").write("p = 'C:/Users/someone/x'\n")
        commit(c)
        regen_sums(c)
        commit(c)
    sc("S08_machine_specific_absolute_path_in_code", s08, "no_machine_specific_paths_in_code")

    def s09(c):
        os.makedirs(P(c, "tools", "mcr3", "__pycache__"), exist_ok=True)
        open(P(c, "tools", "mcr3", "__pycache__", "x.cpython-313.pyc"), "wb").write(b"\x00\x01")
        git(c, "add", "-f", "-A")
        git(c, "commit", "-q", "-m", "bytecode")
        regen_sums(c)
        commit(c)
    sc("S09_tracked_bytecode", s09, "no_tracked_bytecode")

    # --- the six scanner attacks A13a to A13f (secrets in place, sums regenerated so only the scanner can object)
    def planted(rel, data):
        def f(c):
            p = P(c, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(data)
            commit(c)
            regen_sums(c)
            commit(c)
        return f
    sc("A13a_nul_prefixed_utf16_secret", planted("reports/mcr3/zz_n.txt", b"\x00" + ("to" + "ken=" + "q" * 24).encode("utf-16-le")), "no_credential_shaped_content")
    sc("A13b_utf32_secret", planted("reports/mcr3/zz_u32.txt", ("pass" + "word=" + "k" * 20).encode("utf-32")), "no_credential_shaped_content")
    sc("A13c_secret_key_assignment", planted("reports/mcr3/zz_sk.md", ("secret" + "_key = " + "h" * 30 + "\n").encode()), "no_credential_shaped_content")
    sc("A13d_secret_outside_the_3_0_folders", planted("zz_outside_the_roots.txt", ("api_" + "key=" + "ab12" * 8 + "\n").encode()), "no_credential_shaped_content")
    sc("A13e_hex_value_under_a_secret_name", planted("reports/mcr3/zz_hex.md", ("to" + "ken: " + "ab12" * 16 + "\n").encode()), "no_credential_shaped_content")

    def a13f(c):
        p = P(c, "reports", "mcr3", "zz_member.zip")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("inner/notes.txt", "see " + jwt + "\n")
        commit(c)
        regen_sums(c)
        commit(c)
    sc("A13f_secret_inside_a_zip_member", a13f, "no_credential_shaped_content")
    # --- further token shapes the 3.0 scanner adds
    import mcr3_scan
    for shape in ("github_fine_grained_pat", "anthropic_api_key", "gitlab_token", "google_api_key", "sendgrid_api_key", "stripe_key", "aws_access_key_id"):
        sc("T_%s_in_a_tracked_file" % shape, planted("reports/mcr3/zz_%s.txt" % shape, ("value: " + mcr3_scan.fixture(shape) + "\n").encode()), "no_credential_shaped_content")

    results, ok_all = {}, True
    for name, fn, expect_false, anchor, note in scenarios:
        c = os.path.join(scratch, "c")
        rm(c)
        r = subprocess.run(["git", "clone", "-q", "--no-hardlinks", ROOT, c], capture_output=True, text=True)
        git(c, "checkout", "-q", head)
        fn(c)
        d, wall, peak = verify(c, "--allow-no-anchor")
        if anchor:
            anchor_sha = subprocess.run(["git", "show", "HEAD~2:evidence/mcr3/SHA256SUMS_MCR3.txt"], cwd=c, capture_output=True).stdout.replace(b"\r\n", b"\n")
            import hashlib
            d2, _, _ = verify(c, "--expect-sums-sha256", hashlib.sha256(anchor_sha).hexdigest())
            passed = d["MCR3_VERIFY"] == "PASS_WITHOUT_EXTERNAL_ANCHOR" and d2["MCR3_VERIFY"] == "FAIL" and d2.get("sums_anchor_matches") is False
            results[name] = {"passed": passed, "without_anchor": d["MCR3_VERIFY"], "with_anchor": d2["MCR3_VERIFY"], "wall_seconds": wall, "peak_bytes": peak, "note": note}
        else:
            key_ok = (d.get(expect_false) is False) or (expect_false == "r1_9_tag_is_unchanged" and d.get("r1_9_tag") == "CHANGED_OR_MISSING")
            passed = d["MCR3_VERIFY"] == "FAIL" and key_ok
            results[name] = {"passed": passed, "verifier": d["MCR3_VERIFY"], "intended_check": expect_false, "intended_check_failed": key_ok, "wall_seconds": wall, "peak_bytes": peak}
        ok_all &= results[name]["passed"]
        rm(c)
    # --- verdict-honesty scenarios: a check that was not performed, or an anchor that was not supplied, is never a PASS
    c = os.path.join(scratch, "c")
    rm(c)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", ROOT, c], capture_output=True, text=True)
    git(c, "checkout", "-q", head)
    d_none, w1, p1 = verify(c)
    results["N1_no_anchor_is_blocked_not_pass"] = {"passed": d_none["MCR3_VERIFY"] == "BLOCKED_EXTERNAL_ANCHOR", "verifier": d_none["MCR3_VERIFY"], "wall_seconds": w1, "peak_bytes": p1}
    d_ng, w2, p2 = verify(c, "--no-git", "--allow-no-anchor")
    results["N2_no_git_mode_is_not_pass"] = {"passed": d_ng["MCR3_VERIFY"] == "FAIL" and bool(d_ng.get("mandatory_checks_not_performed")), "verifier": d_ng["MCR3_VERIFY"], "wall_seconds": w2, "peak_bytes": p2}
    d_mv, w3, p3 = verify(c, "--expect-sums-sha256")
    results["N3_anchor_flag_without_a_value_fails"] = {"passed": d_mv["MCR3_VERIFY"] == "FAIL", "verifier": d_mv["MCR3_VERIFY"], "wall_seconds": w3, "peak_bytes": p3}
    ok_all &= all(results[k]["passed"] for k in ("N1_no_anchor_is_blocked_not_pass", "N2_no_git_mode_is_not_pass", "N3_anchor_flag_without_a_value_fails"))
    rm(c)
    out = {"evidence_class": "SYNTHETIC/LOCAL", "scenarios": len(results), "all_passed": ok_all, "head_attacked": head, "sequential": True, "profile": "--fast", "results": results,
           "max_peak_bytes": max([v.get("peak_bytes") or 0 for v in results.values()])}
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    rm(scratch)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
