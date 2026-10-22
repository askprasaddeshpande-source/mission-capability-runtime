# MCR Evidence Contract v1 (`mcr-evidence/1`)

A canonical evidence envelope that is versioned separately from every MCR runtime release. Contract version `1.0.0`. Source of truth: `tools/mcr3/evc1.py` (the checked-in `mcr-evidence-1.schema.json` is generated from it and a test fails if they differ). Examples: `examples/` (one event per type, all accepted by the validator).

## What an event carries
Event id (idempotency key), type, source, time, producer (runtime, runtime version, adapter id and version, source runtime version), correlation (mission, transaction, correlation, causation, mutation-attempt ids; unknown is `null`, never zero), optional principal (with `assurance`: SELF_REPORTED, UNKNOWN or VERIFIED), optional capability (id, qualification status, provider, target, operation), optional budget, one typed claim, evidence (digest, reference, classification, trust, provenance), `authority_effect` (always `"NONE"`), optional authorization reference (a pointer to an approval made elsewhere), optional disposition and outcome class, digests (schema, policy, payload), lineage (transformations, source event, source digest, supersedes), extensions, critical names, and an integrity digest.

## Rules that do not change within major version 1
- Five layers, one per event type: OCCURRENCE, RECEIPT, VERIFIED_FACT, BUSINESS_OUTCOME, AUTHORIZATION_REFERENCE. A verification event can verify hash, signature, producer identity, provider trust or freshness; it cannot claim a business outcome.
- `trust` is derived from `provenance` and is checked on parse; an event cannot claim more than its provenance supports. Synthetic evidence is never SIGNED_TRUSTED.
- Digests: SHA-256 over canonical JSON (sorted keys, no whitespace, UTF-8, no floats). The signature-relevant `content_digest` excludes the integrity block and the verifier-controlled provenance and trust, so a verifier can attach its verdict without invalidating the producer's signature.
- A claim states what it is: an execution receipt carries `implies_commit: false`; a commit observation carries `implies_outcome: false`; a readback separates `claimed_authoritative` from `provenance_verified`.

## Using the trust label
`evidence.trust` is derived from `evidence.provenance` and checked for consistency on parse. It is **not** proof: a consumer that makes a trust decision must re-run provenance assessment itself (see the security contract, section 3b). Ids are limited to 96 characters (the `pe-event/1` limit), and `$` in a schema pattern means end of string only.

## Compatibility
| Situation | Behaviour |
|---|---|
| same major, same or older minor, no unknown fields | accepted |
| a newer minor adds an optional top-level field, name not in `critical` | accepted by an older consumer; the field is retained as unrecognized and never interpreted |
| an unknown top-level field in the same minor the consumer supports | rejected |
| an unknown name in `critical` | rejected (fail closed), whatever the version |
| a new event type, claim kind or enum value | a MAJOR change: rejected by a version-1 consumer |
| another major version | rejected |
| integrity, payload digest, trust, layer or semantic rule violated | rejected |
Minor versions only add optional top-level fields or use `extensions`. Migration within a major relabels the version, appends a lineage step, records the source digest and gives a new event id and integrity digest; it refuses a downgrade that would drop an unrecognized field and never crosses a major version. The executable matrix is `evidence/mcr3/MCR3_CONSUMER_COMPATIBILITY_MATRIX_R1.json`.

## Conformance
`python tools/mcr3/validate_mcr3_evc1.py` (201 checks: schema, examples, 70+ negative fixtures, exhaustive trust derivation, canonical form, compatibility, migration, mini-validator unit tests, optional cross-check against the `jsonschema` library when installed).
