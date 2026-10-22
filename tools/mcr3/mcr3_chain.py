"""Consistency of ONE mission's event set (an "evidence chain"), beyond what a single event's schema can say.

`check_mission_events(events)` returns a list of problems (empty = consistent). It never raises on hostile input. It checks
identity (one mission, one transaction, unique ids), shape (one start first, at most one disposition last, a single causal
path, non-decreasing times), counting (attempt numbers 1..n without gaps), cross-references (the digest each claim names is
the evidence digest of the event it refers to) and logic (a commit needs an EXISTS readback before it, a PASS outcome needs
a committed observation, COMPLETE needs both and a full 14-digest chain). A consistent set is not an authentic set: signatures
and trust are separate (mcr3_provenance).
"""
import datetime

import evc1


def _when(ts):
    return datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(microseconds=int((ts[19:-1] + "000000")[1:7]) if ts[19:20] == "." else 0)

ORDER = ["mcr.mission.started", "mcr.authorization.referenced", "mcr.mutation.attempted", "mcr.execution.receipt", "mcr.readback.claimed",
         "mcr.commit.observed", "mcr.outcome.evaluated"]


def check_mission_events(events):
    probs = []
    if not isinstance(events, list) or not events:
        return ["no events"]
    parsed = []
    for i, e in enumerate(events):
        try:
            known, _ = evc1.parse(e)
        except Exception as exc:
            probs.append("event %d is not a valid mcr-evidence/1 event (%s)" % (i, str(exc)[:60]))
            continue
        parsed.append(known)
    if probs:
        return probs
    ids = [e["id"] for e in parsed]
    if len(set(ids)) != len(ids):
        probs.append("duplicate event ids")
    missions = {e["correlation"]["mission_id"] for e in parsed}
    if len(missions) != 1 or None in missions:
        probs.append("events belong to %d missions (or one has no mission id)" % len(missions))
    txs = {e["correlation"]["transaction_id"] for e in parsed if e["type"] != "mcr.mission.started"}
    if len(txs) > 1 or None in txs:
        probs.append("events belong to more than one transaction (or one has none)")
    starts = [i for i, e in enumerate(parsed) if e["type"] == "mcr.mission.started"]
    if len(starts) != 1 or starts[0] != 0:
        probs.append("there must be exactly one mission.started and it must come first")
    disp = [i for i, e in enumerate(parsed) if e["type"] == "mcr.mission.disposition"]
    if len(disp) > 1 or (disp and disp[0] != len(parsed) - 1):
        probs.append("at most one mission.disposition, and it must come last")
    for i in range(1, len(parsed)):
        if parsed[i]["correlation"]["causation_id"] != parsed[i - 1]["id"]:
            probs.append("event %d does not name its predecessor as its cause" % i)
    if parsed[0]["correlation"]["causation_id"] is not None:
        probs.append("the first event must have no cause")
    times = [_when(e["time"]) for e in parsed]
    if times != sorted(times):
        probs.append("event times decrease")
    # counting
    att = [e["claim"]["attempt_number"] for e in parsed if e["type"] == "mcr.mutation.attempted"]
    if att != list(range(1, len(att) + 1)):
        probs.append("mutation attempt numbers are not 1..n without gaps")
    comp = [e["claim"]["attempt_number"] for e in parsed if e["type"] == "mcr.compensation.attempted"]
    if comp != list(range(1, len(comp) + 1)):
        probs.append("compensation attempt numbers are not 1..n without gaps")
    pos = {}
    for i, e in enumerate(parsed):
        pos.setdefault(e["type"], i)
    by = {e["type"]: e for e in parsed if e["type"] not in ("mcr.compensation.attempted",)}
    # ordering of the forward events that are present
    seen = [pos[t] for t in ORDER if t in pos]
    if seen != sorted(seen):
        probs.append("forward events are out of order")
    rb, co, oc, er = by.get("mcr.readback.claimed"), by.get("mcr.commit.observed"), by.get("mcr.outcome.evaluated"), by.get("mcr.execution.receipt")
    # cross-references
    if co and (not rb or co["claim"]["readback_digest"] != rb["evidence"]["digest"]):
        probs.append("commit observation names a readback that is not in the chain")
    if oc and (not rb or oc["claim"]["readback_digest"] != rb["evidence"]["digest"]):
        probs.append("outcome evaluation names a readback that is not in the chain")
    # logic
    if co and co["claim"]["commit_state"] == "COMMITTED":
        if not rb or rb["claim"]["existence"] != "EXISTS":
            probs.append("COMMITTED needs an EXISTS readback before it")
        if not er or er["claim"]["call_class"] not in ("PROVIDER_RESPONSE_SUCCESS", "COMMIT_CONFIRMED", "COMMIT_UNKNOWN", "OUTCOME_VALIDATED"):
            probs.append("COMMITTED needs an execution receipt before it")
    if oc and oc["claim"]["result"] == "PASS" and not (co and co["claim"]["commit_state"] == "COMMITTED"):
        probs.append("a PASS outcome needs a committed observation")
    if rb and rb["claim"]["claimed_authoritative"] and rb["claim"]["source_level"] != "AUTHORITATIVE_REPOSITORY":
        probs.append("readback claims authority from a non-authoritative level")
    if disp:
        d = parsed[disp[0]]
        c = d["claim"]
        digs = set(c["chain_digests"])
        for t in ("mcr.mission.started", "mcr.execution.receipt", "mcr.readback.claimed", "mcr.commit.observed", "mcr.outcome.evaluated"):
            if t in by and by[t]["evidence"]["digest"] not in digs:
                probs.append("disposition chain_digests lack the evidence digest of %s" % t)
        if c["disposition"] == "COMPLETE":
            if not (oc and oc["claim"]["result"] == "PASS" and co and co["claim"]["commit_state"] == "COMMITTED"):
                probs.append("COMPLETE needs a PASS outcome and a COMMITTED observation")
            if len(digs) != 14 or len(c["chain_digests"]) != 14:
                probs.append("COMPLETE needs a 14-digest chain")
        if c["outcome_class"] == "OUTCOME_VALIDATED" and not (oc and oc["claim"]["result"] == "PASS"):
            probs.append("OUTCOME_VALIDATED needs a PASS outcome")
        if c["outcome_class"] in ("COMMIT_OBSERVED", "OUTCOME_OBSERVED", "OUTCOME_VALIDATED", "COMPLETE") and not co:
            probs.append("%s needs a commit observation" % c["outcome_class"])
        if c["outcome_class"] == "PROVIDER_ACKNOWLEDGED" and not (er and er["claim"]["provider_acknowledged"]):
            probs.append("PROVIDER_ACKNOWLEDGED needs an acknowledged execution receipt")
        if c["disposition"] == "COMPENSATED" and not comp:
            probs.append("COMPENSATED needs at least one compensation attempt")
        if c["disposition"] == "UNRECOVERABLE" and c["outcome_class"] != "UNRECOVERABLE":
            probs.append("UNRECOVERABLE disposition needs the UNRECOVERABLE class")
    return probs
