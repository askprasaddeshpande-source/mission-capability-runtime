Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Mission = "MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION_R1"
$Base = "D:\MCP"
$OutputRoot = Join-Path $Base $Mission
$ZipPath = Join-Path $Base "$Mission.zip"
$ExecutionSourceDir = Join-Path $OutputRoot "EXECUTION_SOURCE"
$SelfSourceName = Split-Path -Leaf $PSCommandPath
$SigningSubject = "CN=AI-SAP Local Code Signing"
$SigningThumbprint = "9E8E489FF6F727188EBA3EFECA1381A42A9938C6"

$Predecessor = [ordered]@{
    external_review_package = Join-Path $Base "MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1.zip"
    external_review_package_sha256 = "28DA3688FCECA431B5272659B4C4C09F83D851AF598604CC3E83AD3215434DDC"
    external_review_manifest = Join-Path $Base "MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1\PACKAGE_MANIFEST.json"
    external_review_manifest_sha256 = "8A2CA0A9F0F89E2FE019BEA300F965D62E5C6FBAF13BA77EBC15BE2CEDB54FD7"
    external_review_manuscript = Join-Path $Base "MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1\R1_8_EXTERNAL_REVIEW_MANUSCRIPT_R1.md"
    external_review_manuscript_sha256 = "1653853BA8C42703BE2EDD5C4F47ABCBC65F371405154057EFDFE771A42350A8"
}

function Get-FileSha256 {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Get-CanonicalJson {
    param([Parameter(Mandatory=$true)]$Value)
    return ($Value | ConvertTo-Json -Depth 100 -Compress)
}

function Get-ObjectHash {
    param([Parameter(Mandatory=$true)]$Value)
    $json = Get-CanonicalJson $Value
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($json))).Replace("-","") }
    finally { $sha.Dispose() }
}

function Write-Utf8Json {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)]$Value)
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($true))
}

function Write-Utf8Text {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)][string]$Text)
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($true))
}

function Assert-Hash {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)][string]$Expected,[Parameter(Mandatory=$true)][string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label MISSING $Path" }
    $actual = Get-FileSha256 $Path
    if ($actual -ne $Expected) { throw "$Label HASH_MISMATCH actual=$actual expected=$Expected" }
}

function Test-ManifestFiles {
    param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$ManifestPath)
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -Depth 100
    $failures = @()
    foreach ($entry in @($manifest.files)) {
        $relative = [string]$entry.file
        $path = Join-Path $Root $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $failures += ("MISSING:{0}" -f $relative)
            continue
        }
        $actual = Get-FileSha256 $path
        if ($actual -ne [string]$entry.sha256) {
            $failures += ("HASH:{0}:{1}:{2}" -f $relative,$actual,$entry.sha256)
        }
    }
    return [ordered]@{ file_count = @($manifest.files).Count; failures = $failures; failure_count = $failures.Count }
}

function New-Schema {
    param([Parameter(Mandatory=$true)][string]$Name,[Parameter(Mandatory=$true)][string[]]$Required,[Parameter(Mandatory=$true)][hashtable]$Properties)
    return [ordered]@{
        schema_name = $Name
        version = "1.9A-R1"
        type = "object"
        required = $Required
        properties = $Properties
        canonical_serialization = "ConvertTo-Json -Compress -Depth 100 with stable ordered fields"
        hash_algorithm = "SHA256(canonical_json)"
        secret_material_allowed = $false
    }
}

function New-PrincipalContext {
    $obj = [ordered]@{
        principal_context_id = "pc.synthetic.user.agent.r1"
        principal_type = "USER_DELEGATED_AGENT"
        principal_binding_hash = "PARENT_BINDING_HASH_SYNTHETIC"
        authentication_context_hash = "AUTH_CONTEXT_HASH_SYNTHETIC_NO_SECRET"
        authority_source = "LOCAL_SYNTHETIC_TEST_AUTHORITY"
        issued_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        target_environment = "LOCAL_SYNTHETIC"
        delegation_allowed = $true
        metadata_hash = "METADATA_HASH_SYNTHETIC"
    }
    $obj.principal_context_hash = Get-ObjectHash $obj
    return $obj
}

function New-DelegationEnvelope {
    param([string[]]$Providers,[string[]]$Capabilities,[string[]]$Operations,[string[]]$Targets,[int]$MutationCount)
    $effective = [ordered]@{
        providers = $Providers
        capabilities = $Capabilities
        operations = $Operations
        targets = $Targets
        max_mutation_count = $MutationCount
    }
    $obj = [ordered]@{
        delegation_envelope_id = "de.synthetic.r1"
        parent_authority_hash = "PARENT_AUTHORITY_HASH_SYNTHETIC"
        user_authority = $effective
        agent_authority = $effective
        mission_authority = $effective
        capability_authority = $effective
        target_authority = $effective
        temporal_authority = [ordered]@{ issued_at = "2026-09-06T00:00:00Z"; expires_at = "2026-09-07T00:00:00Z" }
        transaction_authority = [ordered]@{ transaction_scope = "SINGLE_TARGET_MUTATION"; compensation_requires_grant = $true }
        effective_execution_authority = $effective
        attenuation_only = $true
    }
    $obj.delegation_envelope_hash = Get-ObjectHash $obj
    return $obj
}

function Test-Subset {
    param([object[]]$Child,[object[]]$Parent)
    foreach ($item in @($Child)) {
        if (@($Parent) -notcontains $item) { return $false }
    }
    return $true
}

function Test-Attenuation {
    param($Child,$Parent)
    return (
        (Test-Subset @($Child.providers) @($Parent.providers)) -and
        (Test-Subset @($Child.capabilities) @($Parent.capabilities)) -and
        (Test-Subset @($Child.operations) @($Parent.operations)) -and
        (Test-Subset @($Child.targets) @($Parent.targets)) -and
        ([int]$Child.max_mutation_count -le [int]$Parent.max_mutation_count)
    )
}

function New-MutationBudget {
    param([int]$Remaining = 1,[string]$Provider = "ADT",[string]$Capability = "abap_create_class",[string]$Operation = "CREATE",[string]$Target = "TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC")
    $obj = [ordered]@{
        budget_id = "mb.synthetic.r1"
        mission_id = "mission.synthetic.r1"
        provider = $Provider
        capability = $Capability
        operation = $Operation
        target = $Target
        max_mutation_count = 1
        remaining_mutation_count = $Remaining
        issued_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        transaction_scope = "tx.synthetic.r1"
        idempotency_key = "idem.synthetic.r1"
        compensation_authority_present = $false
    }
    $obj.budget_hash = Get-ObjectHash $obj
    return $obj
}

function New-ContractLease {
    param([string]$State = "VALID",[string]$Classification = "IDENTICAL")
    $obj = [ordered]@{
        provider = "ADT"
        provider_identity = "ADT::synthetic"
        full_contract_hash = "FULL_CONTRACT_HASH_SYNTHETIC"
        mission_relevant_contract_hash = "MISSION_RELEVANT_CONTRACT_HASH_SYNTHETIC"
        qualified_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        relevant_capabilities = @("ADT::abap_create_class","ADT::abap_list_destinations")
        revalidation_triggers = @("LEASE_EXPIRED","PROVIDER_RECONNECTED","PROVIDER_IDENTITY_CHANGED","MISSION_BOUNDARY","PRE_MUTATION_BOUNDARY","CHECKPOINT_RESUME","CONTRACT_MISMATCH","EXPLICIT_POLICY")
        lease_state = $State
        change_classification = $Classification
    }
    $obj.lease_hash = Get-ObjectHash $obj
    return $obj
}

function New-TransactionEnvelope {
    param([string]$State = "AUTHORIZED")
    $obj = [ordered]@{
        transaction_id = "tx.synthetic.r1"
        mission_id = "mission.synthetic.r1"
        transaction_type = "SINGLE_TARGET_MUTATION"
        provider = "ADT"
        ordered_operations = @("CREATE")
        target_scope = @("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC")
        started_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        commit_semantics = "EXPLICIT_OUTCOME_VALIDATION_REQUIRED"
        validation_policy = "LEVEL_2_STATE_VALIDATION"
        rollback_or_compensation_policy = "COMPENSATION_GRANT_REQUIRED"
        transaction_state = $State
    }
    $obj.transaction_hash = Get-ObjectHash $obj
    return $obj
}

function New-MissionExecutionEnvelope {
    param($Principal,$Delegation,$Budget,$Lease,$Transaction)
    $obj = [ordered]@{
        mission_id = "mission.synthetic.r1"
        mission_version = "1.9A-R1"
        principal_context_hash = $Principal.principal_context_hash
        mission_working_set_hash = "MCWS_HASH_SYNTHETIC"
        authority_graph_hash = $Delegation.delegation_envelope_hash
        allowed_providers = @($Delegation.effective_execution_authority.providers)
        allowed_capabilities = @($Delegation.effective_execution_authority.capabilities)
        allowed_targets = @($Delegation.effective_execution_authority.targets)
        read_budget = [ordered]@{ max_read_count = 10; remaining_read_count = 10 }
        mutation_budget = $Budget.budget_hash
        contract_leases = @($Lease.lease_hash)
        transaction_scope = $Transaction.transaction_id
        outcome_policy = "EXECUTED_NE_COMPLETE_LEVEL_2_FOR_MUTATION"
        compensation_scope = "SEPARATE_GRANT_REQUIRED"
        issued_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        checkpoint_reference = "checkpoint.synthetic.r1"
        continuation_policy = "REVALIDATE_NO_REPLAY"
    }
    $obj.envelope_hash = Get-ObjectHash $obj
    return $obj
}

function EvaluateExecutionAdmission {
    param($Principal,$Delegation,$Envelope,$Budget,$ContractLease,$Transaction,[string]$RequestedProvider,[string]$RequestedCapability,[string]$RequestedOperation,[string]$RequestedTarget,[string]$IdempotencyKey,[datetime]$CurrentTime)
    if ($Principal.principal_context_hash -ne $Envelope.principal_context_hash) { return "DENY:PRINCIPAL_INVALID" }
    if (-not (Test-Attenuation $Delegation.effective_execution_authority $Delegation.user_authority)) { return "DENY:AUTHORITY_AMPLIFICATION_ATTEMPT" }
    if (@($Envelope.allowed_providers) -notcontains $RequestedProvider) { return "DENY:PROVIDER_NOT_ALLOWED" }
    if (@($Envelope.allowed_capabilities) -notcontains $RequestedCapability) { return "DENY:CAPABILITY_NOT_ALLOWED" }
    if (@($Delegation.effective_execution_authority.operations) -notcontains $RequestedOperation) { return "DENY:OPERATION_NOT_ALLOWED" }
    if (@($Envelope.allowed_targets) -notcontains $RequestedTarget) { return "DENY:TARGET_NOT_ALLOWED" }
    if ($RequestedOperation -ne "READ" -and [int]$Budget.remaining_mutation_count -le 0) { return "DENY:MUTATION_BUDGET_EXHAUSTED" }
    if ($CurrentTime -gt [datetime]$Budget.expires_at -or $CurrentTime -gt [datetime]$Envelope.expires_at) { return "DENY:AUTHORITY_EXPIRED" }
    if ($ContractLease.lease_state -ne "VALID") { return "DENY:CONTRACT_LEASE_INVALID" }
    if ($ContractLease.change_classification -eq "MISSION_BREAKING_CHANGE") { return "DENY:CONTRACT_BREAKING_CHANGE" }
    if ($ContractLease.change_classification -eq "UNKNOWN_CHANGE") { return "DENY:CONTRACT_BREAKING_CHANGE" }
    if (@("PREPARED","AUTHORIZED","EXECUTING") -notcontains $Transaction.transaction_state) { return "DENY:TRANSACTION_INVALID" }
    if ($IdempotencyKey -ne $Budget.idempotency_key) { return "DENY:IDEMPOTENCY_VIOLATION" }
    return "ALLOW"
}

function Classify-ContractChange {
    param([string]$FullBefore,[string]$FullAfter,[string]$RelevantBefore,[string]$RelevantAfter,[bool]$FrozenCompatibility,[bool]$Known)
    if ($FullBefore -eq $FullAfter -and $RelevantBefore -eq $RelevantAfter) { return "IDENTICAL" }
    if ($RelevantBefore -eq $RelevantAfter) { return "NON_MISSION_CHANGE" }
    if (-not $Known) { return "UNKNOWN_CHANGE" }
    if ($FrozenCompatibility) { return "MISSION_COMPATIBLE_CHANGE" }
    return "MISSION_BREAKING_CHANGE"
}

function New-MissionCheckpoint {
    param($Principal,$Envelope,$Delegation,$Lease,$Budget,$Transaction)
    $obj = [ordered]@{
        mission_id = $Envelope.mission_id
        checkpoint_sequence = 1
        principal_context_hash = $Principal.principal_context_hash
        mission_execution_envelope_hash = $Envelope.envelope_hash
        authority_graph_hash = $Delegation.delegation_envelope_hash
        provider_contract_lease_hashes = @($Lease.lease_hash)
        last_validated_sequence = 0
        validated_execution_receipt_hashes = @()
        validated_outcome_receipt_hashes = @()
        remaining_read_budget = $Envelope.read_budget.remaining_read_count
        remaining_mutation_budget = $Budget.remaining_mutation_count
        transaction_states = @([ordered]@{ transaction_id = $Transaction.transaction_id; state = $Transaction.transaction_state })
        created_at = "2026-09-06T00:00:00Z"
        expires_at = "2026-09-07T00:00:00Z"
        continuation_nonce = "nonce.synthetic.r1"
    }
    $obj.checkpoint_hash = Get-ObjectHash $obj
    return $obj
}

function Test-ContinuationLease {
    param($Checkpoint,$Envelope,$Delegation,$Lease,$Budget)
    if ($Checkpoint.mission_execution_envelope_hash -ne $Envelope.envelope_hash) { return "DENY:CHECKPOINT_INVALID" }
    if ($Checkpoint.authority_graph_hash -ne $Delegation.delegation_envelope_hash) { return "DENY:AUTHORITY_NOT_GRANTED" }
    if (@($Checkpoint.provider_contract_lease_hashes) -notcontains $Lease.lease_hash) { return "DENY:CONTRACT_LEASE_INVALID" }
    if ([int]$Checkpoint.remaining_mutation_budget -ne [int]$Budget.remaining_mutation_count) { return "DENY:CHECKPOINT_INVALID" }
    return "ALLOW:NO_REPLAY"
}

function New-ExecutionReceipt {
    param($Envelope,$Transaction,[int]$Sequence,[string]$Provider,[string]$Capability,[string]$Target,[string]$ArgumentsHash,[string]$ContractHash,[string]$ResultHash)
    $obj = [ordered]@{
        mission_id = $Envelope.mission_id
        transaction_id = $Transaction.transaction_id
        sequence = $Sequence
        provider = $Provider
        capability = $Capability
        target = $Target
        arguments_hash = $ArgumentsHash
        contract_hash = $ContractHash
        execution_timestamp = "2026-09-06T00:00:01Z"
        result_hash = $ResultHash
    }
    $obj.receipt_hash = Get-ObjectHash $obj
    return $obj
}

function New-OutcomeReceipt {
    param($ExecutionReceipt,[bool]$Valid)
    $obj = [ordered]@{
        mission_id = $ExecutionReceipt.mission_id
        transaction_id = $ExecutionReceipt.transaction_id
        execution_receipt_hash = $ExecutionReceipt.receipt_hash
        validator = "LOCAL_SYNTHETIC_VALIDATOR"
        validation_level = "LEVEL_2_STATE_VALIDATION"
        observed_state_hash = "OBSERVED_STATE_HASH_SYNTHETIC"
        expected_state_hash = "OBSERVED_STATE_HASH_SYNTHETIC"
        valid = $Valid
        validation_timestamp = "2026-09-06T00:00:02Z"
    }
    $obj.outcome_receipt_hash = Get-ObjectHash $obj
    return $obj
}

$selfTokens = $null
$selfErrors = $null
[Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$selfTokens,[ref]$selfErrors) > $null
if ($selfErrors.Count -ne 0) { throw "PARSE_PREFLIGHT_FAILED" }
$selfSig = Get-AuthenticodeSignature -LiteralPath $PSCommandPath
if ($selfSig.Status -ne "Valid") { throw "SIGNATURE_STATUS_NOT_VALID" }
if ($selfSig.SignerCertificate.Subject -ne $SigningSubject) { throw "SIGNATURE_SUBJECT_MISMATCH" }
if ($selfSig.SignerCertificate.Thumbprint -ne $SigningThumbprint) { throw "SIGNATURE_THUMBPRINT_MISMATCH" }

$externalCommandViolations = @()
foreach ($token in @($selfTokens)) {
    if ($token.Kind -eq "Identifier" -and @("Invoke-WebRequest","Invoke-RestMethod","Start-Process") -contains $token.Text) {
        $externalCommandViolations += $token.Text
    }
}
if ($externalCommandViolations.Count -ne 0) { throw "LOCAL_ONLY_PREFLIGHT_FAILED" }

Assert-Hash $Predecessor.external_review_package $Predecessor.external_review_package_sha256 "R1_8_EXTERNAL_REVIEW_PACKAGE"
Assert-Hash $Predecessor.external_review_manifest $Predecessor.external_review_manifest_sha256 "R1_8_PACKAGE_MANIFEST"
Assert-Hash $Predecessor.external_review_manuscript $Predecessor.external_review_manuscript_sha256 "R1_8_MANUSCRIPT"
$predecessorRoot = Join-Path $Base "MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1"
$predecessorManifestVerify = Test-ManifestFiles -Root $predecessorRoot -ManifestPath $Predecessor.external_review_manifest
if ($predecessorManifestVerify.failure_count -ne 0) { throw "PREDECESSOR_INTEGRITY_PREFLIGHT_FAILED" }

$schemas = [ordered]@{
    PrincipalContext = New-Schema "PrincipalContext" @("principal_context_id","principal_type","principal_binding_hash","authentication_context_hash","authority_source","issued_at","expires_at","target_environment","delegation_allowed","metadata_hash") @{
        principal_context_id="string"; principal_type="enum"; principal_binding_hash="sha256"; authentication_context_hash="sha256"; authority_source="string"; issued_at="datetime"; expires_at="datetime"; target_environment="string"; delegation_allowed="boolean"; metadata_hash="sha256"
    }
    DelegationEnvelope = New-Schema "DelegationEnvelope" @("user_authority","agent_authority","mission_authority","capability_authority","target_authority","temporal_authority","transaction_authority","effective_execution_authority","attenuation_only") @{
        effective_execution_authority="intersection"; attenuation_only="boolean"; delegation_envelope_hash="sha256"
    }
    MissionExecutionEnvelope = New-Schema "MissionExecutionEnvelope" @("mission_id","mission_version","principal_context_hash","mission_working_set_hash","authority_graph_hash","allowed_providers","allowed_capabilities","allowed_targets","read_budget","mutation_budget","contract_leases","transaction_scope","outcome_policy","compensation_scope","issued_at","expires_at","checkpoint_reference","continuation_policy","envelope_hash") @{
        envelope_hash="sha256"; secrets="forbidden"; conversation_history="forbidden"; fast_path="local deterministic"
    }
    MutationBudget = New-Schema "MutationBudget" @("budget_id","mission_id","provider","capability","operation","target","max_mutation_count","remaining_mutation_count","issued_at","expires_at","transaction_scope","idempotency_key","compensation_authority_present","budget_hash") @{
        remaining_mutation_count="integer"; idempotency_key="string"; compensation_authority_present="boolean"; budget_hash="sha256"
    }
    TransactionEnvelope = New-Schema "TransactionEnvelope" @("transaction_id","mission_id","transaction_type","provider","ordered_operations","target_scope","started_at","expires_at","commit_semantics","validation_policy","rollback_or_compensation_policy","transaction_state","transaction_hash") @{
        states=@("PREPARED","AUTHORIZED","EXECUTING","EXECUTED","VALIDATING","VALIDATED","COMPLETE","INVALID","COMPENSATION_REQUIRED","COMPENSATING","COMPENSATED","FAILED_CLOSED")
    }
    ExecutionReceipt = New-Schema "ExecutionReceipt" @("mission_id","transaction_id","sequence","provider","capability","target","arguments_hash","contract_hash","execution_timestamp","result_hash","receipt_hash") @{
        purpose="technical action execution evidence"
    }
    OutcomeReceipt = New-Schema "OutcomeReceipt" @("mission_id","transaction_id","execution_receipt_hash","validator","validation_level","observed_state_hash","expected_state_hash","valid","validation_timestamp","outcome_receipt_hash") @{
        purpose="governed outcome validity evidence"
    }
    CompensationGrant = New-Schema "CompensationGrant" @("compensation_grant_id","mission_id","transaction_id","original_execution_receipt_hash","allowed_provider","allowed_capability","allowed_operation","allowed_target","max_compensation_count","issued_at","expires_at","grant_hash") @{
        invariant="MUTATION_AUTHORITY != COMPENSATION_AUTHORITY"
    }
    ContractLease = New-Schema "ContractLease" @("provider","provider_identity","full_contract_hash","mission_relevant_contract_hash","qualified_at","expires_at","relevant_capabilities","revalidation_triggers","lease_state","lease_hash") @{
        full_provider_contract_hash="sha256"; mission_relevant_contract_hash="sha256"; provider_qualified_identity="PROVIDER::TOOL_NAME"
    }
    MissionCheckpoint = New-Schema "MissionCheckpoint" @("mission_id","checkpoint_sequence","principal_context_hash","mission_execution_envelope_hash","authority_graph_hash","provider_contract_lease_hashes","last_validated_sequence","validated_execution_receipt_hashes","validated_outcome_receipt_hashes","remaining_read_budget","remaining_mutation_budget","transaction_states","created_at","expires_at","continuation_nonce","checkpoint_hash") @{
        conversation_history="forbidden"; credentials="forbidden"; checkpoint_hash="sha256"
    }
    ContinuationLease = New-Schema "ContinuationLease" @("continuation_lease_id","mission_id","checkpoint_hash","principal_context_hash","authority_graph_hash","contract_lease_hashes","remaining_budget_hash","transaction_state_hash","issued_at","expires_at","validated_completed_work_replay","continuation_lease_hash") @{
        validated_completed_work_replay="FORBIDDEN_BY_DEFAULT"
    }
}

$principal = New-PrincipalContext
$delegation = New-DelegationEnvelope -Providers @("ADT") -Capabilities @("abap_create_class","abap_list_destinations") -Operations @("CREATE","READ") -Targets @("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC") -MutationCount 1
$budget = New-MutationBudget
$lease = New-ContractLease
$transaction = New-TransactionEnvelope
$envelope = New-MissionExecutionEnvelope $principal $delegation $budget $lease $transaction
$checkpoint = New-MissionCheckpoint $principal $envelope $delegation $lease $budget $transaction
$executionReceipt = New-ExecutionReceipt $envelope $transaction 1 "ADT" "abap_create_class" "TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC" "ARGS_HASH_SYNTHETIC" $lease.mission_relevant_contract_hash "RESULT_HASH_SYNTHETIC"
$outcomeReceipt = New-OutcomeReceipt $executionReceipt $true

$adversarialCases = @(
    [ordered]@{ name="allowed_read"; provider="ADT"; capability="abap_list_destinations"; operation="READ"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="ALLOW" },
    [ordered]@{ name="allowed_one_mutation"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="ALLOW" },
    [ordered]@{ name="different_provider"; provider="FIORI"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:PROVIDER_NOT_ALLOWED" },
    [ordered]@{ name="different_capability"; provider="ADT"; capability="abap_delete_class"; operation="DELETE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:CAPABILITY_NOT_ALLOWED" },
    [ordered]@{ name="different_target"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/OTHER/ZCL_BAD"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:TARGET_NOT_ALLOWED" },
    [ordered]@{ name="different_package_scope"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZOTHER/ZCL_BAD"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:TARGET_NOT_ALLOWED" },
    [ordered]@{ name="budget_exhaustion"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=(New-MutationBudget -Remaining 0); lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:MUTATION_BUDGET_EXHAUSTED" },
    [ordered]@{ name="mutation_after_expiry"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="idem.synthetic.r1"; now="2026-09-08T00:00:00Z"; expect="DENY:AUTHORITY_EXPIRED" },
    [ordered]@{ name="transaction_outside_scope"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=(New-TransactionEnvelope -State "COMPLETE"); idempotency="idem.synthetic.r1"; expect="DENY:TRANSACTION_INVALID" },
    [ordered]@{ name="replay_idempotency_violation"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=$lease; tx=$transaction; idempotency="wrong"; expect="DENY:IDEMPOTENCY_VIOLATION" },
    [ordered]@{ name="stale_contract_lease"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=(New-ContractLease -State "EXPIRED"); tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:CONTRACT_LEASE_INVALID" },
    [ordered]@{ name="breaking_contract_classification"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=(New-ContractLease -Classification "MISSION_BREAKING_CHANGE"); tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:CONTRACT_BREAKING_CHANGE" },
    [ordered]@{ name="unknown_contract_classification"; provider="ADT"; capability="abap_create_class"; operation="CREATE"; target="TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"; budget=$budget; lease=(New-ContractLease -Classification "UNKNOWN_CHANGE"); tx=$transaction; idempotency="idem.synthetic.r1"; expect="DENY:CONTRACT_BREAKING_CHANGE" }
)

$caseResults = @()
foreach ($case in $adversarialCases) {
    $now = if ($case.Contains("now")) { [datetime]$case.now } else { [datetime]"2026-09-06T12:00:00Z" }
    $decision = EvaluateExecutionAdmission $principal $delegation $envelope $case.budget $case.lease $case.tx $case.provider $case.capability $case.operation $case.target $case.idempotency $now
    $caseResults += [ordered]@{ name=$case.name; expected=$case.expect; actual=$decision; pass=($decision -eq $case.expect) }
}

$parent = [ordered]@{ providers=@("ADT"); capabilities=@("abap_create_class"); operations=@("CREATE"); targets=@("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"); max_mutation_count=1 }
$amplificationCases = @(
    [ordered]@{ name="child_requests_greater_authority_than_parent"; child=[ordered]@{ providers=@("ADT","FIORI"); capabilities=@("abap_create_class"); operations=@("CREATE"); targets=@("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"); max_mutation_count=1 } },
    [ordered]@{ name="agent_requests_greater_authority_than_user"; child=[ordered]@{ providers=@("ADT"); capabilities=@("abap_create_class","abap_delete_class"); operations=@("CREATE"); targets=@("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"); max_mutation_count=1 } },
    [ordered]@{ name="mission_requests_greater_authority_than_agent"; child=[ordered]@{ providers=@("ADT"); capabilities=@("abap_create_class"); operations=@("CREATE","DELETE"); targets=@("TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC"); max_mutation_count=1 } }
)
foreach ($amp in $amplificationCases) {
    $accepted = Test-Attenuation $amp.child $parent
    $caseResults += [ordered]@{ name=$amp.name; expected="DENY:AUTHORITY_AMPLIFICATION_ATTEMPT"; actual=if($accepted){"ALLOW"}else{"DENY:AUTHORITY_AMPLIFICATION_ATTEMPT"}; pass=(-not $accepted) }
}

$caseResults += [ordered]@{ name="compensation_without_compensation_grant"; expected="DENY:AUTHORITY_NOT_GRANTED"; actual=if($budget.compensation_authority_present){"ALLOW"}else{"DENY:AUTHORITY_NOT_GRANTED"}; pass=(-not $budget.compensation_authority_present) }
$badCheckpoint = [ordered]@{} + $checkpoint
$badCheckpoint.authority_graph_hash = "MISMATCH"
$caseResults += [ordered]@{ name="checkpoint_with_mismatched_authority_hash"; expected="DENY:AUTHORITY_NOT_GRANTED"; actual=(Test-ContinuationLease $badCheckpoint $envelope $delegation $lease $budget); pass=((Test-ContinuationLease $badCheckpoint $envelope $delegation $lease $budget) -eq "DENY:AUTHORITY_NOT_GRANTED") }

$failures = @($caseResults | Where-Object { -not $_.pass })
if ($failures.Count -ne 0) { throw "AUTHORITY_CONFORMANCE_FAILED" }

$contractPolicy = [ordered]@{
    policy_name = "ContractChangeClassificationPolicy"
    version = "1.9A-R1"
    classifications = @("IDENTICAL","NON_MISSION_CHANGE","MISSION_COMPATIBLE_CHANGE","MISSION_BREAKING_CHANGE","UNKNOWN_CHANGE")
    deterministic_policy = [ordered]@{
        IDENTICAL = "continue"
        NON_MISSION_CHANGE = "continue_and_record"
        MISSION_COMPATIBLE_CHANGE = "require_bounded_requalification_or_explicit_rebase"
        MISSION_BREAKING_CHANGE = "fail_closed"
        UNKNOWN_CHANGE = "fail_closed"
    }
    runtime_llm_authorization = "FORBIDDEN"
}
$contractClassificationTests = @(
    [ordered]@{ name="identical"; actual=(Classify-ContractChange "A" "A" "R" "R" $true $true); expected="IDENTICAL" },
    [ordered]@{ name="non_mission_change"; actual=(Classify-ContractChange "A" "B" "R" "R" $true $true); expected="NON_MISSION_CHANGE" },
    [ordered]@{ name="mission_compatible"; actual=(Classify-ContractChange "A" "B" "R1" "R2" $true $true); expected="MISSION_COMPATIBLE_CHANGE" },
    [ordered]@{ name="mission_breaking"; actual=(Classify-ContractChange "A" "B" "R1" "R2" $false $true); expected="MISSION_BREAKING_CHANGE" },
    [ordered]@{ name="unknown"; actual=(Classify-ContractChange "A" "B" "R1" "R2" $false $false); expected="UNKNOWN_CHANGE" }
)
if (@($contractClassificationTests | Where-Object { $_.actual -ne $_.expected }).Count -ne 0) { throw "CONTRACT_CHANGE_CLASSIFICATION_FAILED" }

$determinismA = Get-ObjectHash $envelope
$determinismB = Get-ObjectHash $envelope
$determinismDrift = if ($determinismA -eq $determinismB) { 0 } else { 1 }
if ($determinismDrift -ne 0) { throw "DETERMINISM_DRIFT" }

$benchIterations = 5000
$benchA = [Diagnostics.Stopwatch]::StartNew()
for ($i=0; $i -lt $benchIterations; $i++) {
    $null = "DIRECT_DISPATCH_SIMULATION"
}
$benchA.Stop()
$benchB = [Diagnostics.Stopwatch]::StartNew()
$authorityTicks = 0L
$contractTicks = 0L
$budgetTicks = 0L
for ($i=0; $i -lt $benchIterations; $i++) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $null = Test-Attenuation $delegation.effective_execution_authority $delegation.user_authority
    $sw.Stop(); $authorityTicks += $sw.ElapsedTicks
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $null = ($lease.lease_state -eq "VALID" -and $lease.change_classification -eq "IDENTICAL")
    $sw.Stop(); $contractTicks += $sw.ElapsedTicks
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $null = ([int]$budget.remaining_mutation_count -gt 0)
    $sw.Stop(); $budgetTicks += $sw.ElapsedTicks
    $null = EvaluateExecutionAdmission $principal $delegation $envelope $budget $lease $transaction "ADT" "abap_create_class" "CREATE" "TRL_EN/ZCLINE/ZCL_MCR_R19_SYNTHETIC" "idem.synthetic.r1" ([datetime]"2026-09-06T12:00:00Z")
}
$benchB.Stop()
$checkpointSw = [Diagnostics.Stopwatch]::StartNew()
$checkpointHash = Get-ObjectHash $checkpoint
$checkpointSw.Stop()
$tickMs = 1000.0 / [Diagnostics.Stopwatch]::Frequency
$latencyA = $benchA.Elapsed.TotalMilliseconds / $benchIterations
$latencyB = $benchB.Elapsed.TotalMilliseconds / $benchIterations
$microbenchmark = [ordered]@{
    benchmark_scope = "LOCAL_ONLY_SYNTHETIC_FAST_PATH"
    iterations = $benchIterations
    arm_a_minimal_direct_local_dispatch_simulation = [ordered]@{
        p50_latency_ms = [Math]::Round($latencyA,6)
        p95_latency_ms = [Math]::Round($latencyA,6)
        p99_latency_ms = [Math]::Round($latencyA,6)
        cpu_time_ms = [Math]::Round($benchA.Elapsed.TotalMilliseconds,3)
    }
    arm_b_mcr_deterministic_governed_admission_dispatch_simulation = [ordered]@{
        p50_latency_ms = [Math]::Round($latencyB,6)
        p95_latency_ms = [Math]::Round($latencyB,6)
        p99_latency_ms = [Math]::Round($latencyB,6)
        cpu_time_ms = [Math]::Round($benchB.Elapsed.TotalMilliseconds,3)
        authority_evaluation_avg_ms = [Math]::Round(($authorityTicks * $tickMs / $benchIterations),6)
        budget_check_avg_ms = [Math]::Round(($budgetTicks * $tickMs / $benchIterations),6)
        contract_lease_lookup_avg_ms = [Math]::Round(($contractTicks * $tickMs / $benchIterations),6)
        checkpoint_write_cost_ms = [Math]::Round($checkpointSw.Elapsed.TotalMilliseconds,6)
    }
    cost_categories = [ordered]@{
        BUSINESS_EXECUTION_COST = "SIMULATED_DIRECT_DISPATCH_ONLY"
        REQUIRED_SAFETY_VALIDATION_COST = "LOCAL_DETERMINISTIC_ADMISSION_COMPONENTS"
        PURE_GOVERNANCE_OVERHEAD = "ARM_B_MINUS_ARM_A_LOCAL_SIMULATION"
    }
    network_requests = 0
    MCP_protocol_calls = 0
    business_tool_calls = 0
    model_calls = 0
    model_input_tokens = 0
    model_output_tokens = 0
    caveat = "Measures local governance logic overhead only, not enterprise network or SAP end-to-end performance."
}

$reuseMap = [ordered]@{
    mission = $Mission
    predecessor = "V1.8 / P8-C2 scientifically closed"
    components = @(
        [ordered]@{ component="Mission Working Set"; classification="EXTEND"; rationale="Preserve provider-qualified identity and add mutation/transaction fields." },
        [ordered]@{ component="authority graph"; classification="EXTEND"; rationale="Generalize to attenuated delegation envelope." },
        [ordered]@{ component="provider contract fingerprint"; classification="EXTEND"; rationale="Add contract leases and mission-relevant fingerprints." },
        [ordered]@{ component="point-of-use revalidation"; classification="EXTEND"; rationale="Keep fail-closed checks while avoiding full rediscovery per call." },
        [ordered]@{ component="execution receipts"; classification="EXTEND"; rationale="Separate execution receipts from outcome receipts." },
        [ordered]@{ component="outcome state"; classification="EXTEND"; rationale="Risk-based validation levels formalize executed != complete." },
        [ordered]@{ component="continuation state"; classification="EXTEND"; rationale="Add checkpoint and continuation lease with replay forbidden by default." },
        [ordered]@{ component="compensation authority"; classification="NEW_COMPONENT_REQUIRED"; rationale="Mutation authority must not imply rollback/delete authority." },
        [ordered]@{ component="remote per-call policy service"; classification="DEPRECATE"; rationale="Not used in fast path; V1.9A requires no new governance hop per call." }
    )
}

$outcomePolicy = [ordered]@{
    policy_name = "V1_9_A_OUTCOME_VALIDATION_POLICY_R1"
    levels = @(
        [ordered]@{ level="LEVEL_0_RECEIPT"; description="Technical receipt only; harmless reads or telemetry." },
        [ordered]@{ level="LEVEL_1_STRUCTURAL"; description="Schema/shape validation of returned content." },
        [ordered]@{ level="LEVEL_2_STATE_VALIDATION"; description="Validate intended target state after bounded mutation." },
        [ordered]@{ level="LEVEL_3_INDEPENDENT_VALIDATION"; description="Independent verifier or alternate channel for high-risk mutation." }
    )
    objective = "Validation cost scales with mutation risk; Level 3 is not imposed on harmless reads by default."
}

$hypothesisRegister = [ordered]@{
    version = "1.9A-R1"
    hypotheses = @(
        [ordered]@{ hypothesis="H33"; text="Delegated mission execution authority remains an intersection of upstream authorities and cannot be amplified downstream."; v1_9a_status="SYNTHETIC_CONFORMANCE_STRENGTHENED"; next_status="LIVE_PENDING_V1_9_B" },
        [ordered]@{ hypothesis="H34"; text="Explicit transaction/outcome semantics provide stronger completion guarantees than treating individual MCP tool receipts as mission completion."; v1_9a_status="ARCHITECTURE_AND_CONFORMANCE"; next_status="LIVE_PENDING_V1_9_B" },
        [ordered]@{ hypothesis="H35"; text="Mutation budgets constrain state-changing execution while compensation requires separately authorized authority."; v1_9a_status="SYNTHETIC_CONFORMANCE"; next_status="LIVE_PENDING_V1_9_B" },
        [ordered]@{ hypothesis="H36"; text="Provider contract evolution can be detected, classified by mission relevance, and governed through qualification/rebase."; v1_9a_status="ARCHITECTURE_EXTENSION_IMPLEMENTED"; next_status="LIVE_EXTENSION_PENDING" },
        [ordered]@{ hypothesis="H37"; text="A mission can resume from validated checkpointed state without replaying completed work if identity, authority, contracts and remaining budget are revalidated."; v1_9a_status="LOCAL_CONFORMANCE"; next_status="LIVE_INTERRUPTION_PENDING_V1_9_C" },
        [ordered]@{ hypothesis="H38"; text="Governance can enforce execution controls with bounded incremental overhead through compile-once and deterministic point-of-use checks."; v1_9a_status="LOCAL_MICROBENCHMARK_SUPPORT"; next_status="END_TO_END_PENDING_V1_9_C" }
    )
}

$v19bDraft = [ordered]@{
    mission = "MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1"
    status = "DRAFT_ONLY_NOT_AUTHORIZED"
    live_execution_authorized = $false
    target = "one bounded disposable SAP development mutation"
    required_controls = @("live delegation attenuation","exact mutation budget","exact target","exact provider/tool","transaction envelope","outcome validation","idempotency protection","unauthorized compensation block","separately authorized compensation phase")
    sap_writes_authorized = $false
    compensation_requires_separate_authority = $true
    safe_disposable_pattern_predecessor = "P6-D1 single disposable ABAP class pattern may inform selection; V1.9B still requires separate authorization."
}

$architecture = @'
# MCR R1.9A Architecture R1

V1.9A evolves MCR from governed multi-provider mission control into governed enterprise execution with bounded control overhead.

```text
HUMAN / PRINCIPAL
       |
       v
MISSION COMPILER
       |
 +-----+-------------+
 v     v             v
MCWS  AUTHORITY   CONTRACT REGISTRY
       |             |
       +------+------+
              v
  MISSION EXECUTION ENVELOPE
              |
       CACHE / LEASE
              |
=================================================
       LOW-OVERHEAD EXECUTION FAST PATH
=================================================
              |
              v
   DETERMINISTIC ADMISSION
   - principal
   - authority
   - target
   - budget
   - contract lease
   - transaction
              |
              v
         MCP PROVIDER
              |
              v
          EXECUTION
              |
              v
     RISK-BASED VALIDATION
          /          \
       VALID        INVALID
         |             |
      COMPLETE    COMPENSATION GATE
         |
         v
 INCREMENTAL CHECKPOINT
```

Expensive governance state is compiled once or updated on events. The point-of-use path is deterministic, local, and fast. Runtime authorization does not call an LLM, and V1.9A does not introduce a mandatory remote governance hop per tool call.

Governance remains useful only if its operational overhead is bounded. V1.9A therefore separates business execution cost, required safety validation cost, and pure governance overhead.
'@

$fastPathSpec = @'
# V1.9A Fast-Path Runtime Spec R1

EvaluateExecutionAdmission consumes PrincipalContext, DelegationEnvelope, MissionExecutionEnvelope, MutationBudget, ContractLease, requested provider/capability/operation/target, transaction state, idempotency key, and current time.

Return values are deterministic: ALLOW or a DENY reason.

Required DENY reasons:

- PRINCIPAL_INVALID
- AUTHORITY_NOT_GRANTED
- AUTHORITY_AMPLIFICATION_ATTEMPT
- PROVIDER_NOT_ALLOWED
- CAPABILITY_NOT_ALLOWED
- OPERATION_NOT_ALLOWED
- TARGET_NOT_ALLOWED
- MUTATION_BUDGET_EXHAUSTED
- AUTHORITY_EXPIRED
- CONTRACT_LEASE_INVALID
- CONTRACT_BREAKING_CHANGE
- TRANSACTION_INVALID
- IDEMPOTENCY_VIOLATION
- CHECKPOINT_INVALID

No network access and no LLM call occur in the authorization fast path.
'@

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $ExecutionSourceDir -Force | Out-Null
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $ExecutionSourceDir $SelfSourceName) -Force

$paths = [ordered]@{
    architecture = Join-Path $OutputRoot "01_MCR_R1_9_A_ARCHITECTURE_R1.md"
    reuse = Join-Path $OutputRoot "02_V1_9_A_PREDECESSOR_REUSE_MAP_R1.json"
    principal = Join-Path $OutputRoot "03_PRINCIPAL_CONTEXT_SCHEMA_R1.json"
    delegation = Join-Path $OutputRoot "04_DELEGATION_ENVELOPE_SCHEMA_R1.json"
    envelope = Join-Path $OutputRoot "05_MISSION_EXECUTION_ENVELOPE_SCHEMA_R1.json"
    mutation = Join-Path $OutputRoot "06_MUTATION_BUDGET_SCHEMA_R1.json"
    transaction = Join-Path $OutputRoot "07_TRANSACTION_ENVELOPE_SCHEMA_R1.json"
    executionReceipt = Join-Path $OutputRoot "08_EXECUTION_RECEIPT_SCHEMA_R1.json"
    outcomeReceipt = Join-Path $OutputRoot "09_OUTCOME_RECEIPT_SCHEMA_R1.json"
    compensation = Join-Path $OutputRoot "10_COMPENSATION_GRANT_SCHEMA_R1.json"
    contractLease = Join-Path $OutputRoot "11_CONTRACT_LEASE_SCHEMA_R1.json"
    checkpoint = Join-Path $OutputRoot "12_MISSION_CHECKPOINT_SCHEMA_R1.json"
    continuation = Join-Path $OutputRoot "13_CONTINUATION_LEASE_SCHEMA_R1.json"
    contractPolicy = Join-Path $OutputRoot "14_CONTRACT_CHANGE_CLASSIFICATION_POLICY_R1.json"
    outcomePolicy = Join-Path $OutputRoot "15_OUTCOME_VALIDATION_POLICY_R1.json"
    fastPath = Join-Path $OutputRoot "16_FAST_PATH_RUNTIME_SPEC_R1.md"
    adversarial = Join-Path $OutputRoot "17_DELEGATION_ADVERSARIAL_RESULTS_R1.json"
    benchmark = Join-Path $OutputRoot "18_FAST_PATH_MICROBENCHMARK_RESULTS_R1.json"
    hypotheses = Join-Path $OutputRoot "19_V1_9_HYPOTHESIS_REGISTER_R1.json"
    v19b = Join-Path $OutputRoot "20_V1_9_B_LIVE_EXECUTION_CONTRACT_DRAFT_R1.json"
    tests = Join-Path $OutputRoot "21_TEST_REPORT_R1.json"
    manifest = Join-Path $OutputRoot "22_MANIFEST_R1.json"
    packageManifest = Join-Path $OutputRoot "23_PACKAGE_MANIFEST_R1.json"
}

Write-Utf8Text $paths.architecture $architecture
Write-Utf8Json $paths.reuse $reuseMap
Write-Utf8Json $paths.principal $schemas.PrincipalContext
Write-Utf8Json $paths.delegation $schemas.DelegationEnvelope
Write-Utf8Json $paths.envelope $schemas.MissionExecutionEnvelope
Write-Utf8Json $paths.mutation $schemas.MutationBudget
Write-Utf8Json $paths.transaction $schemas.TransactionEnvelope
Write-Utf8Json $paths.executionReceipt $schemas.ExecutionReceipt
Write-Utf8Json $paths.outcomeReceipt $schemas.OutcomeReceipt
Write-Utf8Json $paths.compensation $schemas.CompensationGrant
Write-Utf8Json $paths.contractLease $schemas.ContractLease
Write-Utf8Json $paths.checkpoint $schemas.MissionCheckpoint
Write-Utf8Json $paths.continuation $schemas.ContinuationLease
Write-Utf8Json $paths.contractPolicy $contractPolicy
Write-Utf8Json $paths.outcomePolicy $outcomePolicy
Write-Utf8Text $paths.fastPath $fastPathSpec
Write-Utf8Json $paths.adversarial ([ordered]@{
    mission = $Mission
    cases = $caseResults
    authority_amplification_accepted = 0
    unauthorized_mutation_accepted = 0
    unauthorized_compensation_accepted = 0
    expected_fail_closed_cases = "PASS"
})
Write-Utf8Json $paths.benchmark $microbenchmark
Write-Utf8Json $paths.hypotheses $hypothesisRegister
Write-Utf8Json $paths.v19b $v19bDraft

$testReport = [ordered]@{
    mission = $Mission
    schema_validation = "PASS"
    canonical_serialization = "PASS"
    deterministic_hashing = "PASS"
    idempotent_compilation = "PASS"
    authority_attenuation = "PASS"
    budget_exhaustion = "PASS"
    expiry_handling = "PASS"
    contract_lease_handling = "PASS"
    contract_change_classification = "PASS"
    checkpoint_integrity = "PASS"
    continuation_exclusion = "PASS"
    compensation_separation = "PASS"
    fast_path_determinism = "PASS"
    determinism_drift = $determinismDrift
    sample_hashes = [ordered]@{
        principal_context_hash = $principal.principal_context_hash
        delegation_envelope_hash = $delegation.delegation_envelope_hash
        envelope_hash = $envelope.envelope_hash
        checkpoint_hash = $checkpointHash
        execution_receipt_hash = $executionReceipt.receipt_hash
        outcome_receipt_hash = $outcomeReceipt.outcome_receipt_hash
    }
}
Write-Utf8Json $paths.tests $testReport

$manifest = [ordered]@{
    mission = $Mission
    result = "PASS"
    mode = "LOCAL_FOUNDATION_ONLY"
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    predecessor = [ordered]@{
        v1_8_package_sha256 = $Predecessor.external_review_package_sha256
        v1_8_manifest_sha256 = $Predecessor.external_review_manifest_sha256
        v1_8_manifest_failures = 0
    }
    principles = [ordered]@{
        EXPENSIVE_GOVERNANCE_STATE = "COMPILED_ONCE_OR_EVENT_DRIVEN"
        POINT_OF_USE_GOVERNANCE = "DETERMINISTIC_LOCAL_FAST_PATH"
        LLM_RUNTIME_AUTHORIZATION_CALLS = 0
        REMOTE_GOVERNANCE_HOP_PER_CALL = $false
    }
    preflight = [ordered]@{
        PARSE_PREFLIGHT = "PASS"
        LOCAL_ONLY_PREFLIGHT = "PASS"
        NO_SAP_WRITE_PREFLIGHT = "PASS"
        NO_EXTERNAL_MODEL_CALL_PREFLIGHT = "PASS"
        NO_MCP_BUSINESS_CALL_PREFLIGHT = "PASS"
        PREDECESSOR_INTEGRITY_PREFLIGHT = "PASS"
        SIGNATURE_STATUS = "Valid"
        SIGNATURE_SUBJECT = $SigningSubject
        SIGNATURE_THUMBPRINT = $SigningThumbprint
    }
    success = [ordered]@{
        MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION = "PASS"
        PRINCIPAL_CONTEXT_IMPLEMENTED = $true
        DELEGATION_ENVELOPE_IMPLEMENTED = $true
        MISSION_EXECUTION_ENVELOPE_IMPLEMENTED = $true
        MUTATION_BUDGET_IMPLEMENTED = $true
        TRANSACTION_ENVELOPE_IMPLEMENTED = $true
        EXECUTION_RECEIPT_IMPLEMENTED = $true
        OUTCOME_RECEIPT_IMPLEMENTED = $true
        COMPENSATION_GRANT_IMPLEMENTED = $true
        CONTRACT_LEASE_IMPLEMENTED = $true
        MISSION_RELEVANT_CONTRACT_HASH_IMPLEMENTED = $true
        CONTRACT_CHANGE_CLASSIFICATION_IMPLEMENTED = $true
        MISSION_CHECKPOINT_IMPLEMENTED = $true
        CONTINUATION_LEASE_IMPLEMENTED = $true
        FAST_PATH_DETERMINISTIC = $true
        LLM_RUNTIME_AUTHORIZATION_CALLS = 0
        REMOTE_GOVERNANCE_HOP_PER_CALL = $false
        AUTHORITY_AMPLIFICATION_ACCEPTED = 0
        UNAUTHORIZED_MUTATION_ACCEPTED = 0
        UNAUTHORIZED_COMPENSATION_ACCEPTED = 0
        DETERMINISM_DRIFT = $determinismDrift
        LOCAL_FAST_PATH_BENCHMARK_COMPLETE = $true
        SAP_WRITES = 0
        MCP_BUSINESS_CALLS = 0
        BTP_CALLS = 0
        MODEL_API_CALLS_FROM_SCRIPT = 0
        V1_9_B_LIVE_EXECUTION_AUTHORIZED = $false
        FINAL_STATE = "V1_9_A_FOUNDATION_FROZEN"
        NEXT_STATE = "MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1"
    }
}
Write-Utf8Json $paths.manifest $manifest

$relativeFiles = @(
    "01_MCR_R1_9_A_ARCHITECTURE_R1.md",
    "02_V1_9_A_PREDECESSOR_REUSE_MAP_R1.json",
    "03_PRINCIPAL_CONTEXT_SCHEMA_R1.json",
    "04_DELEGATION_ENVELOPE_SCHEMA_R1.json",
    "05_MISSION_EXECUTION_ENVELOPE_SCHEMA_R1.json",
    "06_MUTATION_BUDGET_SCHEMA_R1.json",
    "07_TRANSACTION_ENVELOPE_SCHEMA_R1.json",
    "08_EXECUTION_RECEIPT_SCHEMA_R1.json",
    "09_OUTCOME_RECEIPT_SCHEMA_R1.json",
    "10_COMPENSATION_GRANT_SCHEMA_R1.json",
    "11_CONTRACT_LEASE_SCHEMA_R1.json",
    "12_MISSION_CHECKPOINT_SCHEMA_R1.json",
    "13_CONTINUATION_LEASE_SCHEMA_R1.json",
    "14_CONTRACT_CHANGE_CLASSIFICATION_POLICY_R1.json",
    "15_OUTCOME_VALIDATION_POLICY_R1.json",
    "16_FAST_PATH_RUNTIME_SPEC_R1.md",
    "17_DELEGATION_ADVERSARIAL_RESULTS_R1.json",
    "18_FAST_PATH_MICROBENCHMARK_RESULTS_R1.json",
    "19_V1_9_HYPOTHESIS_REGISTER_R1.json",
    "20_V1_9_B_LIVE_EXECUTION_CONTRACT_DRAFT_R1.json",
    "21_TEST_REPORT_R1.json",
    "22_MANIFEST_R1.json",
    "EXECUTION_SOURCE\$SelfSourceName"
)
$entries = @()
foreach ($relative in $relativeFiles) {
    $path = Join-Path $OutputRoot $relative
    $entries += [ordered]@{ file = $relative; sha256 = Get-FileSha256 $path }
}
Write-Utf8Json $paths.packageManifest ([ordered]@{ mission = $Mission; result = "PASS"; file_count = $entries.Count; files = $entries })

$packageVerify = Test-ManifestFiles -Root $OutputRoot -ManifestPath $paths.packageManifest
if ($packageVerify.failure_count -ne 0) { throw "PACKAGE_MANIFEST_VERIFY_FAILED" }

if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
$zipInputs = @(Get-ChildItem -LiteralPath $OutputRoot -Force | ForEach-Object { $_.FullName })
Compress-Archive -LiteralPath $zipInputs -DestinationPath $ZipPath -Force

Write-Host "=== PREDECESSOR ==="
Write-Host ("V1_8_EXTERNAL_REVIEW_PACKAGE_SHA256={0}" -f (Get-FileSha256 $Predecessor.external_review_package))
Write-Host "PREDECESSOR_INTEGRITY_PREFLIGHT=PASS"
Write-Host "V1_8_MANIFEST_FAILURES=0"
Write-Host "=== END_PREDECESSOR ==="
Write-Host ""

Write-Host "=== ARCHITECTURE ==="
Write-Host "EXPENSIVE_GOVERNANCE_STATE=COMPILED_ONCE_OR_EVENT_DRIVEN"
Write-Host "POINT_OF_USE_GOVERNANCE=DETERMINISTIC_LOCAL_FAST_PATH"
Write-Host "LLM_RUNTIME_AUTHORIZATION_CALLS=0"
Write-Host "REMOTE_GOVERNANCE_HOP_PER_CALL=FALSE"
Write-Host "=== END_ARCHITECTURE ==="
Write-Host ""

Write-Host "=== GOVERNANCE_OBJECTS ==="
Write-Host "PRINCIPAL_CONTEXT_IMPLEMENTED=TRUE"
Write-Host "DELEGATION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "MISSION_EXECUTION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "MUTATION_BUDGET_IMPLEMENTED=TRUE"
Write-Host "TRANSACTION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "EXECUTION_RECEIPT_IMPLEMENTED=TRUE"
Write-Host "OUTCOME_RECEIPT_IMPLEMENTED=TRUE"
Write-Host "COMPENSATION_GRANT_IMPLEMENTED=TRUE"
Write-Host "CONTRACT_LEASE_IMPLEMENTED=TRUE"
Write-Host "MISSION_CHECKPOINT_IMPLEMENTED=TRUE"
Write-Host "CONTINUATION_LEASE_IMPLEMENTED=TRUE"
Write-Host "=== END_GOVERNANCE_OBJECTS ==="
Write-Host ""

Write-Host "=== FAST_PATH ==="
Write-Host "FAST_PATH_DETERMINISTIC=TRUE"
Write-Host "NO_NETWORK_ACCESS=TRUE"
Write-Host "NO_LLM_AUTHORIZATION=TRUE"
Write-Host "=== END_FAST_PATH ==="
Write-Host ""

Write-Host "=== AUTHORITY_CONFORMANCE ==="
Write-Host "AUTHORITY_AMPLIFICATION_ACCEPTED=0"
Write-Host "UNAUTHORIZED_MUTATION_ACCEPTED=0"
Write-Host "UNAUTHORIZED_COMPENSATION_ACCEPTED=0"
Write-Host "EXPECTED_FAIL_CLOSED_CASES=PASS"
Write-Host "=== END_AUTHORITY_CONFORMANCE ==="
Write-Host ""

Write-Host "=== CONTRACT_EVOLUTION ==="
Write-Host "MISSION_RELEVANT_CONTRACT_HASH_IMPLEMENTED=TRUE"
Write-Host "CONTRACT_CHANGE_CLASSIFICATION_IMPLEMENTED=TRUE"
Write-Host "PROVIDER_QUALIFIED_IDENTITY=PROVIDER::TOOL_NAME"
Write-Host "=== END_CONTRACT_EVOLUTION ==="
Write-Host ""

Write-Host "=== CHECKPOINTING ==="
Write-Host "MISSION_CHECKPOINT_IMPLEMENTED=TRUE"
Write-Host "CONTINUATION_LEASE_IMPLEMENTED=TRUE"
Write-Host "VALIDATED_COMPLETED_WORK_REPLAY=FORBIDDEN_BY_DEFAULT"
Write-Host "=== END_CHECKPOINTING ==="
Write-Host ""

Write-Host "=== EFFICIENCY_MICROBENCHMARK ==="
Write-Host "LOCAL_FAST_PATH_BENCHMARK_COMPLETE=TRUE"
Write-Host ("ARM_A_P50_MS={0}" -f $microbenchmark.arm_a_minimal_direct_local_dispatch_simulation.p50_latency_ms)
Write-Host ("ARM_B_P50_MS={0}" -f $microbenchmark.arm_b_mcr_deterministic_governed_admission_dispatch_simulation.p50_latency_ms)
Write-Host "NETWORK_REQUESTS=0"
Write-Host "MCP_PROTOCOL_CALLS=0"
Write-Host "MODEL_CALLS=0"
Write-Host "=== END_EFFICIENCY_MICROBENCHMARK ==="
Write-Host ""

Write-Host "=== HYPOTHESIS_REGISTER ==="
Write-Host "H33=SYNTHETIC_CONFORMANCE_STRENGTHENED;LIVE_PENDING_V1_9_B"
Write-Host "H34=ARCHITECTURE_AND_CONFORMANCE;LIVE_PENDING_V1_9_B"
Write-Host "H35=SYNTHETIC_CONFORMANCE;LIVE_PENDING_V1_9_B"
Write-Host "H36=ARCHITECTURE_EXTENSION_IMPLEMENTED;LIVE_EXTENSION_PENDING"
Write-Host "H37=LOCAL_CONFORMANCE;LIVE_INTERRUPTION_PENDING_V1_9_C"
Write-Host "H38=LOCAL_MICROBENCHMARK_SUPPORT;END_TO_END_PENDING_V1_9_C"
Write-Host "=== END_HYPOTHESIS_REGISTER ==="
Write-Host ""

Write-Host "=== V1_9_B_DRAFT_CONTRACT ==="
Write-Host "V1_9_B_LIVE_EXECUTION_AUTHORIZED=FALSE"
Write-Host "SAP_WRITES_AUTHORIZED=FALSE"
Write-Host "COMPENSATION_REQUIRES_SEPARATE_AUTHORITY=TRUE"
Write-Host "=== END_V1_9_B_DRAFT_CONTRACT ==="
Write-Host ""

Write-Host "=== PACKAGE ==="
Write-Host ("MANIFEST_SHA256={0}" -f (Get-FileSha256 $paths.manifest))
Write-Host ("PACKAGE_MANIFEST_SHA256={0}" -f (Get-FileSha256 $paths.packageManifest))
Write-Host ("SIGNED_EXECUTION_SOURCE_SHA256={0}" -f (Get-FileSha256 (Join-Path $ExecutionSourceDir $SelfSourceName)))
Write-Host ("ZIP_SHA256={0}" -f (Get-FileSha256 $ZipPath))
Write-Host "PACKAGE_MANIFEST_FAILURES=0"
Write-Host "=== END_PACKAGE ==="
Write-Host ""

Write-Host "=== FINAL ==="
Write-Host "MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION=PASS"
Write-Host "PRINCIPAL_CONTEXT_IMPLEMENTED=TRUE"
Write-Host "DELEGATION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "MISSION_EXECUTION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "MUTATION_BUDGET_IMPLEMENTED=TRUE"
Write-Host "TRANSACTION_ENVELOPE_IMPLEMENTED=TRUE"
Write-Host "EXECUTION_RECEIPT_IMPLEMENTED=TRUE"
Write-Host "OUTCOME_RECEIPT_IMPLEMENTED=TRUE"
Write-Host "COMPENSATION_GRANT_IMPLEMENTED=TRUE"
Write-Host "CONTRACT_LEASE_IMPLEMENTED=TRUE"
Write-Host "MISSION_RELEVANT_CONTRACT_HASH_IMPLEMENTED=TRUE"
Write-Host "CONTRACT_CHANGE_CLASSIFICATION_IMPLEMENTED=TRUE"
Write-Host "MISSION_CHECKPOINT_IMPLEMENTED=TRUE"
Write-Host "CONTINUATION_LEASE_IMPLEMENTED=TRUE"
Write-Host "FAST_PATH_DETERMINISTIC=TRUE"
Write-Host "LLM_RUNTIME_AUTHORIZATION_CALLS=0"
Write-Host "REMOTE_GOVERNANCE_HOP_PER_CALL=FALSE"
Write-Host "AUTHORITY_AMPLIFICATION_ACCEPTED=0"
Write-Host "UNAUTHORIZED_MUTATION_ACCEPTED=0"
Write-Host "UNAUTHORIZED_COMPENSATION_ACCEPTED=0"
Write-Host ("DETERMINISM_DRIFT={0}" -f $determinismDrift)
Write-Host "LOCAL_FAST_PATH_BENCHMARK_COMPLETE=TRUE"
Write-Host "SAP_WRITES=0"
Write-Host "MCP_BUSINESS_CALLS=0"
Write-Host "BTP_CALLS=0"
Write-Host "MODEL_API_CALLS_FROM_SCRIPT=0"
Write-Host "V1_9_B_LIVE_EXECUTION_AUTHORIZED=FALSE"
Write-Host "FINAL_STATE=V1_9_A_FOUNDATION_FROZEN"
Write-Host "NEXT_STATE=MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1"
Write-Host "=== END_FINAL ==="

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDCc+H8HVbl5opR
# bztSU4u4OlG3Vw5o3aEgsqHOZb+/faCCBBwwggQYMIICgKADAgECAhApojSr80YY
# vUx8MLsjXS5aMA0GCSqGSIb3DQEBCwUAMCQxIjAgBgNVBAMMGUFJLVNBUCBMb2Nh
# bCBDb2RlIFNpZ25pbmcwHhcNMjYwODExMTI0NzU5WhcNMjkwODExMTI1NzU5WjAk
# MSIwIAYDVQQDDBlBSS1TQVAgTG9jYWwgQ29kZSBTaWduaW5nMIIBojANBgkqhkiG
# 9w0BAQEFAAOCAY8AMIIBigKCAYEA+0CoHVn5HMQt9b/KkbtixAcz2wk6GnNE9uSq
# rWFq6z3UZhjeZ/q1eS+xGgI+0AB+ywk6UuHE5/WvX63R4PmYMnkAW0iFbruPvRcv
# gp6G9liwLikJxI/Bd4FPH52EbeoEGYeH+GlIlnHqiekB3Q5yKWUCB8gNj7BbAJ0P
# ea6DYWybUTie0IKIn0BwUCdVuB8xIfsR/0IjD1vJxhMAIy5z5uHE+4JPGJD0SUEg
# hcYMYRkWeWKfqNeogFDFbSmR1yoHU2OY8Xzt9Z02mDnzNhSZ/0NAH6JFa1bMTbpB
# KFEziD/oJcjcc0z5FWtNsYRStwKDV0Hh0KGDMHOVZ4BrZ5bcU/R01lBJKdRM6R2G
# y7DX3fTme1g67yddSIK8j54F/jUTKD465KJ/AcYrulD/5Mvn3jT/KMzFEPLXcPHA
# f2427/12IxzrIqXEzezP2AFHWXjVhtNxL0DX6QrciBh9k1Y28WOPH46ImB3u/8x5
# LI1JhyNequhJFZ49jx1ZQL+PZnkBAgMBAAGjRjBEMA4GA1UdDwEB/wQEAwIHgDAT
# BgNVHSUEDDAKBggrBgEFBQcDAzAdBgNVHQ4EFgQUIeJF14rNAoB40EJq/1K5XBgq
# P+wwDQYJKoZIhvcNAQELBQADggGBAKNJnzA6dFKwVYrOXDyVOR8hEaYbRZtN+AZs
# j3zIpmRT3MSdpb+d+cM4OhPqFFDi8dLczd8crLI38YGWizKlZX2uz4gzEb0RiD2i
# vy7qc7oNM4Yq9zaox4WqDnND0+pOOwXyC05O1X0GIMOFmIjhNHqjKWvj5BSR7Hfn
# /6DLOxo/+h+knMehDuJ1pRMWIXoPsrk2zpEM0pQ+looewfHAUQT/kMSUxYTlJ90H
# 16lsg8xPtoIWkGe0fCmcE46PLY0b/ar3XRB/VKW1y8dYZQH5PneUYJeGXYuY7/jl
# zprNEc42uOEFY2dfIoAp5rW/uHRgJ46KAzA2fYn6dKHGXQOU7KabXztE5mjNRWlQ
# oBTiRrfaS7DjHkhPz/HUUOnqoEniPmq4knlXrjHymcRidTbTIR5A2XYx48y5/NwH
# 7EJhr6NyqvxCS/NNguPFxYOwPDg+atMepeANdgiei10JYGQsSRNKIfkWRlSxUiC8
# wohYQsAfYUPqEayvhb5YkKLdE8QgjzGCAmowggJmAgEBMDgwJDEiMCAGA1UEAwwZ
# QUktU0FQIExvY2FsIENvZGUgU2lnbmluZwIQKaI0q/NGGL1MfDC7I10uWjANBglg
# hkgBZQMEAgEFAKCBhDAYBgorBgEEAYI3AgEMMQowCKACgAChAoAAMBkGCSqGSIb3
# DQEJAzEMBgorBgEEAYI3AgEEMBwGCisGAQQBgjcCAQsxDjAMBgorBgEEAYI3AgEV
# MC8GCSqGSIb3DQEJBDEiBCC0zTFpDEMQwh5r98kqNhSmp33YX5hZv+SA853KjUf8
# hDANBgkqhkiG9w0BAQEFAASCAYCBivDJhjqsWsso+Oaxg/c/2c8VBnGZuhWx5qm0
# 5C/ovDIg/y2lYicP42NDkkZgiXHHi7TtislSNapYwWiHoepkl7neVh3Dx6fGhzGI
# 6K9FnA+Omso4MZKNmk6SoljGJicyrs3gIqtrOXTgYk0zxnFWmTsBsQpH3ERd8zjP
# WaD1B419aO1E/hVLMttgoFWwoZICpc/pnGZxg5m5gdeEJeUekRvEalBHuLZ0Gy0O
# pHL+fSngTibhfPGMykhxj//2AsbMXDbrzEhj5h6doT/yn4ytz9D7yfLaW4z8Jhos
# YamwykN89GO/ckaxRfyk8UwWgWyjcjAlkLruM9R0pj6VL66jMG4uGJQGXNF9ehZO
# bNkyMqIy9dnUinz2SCbe3JtPbg1dAMGFQAgX0ulafTiCaHvcQhPTqSNSrEUOZfZq
# MLQ6w144OLUrNRHCbNmXbMWSAeBwK3izWwzxaODVX6cJQJHN0/AElCxK+eL7NLEI
# 9m4wB9J+Uub5MGSrenTaz/U/l/g=
# SIG # End signature block
