# MCR R2.0C Authorization Consumed Notice R1

The authorization packet `MCR_R2_0_C_AUTHORIZATION_PACKET_R1.md` (frozen; not edited) carried one single-use authorization phrase bound to freeze `8CCC5B94...DAE951` and runner `A73F4647...3DDC9`.

**Status: CONSUMED on 2026-10-20.** The phrase was run once by the owner. The result is in `evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json` (one `abap_creation-create_object` call; lock file written before the send). The published phrase must not be reused: a rerun would be refused by the lock file and by the prewrite baseline check, and in any case would be a new mutation lineage requiring a fresh authorization.

Requirements for any future freeze (from the independent review): bind the model revision hash into the authorization phrase in addition to the freeze and runner hashes; record consumption in a repository notice like this one at the time of execution.

Limit: the lock file lives in the owner workspace, outside Git, so this notice is a statement by the executing agent, not independent proof of consumption.
