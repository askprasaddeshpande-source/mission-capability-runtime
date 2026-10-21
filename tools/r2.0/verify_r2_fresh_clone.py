"""Verify the R2.0 lineage from a repository checkout; needs no owner workspace.

Usage:
  python tools/r2.0/verify_r2_fresh_clone.py            # verify the checkout this file lives in
  python tools/r2.0/verify_r2_fresh_clone.py --clone    # git clone the checkout into a temp dir first
  python tools/r2.0/verify_r2_fresh_clone.py --write-sums   # (maintainers) regenerate SHA256SUMS_R2_0.txt

Checks: file hashes match SHA256SUMS_R2_0.txt (CRLF-insensitive for text); validator and scenario results
regenerate byte-identically; schemas regenerate identically; no absolute workstation paths or secret-like
strings in published R2.0 artifacts; if tag v1.9.0 exists it still points at the recorded commit.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

R1_9_TAG, R1_9_COMMIT = "v1.9.0", "9c5105fe5b35dadf7b1384f54d4bea4c490d3ae0"
SUMS = "evidence/r2.0/SHA256SUMS_R2_0.txt"
# Pinned historical files (byte-identical, CRLF-insensitive). BASELINE = every R2.0 file at commit 6f992c6 except the five
# intentionally revised afterwards (model, validator, local-scenario runner, verifier, mutation harness, sums).
# G_ERA = result/report files added by commit 8a383b6 (R2.0G). New versions are added as new files, never by editing these.
PIN_BASELINE_6f992c6 = {
    "architecture/r2.0/MCR_R2_0_STATE_MACHINE_R1.md": "A3265BEEB4C5E8E997D81ED69FA1C9AA99342F7ADC12BA9674DAB440A007D0CC",
    "architecture/r2.0/MCR_R2_0_VALIDATED_OUTCOME_ARCHITECTURE_R1.md": "678136E975E4579776ED1E1434A714CEF91534C867168D7BFE9C27D8B9988100",
    "architecture/r2.0/schemas/AuthoritativeReadbackContract.schema.json": "D93B77A2180C2434A4F9B55EF6C10E4099A215539CE873AF5806BBE0F1CBD6EF",
    "architecture/r2.0/schemas/AuthoritativeReadbackReceipt.schema.json": "506EC0266B419921CE461F7776BA15BD4826B66ED9C25630C80C25788ED7BB49",
    "architecture/r2.0/schemas/CapabilityBinding.schema.json": "09F4B5E636A85977725BCAC565D3FBE2B89F6337D9AC19F00553B38B716E408D",
    "architecture/r2.0/schemas/CommitObservation.schema.json": "77E8BDC3B4B4F1440FD5FA1C778BF04CBC358ADDB01EBEEF57C688C507ACE612",
    "architecture/r2.0/schemas/CompensationGrant.schema.json": "567046B8F8AD6E1E1B2FF8F6A1B481EF5C6F1BD054583A3674536006201C0E95",
    "architecture/r2.0/schemas/CompensationReceipt.schema.json": "A2DC93CCEE89E48DCF03B26595331BB79A7F6582ED2D09F85746F0BCCB611065",
    "architecture/r2.0/schemas/CompletionReceipt.schema.json": "780EE759298853AD601F32CA6620270583142A887A244121C09378E7252F5659",
    "architecture/r2.0/schemas/ContinuationLease.schema.json": "19E11E1716F524486E721BA2902B064737599CA5E71870DDAF44D2EFD08939E0",
    "architecture/r2.0/schemas/ContractFingerprint.schema.json": "DF34180A180CFEE564027B8C3D38E20451F43E2F928FB977140C96E00A8A6044",
    "architecture/r2.0/schemas/ContractLease.schema.json": "8D91413C3C44BDA95617DF1F5A7AD711AE8BE2AF45F4C555FE025DB1BBEB47C8",
    "architecture/r2.0/schemas/DelegationEnvelope.schema.json": "187FDE4021F86A9E3528BED81DB02257DB6C482A59853F4D1AD300751AA66F98",
    "architecture/r2.0/schemas/EvidenceEnvelope.schema.json": "59F1AD1BF18A01138A3EACB1BF13F0D35536D52363E0BAB0F75F1E7166A806BA",
    "architecture/r2.0/schemas/ExecutionAuthority.schema.json": "DC879E78E1AFB3AC47FB3C64B072AA9622170BA335676EECB5429BEBA7988B4C",
    "architecture/r2.0/schemas/ExecutionReceipt.schema.json": "28B3307F13EB01D81046B53E852859CFA82EB855F5685E8FBFF4CC2825F4B8EE",
    "architecture/r2.0/schemas/ExpectedOutcomeContract.schema.json": "D2FA31393FB188D718D0CC655EF6BFAD3EB5E4D7D5237E34264026B8B4A372C1",
    "architecture/r2.0/schemas/GovernanceTelemetry.schema.json": "0911A7675DE32E5738C1774CF9F54136071F380151793DBAC6862C6CDC601D00",
    "architecture/r2.0/schemas/MissionIntent.schema.json": "6B5A8EBE0D342516883CAA3389FAC7A5F83A24BE754FC2BCA8BC37E54E7F2ACD",
    "architecture/r2.0/schemas/MutationBudget.schema.json": "0CD49FAA6F3A128C8B3A2692FB5EDBBAEFD5D6348FAE155CA78A80FEE26D7A36",
    "architecture/r2.0/schemas/OutcomePredicate.schema.json": "081AC2B354CB4FF8FEA4379A369449CF04D687082CDC0A1BE87C7C26DA135CC9",
    "architecture/r2.0/schemas/OutcomeReceipt.schema.json": "37E0010CD61A428579A8344CAECBC3DF1E5AC795E2A1AF35E980C61ED7BE8194",
    "architecture/r2.0/schemas/PreMutationCheckpoint.schema.json": "F427D5FE39D313266C16594E4B4C3CDB736DBB0228B3EA8E8FB7550131A0B99E",
    "architecture/r2.0/schemas/PrincipalContext.schema.json": "8A9193439A529D5C6F1F1FD22CA12268AC5E42E0F9CB8DE0F682DF00B1B3CB1B",
    "architecture/r2.0/schemas/ProviderBinding.schema.json": "0D059C29967B6D8B67CB1D29030266C81D11358B25DF5F68B1D233F310D44E2D",
    "architecture/r2.0/schemas/ReplayGuard.schema.json": "05096B526E6DB03670589BD592A7FE107DAB2F6DCA34D0307D8D5CDD9BD17D24",
    "architecture/r2.0/schemas/TransactionEnvelope.schema.json": "69025B3FBA056676C35C40F35F71DCC79401102D9D98A4F14A915BD8C11E1C85",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json": "8456E2D3B9148CC949086E3BB30E46F41DA78BE0D526890E04F6FB990A1EC126",
    "evidence/r2.0/MCR_R2_0_B_DDLS_CONTROL_SUMMARY_R1.json": "1BE52855011E6A49D28BF5D4C2842D74FB44A2DDA2E42AE4F53D25286D314C17",
    "evidence/r2.0/MCR_R2_0_B_LIVE_READONLY_PROBE_SUMMARY_R1.json": "1EE963DC90B8DE986CC83329851AB0E9A4782088AB46AF66B7A3EA6C8E2D9D40",
    "evidence/r2.0/MCR_R2_0_CLAIM_EVIDENCE_REGISTER_R1.md": "CB8B1B4C7A5617D2B5DE92306D141673D071F45167CB8B22E44F311DA49E28E4",
    "evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json": "FA2B7518F7815C08EAD1658C912524CDC3EAAD0F0F82DF90B0B32A2806160A02",
    "evidence/r2.0/MCR_R2_0_C_MOCK_SCENARIOS_R1.json": "4213C0CDAD3A58B10A2DE752010B82EFE51DD52E096E5202C61BFB72C84C58A7",
    "evidence/r2.0/MCR_R2_0_C_PREWRITE_LIVE_READONLY_R1.json": "7E0750A1BD50196FC17C5E023F7AAE7A24F202B31DDB278DE45E38FCB25FCD66",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json": "4BF0B24C9032F6254258ECAC9088F1B78BE431EAE2829850FED9F3632E7ABD5E",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_REGISTER_R1.md": "B158D351CB7D35A856E6F825B11453898C1147489FF7BE207972DF57485E9026",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R2.md": "120499A8E39C34E7079838BCEDF279F1AAB57F52007D6B0B1C92F4175F2BA347",
    "reports/r2.0/MCR_R2_0_A_FOUNDATION_QUALIFICATION_R1.md": "3C1DA58466EDF1367656FDEF36897B7719DA34D0DFA3B1768AB34B4A3506F52E",
    "reports/r2.0/MCR_R2_0_B_READBACK_QUALIFICATION_R1.md": "213ECC7809494A366521D2A3F0DCAE49D1EB6A5892D6A80B7F277F284FEBF39F",
    "reports/r2.0/MCR_R2_0_B_READBACK_QUALIFICATION_R2.md": "E613BF3878415A4DF4AFC617A3A84249E058E7E88BAE75A5CC8CF6F9FBC49CBF",
    "reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md": "B1635033CFAE49D01728B6DC19C33F5B083387E16A20AAA45C187A5B23FB1B9A",
    "reports/r2.0/MCR_R2_0_R1_9_BASELINE_BOUNDARY_R1.md": "2DF2CEA5938B3A591F7E94A6015A5B149EF19BAA261E799348F3967AE09E168B",
    "reports/r2.0/MCR_R2_0_RESEARCH_CHARTER_R1.md": "5FF548050DD7585DE4CA9C6ED27CB209075D2AA89D98B573FE0214D648C3F828",
    "research-package/r2.0/MCR_R2_0_EVIDENCE_PLAN_R1.md": "01BC64EBF61C2BF7D86B228BF6BE8140D47353EF29A1CB11D4D7204270AFE064",
    "research-package/r2.0/r2_0c/MCR_R2_0_C_AUTHORIZATION_PACKET_R1.md": "751C6BD6507C4127CAFB35334F350A2CEF1518309935D0B31B27E75EA29D34D8",
    "research-package/r2.0/r2_0c/R2_0C_FREEZE_R1.json": "43A775C21EC2AE1D640DE5A2955762D57E4877BCE828BA828EDBBBA01C67E833",
    "tools/r2.0/r2_0b_readonly_readback_probe.py": "FA381423912A0F7303E5001C9F908A07D61A4D7C486C93DA7B51301542A1EDCD",
    "tools/r2.0/r2_0c_study.py": "A73F4647E0AC9B672284A4A4D4A87AE031CBC6AFB7707362C9050ED632C3DDC9"
}
PIN_G_ERA_8a383b6 = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R1.md": "918C8DF9AA13019039C2CC0DDB8C60CE3ED7CF9399DB0EF899DA09DF3592B8D6",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R2.json": "CA34BBB93B99C56C569A4AC5FC026E7BF70B8513DA66C14E83949A901EC4819A",
    "evidence/r2.0/MCR_R2_0_G_MUTATION_CHECK_R1.json": "3CE06C06665A207EAB3089EE2615B65EAD3188C6BE14AC25BB6A03D8334F44EA",
    "evidence/r2.0/MCR_R2_0_G_TEST_MATRIX_R1.json": "7797ACDE85EC5CC53549F25A702029421C8CC555C4EBCE7B68567790A335EC7D",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R3.md": "295968B42DB484251D66D2D4C9CA7D28CED878669908461DED69DBD5849E4F2E",
    "reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md": "3ACACE47AF8BCBA35A5D2187A87842A69FC4144C55EC355A8E6341362910EF6F",
    "reports/r2.0/MCR_R2_0_G_QUALIFICATION_SUMMARY_R1.md": "6DFC43221A44282A56B889A99D1D0E15BB866B0934F21A338BFAA8F6340914F9"
}
PIN_H_ERA_b5cca1f = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R2.md": "4287D6734441F00E7F0489EAB3846F3C1B8160B52033B7B6C4D17E3A4170925C",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R3.json": "C6A0AF14325745986716929AE3B185A60EDE9761FEDA4ABB62A342D8177FE3AA",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R2.json": "212BC2FD28EDD0ACFDD48258A69FFD0FDC5ABB99F2491D2328867CF406C167F1",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R4.md": "05FAAA09D54D32B0670BFB0ED7DC735E9CFFD2C0ABEB9B27012B1AE11034F8C2",
    "evidence/r2.0/MCR_R2_0_H_MUTATION_CHECK_R2.json": "7B8F895634F55402DAD4D6E881AAFB213B6687BE4426D70D22EB4DC025A910F3",
    "evidence/r2.0/MCR_R2_0_H_TEST_MATRIX_R1.json": "4503D4B949FEE4A45F529BCDDA2D8B568328969573625095A25209683EE8E8A8",
    "reports/r2.0/MCR_R2_0_H_HARDENING_REPORT_R1.md": "DA60EEFD41D4DB08432CF561AC619C06FE96E89995AB79039DD0ADC41C31035B",
    "reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R1_FINDINGS.md": "EF8916A81D663DCDCDF67B159FF4BFDAF1648A924433FAF11DA6A6299BB14F21",
    "research-package/r2.0/r2_0c/MCR_R2_0_C_AUTHORIZATION_CONSUMED_R1.md": "524244079B7CB2513772F39D6EF7B246A7EB9743A9C8FDA7256B1E4E42ED2716"
}
# SHA-256 (CRLF-insensitive) of the model-side files at the revision submitted for independent review. Changing any of
# them requires editing this table in the same commit, which makes the change visible; it is not an external anchor.
PIN_REVIEWED_REVISION = {
    "tools/r2.0/mcr_r2_model.py": "E70F2ACC79BB668232CE3F844770A063F73E1BB8C2742EEB9AD1482B81DDD8CF",
    "tools/r2.0/run_r2_local_scenarios.py": "B19B549776C17D7919F494B3C4C6A362542E3ED4628020B501FD0A56258AB955",
    "tools/r2.0/run_r2_mutation_check.py": "69F7CC5F4F7DBBA3B101F2552743CB5FE435041AB8CD9EA1D5BC089AE8F5BFF6",
    "tools/r2.0/validate_r2_outcome_model.py": "8ACAE628959BD1352250E8A4C5636DC9D85FBB90E3B68204CC59DD3191430686"
}
PIN_I_ERA_a381a22 = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R3.md": "EF291CB6529A0DE1F71C6477D3B05889D466A6D20336DF9D4C9F4552CDF03872",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R4.json": "B534F5C22FF4E6F275BFA19B4613E3A9B37B4F699A44AA75DDF95BA6AF85197D",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R3.json": "DEC7879247D0EA7A6DAD4A9F463AB81C50F41BAB8F9D95ED2AC6BAF7B4F7CB4A",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R5.md": "A6A6C662155D68914E6F73ED35D6A504DEF99B19A6B410B37654B07839C0D302",
    "evidence/r2.0/MCR_R2_0_I_MUTATION_CHECK_R3.json": "E7158AC4BB130EAE238A6EDF2AEF90F23119972BD1ECB302818613C4762BB1FF",
    "evidence/r2.0/MCR_R2_0_I_TEST_MATRIX_R1.json": "2C60B43C60C4ECDB9DB17EA40B61C8DAD9C446C00CA62FCF433F5B41FB1F40D5",
    "evidence/r2.0/MCR_R2_0_I_VERIFIER_ATTACKS_R1.json": "D968FEEB8266D592B750858951763A0CA9EA593E84E05867CCA8B817679AC917",
    "reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R2_FINDINGS.md": "586BFED4DF9AD6FB6089D792EE3954E4E9162D6CE01673B7FC2CC9CFECE1FB55",
    "reports/r2.0/MCR_R2_0_I_HARDENING_REPORT_R1.md": "0653F822F8197B7567CE746B2C905A1ADF9051D208F2FD91854B47A69653586A"
}
PIN_J_ERA_f6e79a4 = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R4.md": "05F813C6582CB8BD4C057B22BE56D01093DD44E1FA8072BEF2DE657D9563ED6B",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R5.json": "83A107AAC5176892B1C3341898A42A26192FAD5208FF23E7B2400E9F25A24469",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R4.json": "DEC7879247D0EA7A6DAD4A9F463AB81C50F41BAB8F9D95ED2AC6BAF7B4F7CB4A",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R6.md": "13A32B161B28F85D13595A715E6A1A15064216F662918FD3BF659205496DA837",
    "evidence/r2.0/MCR_R2_0_J_MUTATION_CHECK_R4.json": "29DEA853669800E9ACD26A4DA5169A982B2528CF5A28716D24ADF4C27B7D6083",
    "evidence/r2.0/MCR_R2_0_J_TEST_MATRIX_R1.json": "A40826FCAC8D18706CBF751A7134907A99C37CEF3575214DD8C1E42D6116A998",
    "evidence/r2.0/MCR_R2_0_J_VERIFIER_ATTACKS_R2.json": "D8B6123290F43A3837B7C28ACFCE7F5BBF0C335AFE3425DC5B47AB5E2C18D34E",
    "reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R3_FINDINGS.md": "4305FA29474C87BBA939E99B18A43E755777C666A50579A657003A4694E45E1A",
    "reports/r2.0/MCR_R2_0_J_HARDENING_REPORT_R1.md": "2209D6B89ECAF472219D53C71E64BEBB31CFF904390E407A6D87F4DC0ED3BDCE"
}
PIN_L_ERA_681f77a = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R5.md": "BAB6E4D8579473F77520C937FF9E38875EC227FE1C8C66C9E2795CD1B4C9A604",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R6.json": "B906609B0BFC4FBFE7490DB08D72B5BD78A06C1EAACD09A886BAA7BC45F33A5F",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R5.json": "DEC7879247D0EA7A6DAD4A9F463AB81C50F41BAB8F9D95ED2AC6BAF7B4F7CB4A",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R7.md": "C3F26550FC0D14767555DB1C05001BD72EAB56B0190633928724C6497C4DFE69",
    "evidence/r2.0/MCR_R2_0_L_MUTATION_CHECK_R5.json": "5B701D8C4E2AA80735FBB294CCB0CF35320BE9C7ECAE9B523F4317A9234BF39B",
    "evidence/r2.0/MCR_R2_0_L_TEST_MATRIX_R1.json": "F4844662F8AD02F503B67A03D26C18CE70085CAEB2CB5A007FF199EE882ACB6A",
    "reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R4_FINDINGS.md": "1E6F594CE0F4680E8C20DF2B140F86EF80B204B9DCFEE68B56DF8DDF723D9961",
    "reports/r2.0/MCR_R2_0_L_HARDENING_REPORT_R1.md": "F7F25FDD1394C0C5A63296E1364BE5995CF45BF061B7A1287450EB9E5DF65475"
}
PIN_M_ERA_212804f = {
    "architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R6.md": "527641D8A7619B67852DCEF4D0B69FEC602579C54057847B1E6AE1F5F1C6161E",
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R7.json": "DF2BA0A4A877A2A2059546225273A954A57116687F960AEA93C8CAAA6BCADBEA",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R6.json": "DEC7879247D0EA7A6DAD4A9F463AB81C50F41BAB8F9D95ED2AC6BAF7B4F7CB4A",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R8.md": "E9AE84BC2B91713F6597570178D3DE38B93351502C16B12397E15E9A23881FB7",
    "evidence/r2.0/MCR_R2_0_M_MUTATION_CHECK_R6.json": "B937FD7F7490DE6E3A267522D59EA37C377DDADA0075E89522E85B13CDAB2D1A",
    "evidence/r2.0/MCR_R2_0_M_TEST_MATRIX_R1.json": "02C1E160406D2B1239BA08AB84540B7A8FDC189F258BD943E2B6337C0FCC6B85",
    "reports/r2.0/MCR_R2_0_M_HARDENING_REPORT_R1.md": "B39457E61A1FC2350111AA63FA6D6E5739257DEF1F3A75B561A9CFA8C9EC16B6"
}
FROZEN_HISTORICAL = dict(PIN_BASELINE_6f992c6, **PIN_G_ERA_8a383b6, **PIN_H_ERA_b5cca1f, **PIN_I_ERA_a381a22, **PIN_J_ERA_f6e79a4, **PIN_L_ERA_681f77a, **PIN_M_ERA_212804f)
ROOTS = ["tools/r2.0", "architecture/r2.0", "evidence/r2.0", "reports/r2.0", "research-package/r2.0"]
SKIP = {SUMS, "__pycache__", "tools/r2.0/make_adt_auth_context.py"}   # local credential helper, git-ignored
TEXT = (".py", ".md", ".json", ".txt")
# Frozen live tooling with owner-workspace default paths (not publication logic); any other tool must be path-free.
TOOLS_WITH_DEFAULT_PATHS = {"tools/r2.0/r2_0c_study.py", "tools/r2.0/r2_0b_readonly_readback_probe.py"}
LOCAL_EXEC_DOCS = {"research-package/r2.0/r2_0c/MCR_R2_0_C_AUTHORIZATION_PACKET_R1.md"}   # owner-workspace commands by design
ABS = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/](?!/)|/Us" + "ers/|/ho" + "me/[a-z]|%(?i:USERPRO" + "FILE|APPD" + "ATA|LOCALAPPD" + "ATA)%|(?<![A-Za-z0-9:])\\\\\\\\[A-Za-z0-9._-]+\\\\[A-Za-z0-9$._-]+")  # drive paths (either slash), user-profile paths, env-var profile paths, UNC shares
SECRET = re.compile(
    r"Bearer\s+[A-Za-z0-9+/=_.-]{16,}"
    r"|Basic\s+[A-Za-z0-9+/=]{16,}"
    r"|protected_token_b64[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9+/=]{20,}"
    r"|BEGIN (RSA |EC |OPENSSH |DSA |ENCRYPTED |PGP )?PRIVATE " "KEY"
    r"|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{5,}"
    r"|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}"
    r"|(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}"
    r"|(?<![A-Za-z0-9])AK" "IA[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"
    r"|(?<![A-Za-z0-9])npm_[A-Za-z0-9]{36}"
    r"|(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}"
    r"|(?<![A-Za-z0-9])[sr]k_live_[A-Za-z0-9]{16,}"
    r"|AccountKey=[A-Za-z0-9+/=]{40,}"
    r"|://[^/\s:@]+:[^/\s@]{3,}@"
    r"|(?P<name>[A-Za-z0-9_.-]*(?i:secret|token|password|passwd|api[_-]?key|authorization)[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?(?P<val>[A-Za-z0-9+/=_.-]{16,}+)(?!\()"
    r"|(?P<sname>[A-Za-z0-9_.-]*(?i:password|passwd|secret|api[_-]?key|private[_-]?key)[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?(?P<sval>[^\s\"']{8,15})(?![^\s\"'])")

HASH_WORDS = {"hash", "sha", "sha1", "sha224", "sha256", "sha384", "sha512", "digest", "checksum", "fingerprint"}
COUNT_WORDS = {"count", "len", "length", "id", "ids", "size"}
LABEL = re.compile(r"(?:[A-Z]+[0-9]?|[0-9]+)(?:_(?:[A-Z]+[0-9]?|[0-9]+))+")       # UPPER_SNAKE enumeration labels
FILENAME = re.compile(r"(?i)\.(md|json|py|txt|ps1|zip|yaml|yml)$")                 # a key that is itself a file name (pin tables)
PLACEHOLDER = re.compile(r"(?i)^(changeme|redacted|example|placeholder|password|secret|required|optional|none|null|true|false|x{4,}|\*{3,}|<.*>|\$\{.*|\$\(.*|%.*%|\{\{.*)$")


def name_is_exempt(nm):
    """Names that denote a public digest or a count/identifier: whole name SEGMENTS only (so account_password and
    client_secret_silent are NOT exempt, while token_sha256, ExpectedTokenHash and token_id are)."""
    seg = [x.lower() for x in re.split(r"[_.\-]+|(?<=[a-z0-9])(?=[A-Z])", nm) if x]
    return bool(seg) and (any(x in HASH_WORDS for x in seg) or seg[-1] in COUNT_WORDS)


def short_secret_like(val):
    """An 8-15 character value under a strongly secret-like name: needs a digit with a letter, or a symbol."""
    if PLACEHOLDER.match(val) or LABEL.fullmatch(val):
        return False
    has_digit, has_alpha = any(c.isdigit() for c in val), any(c.isalpha() for c in val)
    has_symbol = any(c in "!@#$%^&*+=?~" for c in val)
    return (has_digit and has_alpha) or has_symbol


def has_secret(txt):
    """True if any secret-shaped value appears. Exempt: names that denote hashes/digests/counts/ids (whole segments),
    names that are file names, upper-snake enumeration labels, code calls, and placeholders. A hex or base64 value
    under a secret-like name is NOT exempt."""
    for m in SECRET.finditer(txt):
        g = m.groupdict()
        if g.get("name") is not None:
            if name_is_exempt(g["name"]) or FILENAME.search(g["name"]) or LABEL.fullmatch(g.get("val") or ""):
                continue
            return True
        if g.get("sname") is not None:
            if name_is_exempt(g["sname"]) or FILENAME.search(g["sname"]) or not short_secret_like(g["sval"]):
                continue
            return True
        return True
    return False


def files(root):
    out = []
    for r in ROOTS:
        for d, dn, fn in os.walk(os.path.join(root, r)):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                p = os.path.relpath(os.path.join(d, f), root).replace("\\", "/")
                if p not in SKIP and not f.endswith(".pyc"):
                    out.append(p)
    return sorted(out)


def sha(path):
    b = open(path, "rb").read()
    if path.endswith(TEXT):
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest().upper()


def text_variants(b):
    """Every plausible text reading of the bytes, so an odd encoding cannot hide a secret. Wide encodings are tried at
    every byte offset (a leading junk byte misaligns UTF-16/32) and decoded tolerantly (an odd length must not make a
    variant disappear)."""
    out = [b.decode("utf-8-sig", errors="replace")]
    for enc, width in (("utf-16-le", 2), ("utf-16-be", 2), ("utf-32-le", 4), ("utf-32-be", 4)):
        for offset in range(width):
            out.append(b[offset:].decode(enc, errors="ignore"))
    out.append(b.decode("latin-1"))
    return out


def read_text(path):
    return text_variants(open(path, "rb").read())[0]


BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".pyc", ".pyo")
MAX_SCAN = 8 * 1024 * 1024


def scan_bytes_for_secrets(b):
    return any(has_secret(t) for t in text_variants(b))


def scan_tracked_tree(root):
    """Secret scan of EVERY tracked file (not only the R2.0 folders), including text members of zip archives."""
    import zipfile
    tr = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    names = [x for x in tr.stdout.split("\n") if x] if tr.returncode == 0 else []
    hits = []
    for rel in names:
        path = os.path.join(root, rel)
        if not os.path.isfile(path) or rel.lower().endswith(BINARY_EXT) or os.path.getsize(path) > MAX_SCAN:
            continue
        if rel.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(path) as zf:
                    for info in zf.infolist():
                        if info.file_size <= MAX_SCAN and not info.filename.lower().endswith(BINARY_EXT + (".zip",)):
                            if scan_bytes_for_secrets(zf.read(info)):
                                hits.append(rel + "!" + info.filename)
            except zipfile.BadZipFile:
                pass
            continue
        if scan_bytes_for_secrets(open(path, "rb").read()):
            hits.append(rel)
    return hits


def run(root, *args):
    return subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True)


def main(argv):
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    tmp = None
    if "--clone" in argv:
        tmp = tempfile.mkdtemp(prefix="r2verify_")
        subprocess.run(["git", "clone", "-q", root, tmp], check=True)
        root = tmp
    if "--write-sums" in argv:
        with open(os.path.join(root, SUMS), "w", newline="\n") as fh:
            for p in files(root):
                fh.write("%s  %s\n" % (sha(os.path.join(root, p)), p))
        print("wrote", SUMS)
        return 0
    res = {}
    listed = {}
    for line in open(os.path.join(root, SUMS), encoding="utf-8"):
        h, p = line.rstrip("\n").split("  ", 1)
        listed[p] = h
    cur = files(root)
    res["sums_cover_all_files"] = sorted(listed) == cur
    res["hashes_match"] = all(os.path.exists(os.path.join(root, p)) and sha(os.path.join(root, p)) == h for p, h in listed.items())
    t = tempfile.mkdtemp(prefix="r2out_")
    a = run(root, "tools/r2.0/validate_r2_outcome_model.py", "--out", os.path.join(t, "a.json"), "--emit-schemas", os.path.join(t, "schemas"))
    res["validator_passes"] = a.returncode == 0
    res["validator_result_reproduces"] = open(os.path.join(t, "a.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R8.json"), "rb").read().replace(b"\r\n", b"\n")
    sch = sorted(os.listdir(os.path.join(t, "schemas")))
    res["schemas_reproduce"] = sch == sorted(os.listdir(os.path.join(root, "architecture/r2.0/schemas"))) and all(
        open(os.path.join(t, "schemas", s), "rb").read() == open(os.path.join(root, "architecture/r2.0/schemas", s), "rb").read().replace(b"\r\n", b"\n") for s in sch)
    d = run(root, "tools/r2.0/run_r2_local_scenarios.py", "--out", os.path.join(t, "d.json"))
    res["scenarios_pass"] = d.returncode == 0
    res["scenarios_result_reproduces"] = open(os.path.join(t, "d.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R7.json"), "rb").read().replace(b"\r\n", b"\n")
    res["reviewed_revision_pins_match"] = all(os.path.exists(os.path.join(root, p_)) and sha(os.path.join(root, p_)) == h_ for p_, h_ in PIN_REVIEWED_REVISION.items())
    sums_sha = sha(os.path.join(root, SUMS))
    if "--expect-sums-sha256" in argv:
        exp = argv[argv.index("--expect-sums-sha256") + 1] if argv.index("--expect-sums-sha256") + 1 < len(argv) else ""
        res["sums_anchor_matches"] = bool(re.fullmatch(r"[0-9A-Fa-f]{64}", exp)) and sums_sha == exp.upper()
    else:
        res["sums_anchor_matches"] = "NOT_CHECKED (pass --expect-sums-sha256 from a source outside the repository)"
    tracked = subprocess.run(["git", "ls-files", "--", *ROOTS], cwd=root, capture_output=True, text=True)
    if tracked.returncode == 0 and tracked.stdout.strip():
        tr = set(tracked.stdout.split("\n")) - {""}
        res["no_tracked_bytecode"] = not any("__pycache__" in x or x.endswith((".pyc", ".pyo")) for x in tr)
        res["tracked_files_match_sums"] = (tr - {SUMS}) == set(listed)
    elif "--no-git" in argv:
        res["no_tracked_bytecode"] = res["tracked_files_match_sums"] = True
    else:
        res["no_tracked_bytecode"] = res["tracked_files_match_sums"] = False
    res["frozen_historical_unchanged"] = all(os.path.exists(os.path.join(root, p)) and sha(os.path.join(root, p)) == h for p, h in FROZEN_HISTORICAL.items())
    if "--quick" in argv:
        res["mutation_check_passes"] = res["mutation_result_reproduces"] = "SKIPPED (--quick; run without it for release verification)"
    else:
        m = run(root, "tools/r2.0/run_r2_mutation_check.py", "--jobs", "4", "--out", os.path.join(t, "m.json"))
        res["mutation_check_passes"] = m.returncode == 0
        got = json.load(open(os.path.join(t, "m.json"), encoding="utf-8"))
        ref = json.load(open(os.path.join(root, "evidence/r2.0/MCR_R2_0_N_MUTATION_CHECK_R7.json"), encoding="utf-8"))
        stable = lambda d: (d["mutants"], d["by_kind"], d["not_applied"], d["survivors"], d["unexplained_survivors"], d["MUTATION_CHECK"],
                            [(r["mutant"], r["applied"], r["detected"]) for r in d["results"]])
        res["mutation_result_reproduces"] = stable(got) == stable(ref)
    bad_abs, bad_sec = [], []
    for p in cur:
        if True:
            raw_bytes = open(os.path.join(root, p), "rb").read()
            txt = text_variants(raw_bytes)[0]
            if p.startswith("tools/"):
                if p not in TOOLS_WITH_DEFAULT_PATHS and ABS.search(txt):
                    bad_abs.append(p)
            elif p not in LOCAL_EXEC_DOCS and ABS.search(txt):
                bad_abs.append(p)
            if scan_bytes_for_secrets(raw_bytes):
                bad_sec.append(p)
    helper = os.path.join(root, "tools", "r2.0", "make_adt_auth_context.py")
    if os.path.exists(helper):
        htxt = read_text(helper)
        if scan_bytes_for_secrets(open(helper, "rb").read()):
            bad_sec.append("tools/r2.0/make_adt_auth_context.py")
        if ABS.search(htxt):
            bad_abs.append("tools/r2.0/make_adt_auth_context.py")
    tree_hits = scan_tracked_tree(root) if "--no-git" not in argv else []
    bad_sec.extend(h_ for h_ in tree_hits if h_ not in bad_sec)
    res["no_absolute_paths_in_docs"] = not bad_abs
    res["no_secret_like_strings"] = not bad_sec
    g = subprocess.run(["git", "rev-parse", "-q", "--verify", R1_9_TAG + "^{commit}"], cwd=root, capture_output=True, text=True)
    res["r1_9_tag"] = ("UNCHANGED" if g.stdout.strip() == R1_9_COMMIT else "CHANGED") if g.returncode == 0 else "NOT_PRESENT_IN_CHECKOUT"
    ok = all(v is True or ("--quick" in argv and isinstance(v, str) and v.startswith("SKIPPED")) for k, v in res.items() if k not in ("r1_9_tag", "sums_anchor_matches")) and res["sums_anchor_matches"] is not False and res["r1_9_tag"] != "CHANGED"         and (res["r1_9_tag"] == "UNCHANGED" or "--no-git" in argv)
    print(json.dumps(dict(res, sums_sha256=sums_sha, details={"absolute_path_files": bad_abs, "secret_like_files": bad_sec}, R2_FRESH_CLONE_VERIFY="PASS" if ok else "FAIL"), indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
