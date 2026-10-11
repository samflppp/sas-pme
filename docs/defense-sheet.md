# Pipelad — Defense sheet

Track 3 · AI × Cybersecurity, defensive · Pipelad: an airlock between the internet and an SME's servers.

## Threat scenario addressed

A tech SME (20–80 people, no CISO, no SOC) installs open-source packages from PyPI and npm on
servers holding sensitive data. An attacker takes over a maintainer account or a publishing
pipeline and releases a poisoned version (typosquat, emergency "fix", worm). The version steals
credentials or cloud keys at install or import time, then exfiltrates them or downloads a second
stage. Real cases: ultralytics (Dec 2024, the emergency fix was poisoned too), Shai-Hulud (Sep
2025, 500+ npm packages stealing cloud keys), TanStack (May 2026, 84 validly signed versions).

**Defense:** servers have no route and no DNS to the internet. They install only from a gateway
that accepts versions signed by our platform, which first holds each new version 3 days, runs it in
a sandbox seeded with fake secrets, checks name, code and metadata, and has a local LLM explain. A
deterministic policy decides; the AI never approves.

## NIST CSF 2.0 functions covered

| Function | How |
|---|---|
| **Identify** | inventory of every version served and downloaded, per server |
| **Protect** | network isolation of servers; signed publication (Ed25519) over mutual TLS; API relay with a closed allow-list |
| **Detect** | advisory watch (OSV, researcher feeds); static analysis; behavioural sandbox; LLM explanation |
| **Respond** | automatic block; human review for doubtful versions; one-click revocation from the gateway |
| **Govern** | tamper-evident, hash-chained decision log (who, what, why) for audits and questionnaires |

## ATT&CK, ATLAS and OWASP coverage

- **ATT&CK:** T1195.001 Compromise Software Dependencies (core); T1552.001 Credentials In Files and
  T1552.005 Cloud Instance Metadata API (decoys, sandbox); T1071.004 DNS and T1041 Exfiltration
  Over C2 Channel (no route out, sandbox DNS capture); T1105 Ingress Tool Transfer (no internet);
  T1027 Obfuscated Files (static check); T1496 Resource Hijacking (ultralytics miner, held by delay).
- **ATLAS:** AML.T0010 AI Supply Chain Compromise (ML libraries such as ultralytics); AML.T0051 LLM
  Prompt Injection against our own analyst (package content passed as data, schema-validated output,
  LLM cannot approve).
- **OWASP:** Top 10:2025 A03 Software Supply Chain Failures, A08 Software or Data Integrity
  Failures; LLM Top 10:2025 LLM01 Prompt Injection, LLM03 Supply Chain.

## Metrics achieved

| Metric | Result | Source |
|---|---|---|
| Detection rate | **80%** (103 / 128 real malicious versions, Datadog dataset) | `mesure/resultats.md` |
| False positives | **0 / 98** healthy PyPI versions (48 little-known) | `mesure/resultats.md` |
| Time to detect | **72 s** from end of delay to blocked verdict (AWS, CPU-only 7B LLM); delay itself 3 days by design | `demo/script.md`, rehearsal |
| Time to respond | **0** for servers: a blocked version is never signed, so never served; revocation of a published one in one click, inventory lists who downloaded it | demo steps 3–4 |
| Isolation | **8 / 8** checks pass on AWS with the platform taken over | `infra/aws/verifier_compromission.sh` |

Static checks alone reach 73%; the sandbox adds 10 detections with no false alarm; the LLM adds
none, by design — it explains. 762 automated tests pass.

## Known limitations

- The sandbox installs without dependencies: payloads firing on import are missed (ultralytics); the
  delay and advisory watch cover that case.
- A dormant, well-hidden backdoor (xz style) can pass all three layers.
- A platform really taken over can sign a poisoned version; hardware signing key planned.
- The end of the log is not anchored: deleting the last entries goes undetected.
- No per-version emergency override and no SBOM export yet.
- Measured on datasets, not in production; LLM on CPU takes 50–60 s per version.
