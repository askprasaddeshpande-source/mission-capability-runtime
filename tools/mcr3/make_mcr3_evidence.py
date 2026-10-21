"""Generate the deterministic MCR 3.0 evidence artifacts (consumer compatibility matrix, adapter sample outputs, event-contract
digests) into evidence/mcr3. Usage: python tools/mcr3/make_mcr3_evidence.py [--out-dir DIR]
Everything written here is reproducible byte-for-byte from the repository; nothing is machine- or time-dependent.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import evc1  # noqa: E402
import mcr3_adapters as AD  # noqa: E402
import validate_mcr3_adapters as VA  # noqa: E402
import validate_mcr3_evc1 as VE  # noqa: E402

NOW = "2027-01-15T00:00:00Z"


def dump(path, obj):
    with open(path, "w", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def matrix():
    v10 = VE.event_of("mcr.execution.receipt")
    cases = {
        "v1_0_event": v10,
        "v1_1_event_no_new_fields": VE.reseal(v10, lambda x: x.update(contract_version="1.1.0")),
        "v1_1_event_with_unknown_noncritical_field": VE.reseal(v10, lambda x: x.update(contract_version="1.1.0", future_field={"a": 1})),
        "v1_1_event_with_unknown_critical_field": VE.reseal(v10, lambda x: x.update(contract_version="1.1.0", future_field=1, critical=["future_field"])),
        "v1_0_event_with_unknown_field": VE.reseal(v10, lambda x: x.update(future_field=1)),
        "v2_0_event": dict(v10, contract_version="2.0.0"),
        "unknown_event_type": VE.reseal(v10, lambda x: x.update(type="mcr.mission.exploded")),
        "unknown_enum_value": VE.reseal(v10, lambda x: x["claim"].update(call_class="FINE")),
        "tampered_claim": dict(v10, claim=dict(v10["claim"], provider_acknowledged=False)),
        "authority_effect_grant": VE.reseal(v10, lambda x: x.update(authority_effect="GRANT")),
    }
    consumers = {"consumer_supports_1_0": {"supported_minor": 0}, "consumer_supports_1_1": {"supported_minor": 1}}
    out = {}
    for cname, kw in consumers.items():
        out[cname] = {}
        for ename, ev in cases.items():
            try:
                _, unk = evc1.parse(ev, **kw)
                out[cname][ename] = "ACCEPTED" if not unk else "ACCEPTED_UNRECOGNIZED_FIELDS_RETAINED_NOT_INTERPRETED"
            except evc1.ContractError as exc:
                out[cname][ename] = "REJECTED: " + str(exc).split(":")[0][:60]
    return {"contract": evc1.CONTRACT, "current_version": evc1.CURRENT_VERSION, "schema_digest": evc1.SCHEMA_DIGEST, "spec_pins": evc1.SPEC_PINS,
            "rules": ["same major only; a newer minor may add optional top-level fields, which an older consumer retains but never interprets",
                      "an unknown field in the SAME minor is rejected", "an unknown critical name is always rejected", "a new enum value or event type is a major change (rejected here)",
                      "migration within a major relabels, records lineage and the source digest, and refuses to drop unrecognized fields"],
            "matrix": out}


def main(argv):
    out_dir = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else os.path.join(ROOT, "evidence", "mcr3")
    os.makedirs(out_dir, exist_ok=True)
    dump(os.path.join(out_dir, "MCR3_CONSUMER_COMPATIBILITY_MATRIX_R1.json"), matrix())
    live, src = AD.load_r2_live_result(ROOT)
    dump(os.path.join(out_dir, "MCR3_R2_REFERENCE_ADAPTER_OUTPUT_R1.json"),
         {"adapter": AD.Mcr2ReferenceAdapter.declaration().declaration, "source": src, "note": "conversion time is a fixed label, not the occurrence time",
          "events": AD.Mcr2ReferenceAdapter().convert(live, now=NOW, source_ref=src)})
    m, f = VA.complete_mission()
    dump(os.path.join(out_dir, "MCR3_NATIVE_ADAPTER_SAMPLE_R1.json"),
         {"adapter": AD.Mcr3NativeAdapter.declaration().declaration, "scenario": "synthetic complete mission (14 links)", "events": AD.Mcr3NativeAdapter().convert(m, now=NOW)})
    dump(os.path.join(out_dir, "MCR3_CONTRACT_DIGESTS_R1.json"),
         {"contract": evc1.CONTRACT, "schema_digest": evc1.SCHEMA_DIGEST, "event_types": sorted(evc1.TYPE_TABLE),
          "example_digests": {t: VE.event_of(t)["integrity"]["event_digest"] for t in sorted(evc1.TYPE_TABLE)}})
    print("written to", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
