"""Adversarial tests of the verifier. Usage: python tools/r2.0/run_r2_verifier_attacks.py [--out PATH]  (several minutes)

Each attack is applied to a scratch COPY of the working tree; the verifier must FAIL, except the one documented
limitation (A5): a new unpinned file plus regenerated sums passes without an external anchor and must fail with
--expect-sums-sha256. Payloads are assembled at runtime so this file itself contains nothing secret-shaped.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TMP = os.path.join(tempfile.gettempdir(), "r2_vattack_scratch")

JWT = ".".join(["eyJ" + "a" * 20, "b" * 20, "c" * 10])
SK = "sk" + "-" + "d" * 30
BEARER = "Bearer" + " " + "e" * 30
QUOTED = "to" + "ken" + ' = "' + "f" * 30 + '"'
DRIVE_PATH = chr(68) + ":/work/secret/path"
LONG = "g" * 24
UNC = chr(92) * 2 + "fileserver" + chr(92) + "share"
PROFILE = "%" + "USERPRO" + "FILE" + "%" + chr(92) + "x"


def rm(path):
    def onerr(func, p, exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass
    if os.path.exists(path):
        shutil.rmtree(path, onexc=onerr)


def fresh():
    rm(TMP)
    shutil.copytree(SRC, TMP, ignore=shutil.ignore_patterns("__pycache__"))


def run(args=()):
    r = subprocess.run([sys.executable, "tools/r2.0/verify_r2_fresh_clone.py", "--quick", *args], cwd=TMP, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"R2_FRESH_CLONE_VERIFY": "CRASH:" + r.stderr[-200:]}


def sums():
    subprocess.run([sys.executable, "tools/r2.0/verify_r2_fresh_clone.py", "--write-sums"], cwd=TMP, capture_output=True, text=True)


def write(rel, text):
    p = os.path.join(TMP, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main():
    results = {}
    fresh()
    d = run()
    base_sha = d["sums_sha256"]
    results["baseline_clean_copy"] = d["R2_FRESH_CLONE_VERIFY"]

    fresh(); write("tools/r2.0/zz_tool.py", 'P = "' + DRIVE_PATH + '"\n'); sums()
    d = run(); results["A1_forward_slash_drive_path_in_new_tool"] = (d["R2_FRESH_CLONE_VERIFY"], d["no_absolute_paths_in_docs"])

    for name, payload in (("A2a_jwt", "x = " + JWT + "\n"), ("A2b_sk_token", "key " + SK + "\n"),
                          ("A2c_quoted_secret", QUOTED + "\n"), ("A2d_bearer", "Authorization: " + BEARER + "\n")):
        fresh(); write("reports/r2.0/zz_note.md", payload); sums()
        d = run(); results[name] = (d["R2_FRESH_CLONE_VERIFY"], d["no_secret_like_strings"])

    fresh()
    with open(os.path.join(TMP, "reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md"), "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\nedited\n")
    sums()
    d = run(); results["A3_pinned_frozen_file_edited_and_sums_regenerated"] = (d["R2_FRESH_CLONE_VERIFY"], d["frozen_historical_unchanged"])

    fresh()
    p = os.path.join(TMP, "tools/r2.0/mcr_r2_model.py")
    s = open(p, encoding="utf-8").read().replace("\r\n", "\n")
    s2 = re.sub(r'(self\._rel\("R05", )(.+)(\)\n)', lambda m: m.group(1) + "True" + m.group(3), s, count=1)
    assert s2 != s
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s2)
    sums()
    d = run(); results["A4_model_relation_replaced_by_True_and_sums_regenerated"] = (d["R2_FRESH_CLONE_VERIFY"], d["reviewed_revision_pins_match"], d["validator_passes"])

    fresh(); write("reports/r2.0/zz_new_unpinned.md", "new unpinned file\n"); sums()
    d1 = run(); d2 = run(["--expect-sums-sha256", base_sha])
    results["A5_new_file_plus_regenerated_sums"] = {"without_external_anchor": d1["R2_FRESH_CLONE_VERIFY"],
                                                    "with_external_anchor": d2["R2_FRESH_CLONE_VERIFY"], "anchor_matches": d2["sums_anchor_matches"]}


    fresh(); write("reports/r2.0/zz_new_staged.md", "new staged file\n")
    subprocess.run(["git", "add", "reports/r2.0/zz_new_staged.md"], cwd=TMP, capture_output=True)
    sums()
    d1 = run(); d2 = run(["--expect-sums-sha256", base_sha])
    results["A5b_new_file_staged_plus_regenerated_sums"] = {"without_external_anchor": d1["R2_FRESH_CLONE_VERIFY"], "with_external_anchor": d2["R2_FRESH_CLONE_VERIFY"],
                                                          "anchor_matches": d2["sums_anchor_matches"],
                                                          "note": "documented limit: without an anchor from outside the repository an attacker who stages the file and regenerates the sums passes"}
    fresh(); subprocess.run(["git", "tag", "-d", "v1.9.0"], cwd=TMP, capture_output=True)
    d1 = run(); d2 = run(["--no-git"])
    results["A6_missing_r1_9_tag"] = {"default": d1["R2_FRESH_CLONE_VERIFY"], "tag_field": d1["r1_9_tag"], "with_no_git_flag": d2["R2_FRESH_CLONE_VERIFY"]}

    fresh()
    h = os.path.join(TMP, "tools/r2.0/make_adt_auth_context.py")
    if os.path.exists(h):
        with open(h, "a", encoding="utf-8", newline="\n") as fh:
            fh.write('\nTOKEN_X = "' + JWT + '"\n')
        d = run(); results["A7_secret_inside_git_ignored_credential_helper"] = (d["R2_FRESH_CLONE_VERIFY"], d["details"]["secret_like_files"])
    else:
        results["A7_secret_inside_git_ignored_credential_helper"] = "helper not present in this checkout"

    fresh()
    with open(os.path.join(TMP, "evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json"), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(" ")
    d = run(); results["A8_frozen_live_result_one_byte_changed_without_regenerating_sums"] = (d["R2_FRESH_CLONE_VERIFY"], d["hashes_match"], d["frozen_historical_unchanged"])


    # --- review 3 verifier gaps
    fresh()
    pyc = os.path.join(TMP, "tools/r2.0/__pycache__/zz.cpython-313.pyc")
    os.makedirs(os.path.dirname(pyc), exist_ok=True)
    with open(pyc, "wb") as fh:
        fh.write(b"\x00pyc")
    subprocess.run(["git", "add", "-f", "tools/r2.0/__pycache__/zz.cpython-313.pyc"], cwd=TMP, capture_output=True)
    d = run(["--expect-sums-sha256", base_sha]); results["A9_tracked_bytecode_even_with_the_anchor"] = (d["R2_FRESH_CLONE_VERIFY"], d["no_tracked_bytecode"])

    fresh()
    d = run(["--expect-sums-sha256", ""]); results["A10_empty_anchor_value"] = (d["R2_FRESH_CLONE_VERIFY"], d["sums_anchor_matches"])
    fresh()
    d = run(["--expect-sums-sha256", "not-a-hash"]); results["A10b_malformed_anchor_value"] = (d["R2_FRESH_CLONE_VERIFY"], d["sums_anchor_matches"])

    payloads = {
        "A11a_json_quoted_key": ("reports/r2.0/zz.json", '{"to' + 'ken": "' + LONG + '"}\n', "w"),
        "A11b_yaml_file": ("evidence/r2.0/zz.yaml", "pass" + "word: " + LONG + "\n", "w"),
        "A11c_extensionless_file": ("reports/r2.0/zznote", "api_" + "key=" + LONG + "\n", "w"),
        "A11d_utf16_file": ("reports/r2.0/zz16.txt", ("Authori" + "zation: " + BEARER + "\n"), "utf16"),
        "A11e_base64_bearer": ("reports/r2.0/zzb.md", "Bearer" + " " + "QUJDREVGR0hJSktMTU5PUA==" + "\n", "w"),
        "A11f_basic_auth": ("reports/r2.0/zzc.md", "Basic" + " " + "dXNlcjpwYXNzd29yZDEyMzQ1Ng==" + "\n", "w"),
        "A11g_unquoted_password": ("reports/r2.0/zzd.md", "pass" + "word=" + LONG + "\n", "w"),
        "A11h_x_api_key_header": ("reports/r2.0/zze.md", "x-api" + "-key: " + LONG + "\n", "w"),
    }
    for name, (rel, body, mode) in payloads.items():
        fresh()
        full = os.path.join(TMP, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if mode == "utf16":
            with open(full, "wb") as fh:
                fh.write(body.encode("utf-16"))
        else:
            write(rel, body)
        sums()
        d = run(); results[name] = (d["R2_FRESH_CLONE_VERIFY"], d["no_secret_like_strings"])
    for name, body in (("A12a_unc_path", "see " + UNC + "\n"), ("A12b_env_var_profile_path", "see " + PROFILE + "\n")):
        fresh(); write("reports/r2.0/zzp.md", body); sums()
        d = run(); results[name] = (d["R2_FRESH_CLONE_VERIFY"], d["no_absolute_paths_in_docs"])

    # --- review 4 scanner evasions
    evasions = {
        "A13a_nul_prefixed_utf16": ("reports/r2.0/zz_n.txt", b"\x00" + ("to" + "ken=" + "q" * 24).encode("utf-16-le"), True),
        "A13b_utf32_file": ("reports/r2.0/zz_u32.txt", ("pass" + "word=" + "k" * 20).encode("utf-32"), True),
        "A13c_secret_key_assignment": ("reports/r2.0/zz_sk.md", ("secret" + "_key = " + "h" * 30 + "\n").encode(), True),
        "A13d_secret_outside_the_r2_folders": ("zz_outside_the_roots.txt", ("api_" + "key=" + "ab12" * 8 + "\n").encode(), True),
        "A13e_hex_value_under_a_secret_name": ("reports/r2.0/zz_hex.md", ("to" + "ken: " + "ab12" * 16 + "\n").encode(), True),
    }
    for name, (rel, body, stage) in evasions.items():
        fresh()
        full = os.path.join(TMP, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(body)
        subprocess.run(["git", "add", "-f", rel], cwd=TMP, capture_output=True)
        sums()
        d = run(); results[name] = (d["R2_FRESH_CLONE_VERIFY"], d["no_secret_like_strings"])
    fresh()
    with zipfile.ZipFile(os.path.join(TMP, "evidence", "zz_secret_in_zip.zip"), "w") as zf:
        zf.writestr("inner/zz.txt", "to" + "ken=" + "w" * 24)
    subprocess.run(["git", "add", "-f", "evidence/zz_secret_in_zip.zip"], cwd=TMP, capture_output=True)
    sums()
    d = run(); results["A13f_secret_inside_a_zip_member"] = (d["R2_FRESH_CLONE_VERIFY"], d["no_secret_like_strings"])
    rm(TMP)
    print(json.dumps(results, indent=1, sort_keys=True))
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w", newline="\n") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
