# Pipelad — Defense sheet

Track 3, Open Track · AI × Cybersecurity, defensive side · 11 October 2026.
Every claim below points to its proof: a demo step, a file in this repository, a measurement or a
public source. What is not proven is said so (§ 6). The French version, with more detail, is
`docs/defense.md`.

## 1. The project in two sentences

Tech SMEs without a security team install hundreds of open-source packages on sensitive servers,
and a single poisoned update is enough to compromise them. Pipelad cuts those servers off the
internet and lets in only package versions that have waited three days, been analysed on site
(code, sandbox, local AI) and been signed — developers still just type `pip install`.

**Who we help:** the CTO of a 20–80 person tech company (healthtech, fintech) that sells to
regulated clients, with no CISO and no SOC.

## 2. How it works

| Machine | Where | Role |
|---|---|---|
| **Platform** | on the client's premises; the only machine with internet access | watches new versions, holds them 3 days, runs them in a sandbox full of fake secrets, checks name, code and metadata, has a local LLM explain, lets a deterministic policy decide, then signs (Ed25519) |
| **Gateway** | private network, no internet | accepts a version only if signed, untampered (sha256), recent and never seen (nonce), over mutual TLS; serves pip (pypiserver) and npm (Verdaccio) with no upstream fallback; hosts the API relay (closed list, no TLS decryption) |
| **Servers** | private network, no route and no DNS to the internet | install only from the gateway; call only allowed APIs through the relay |

Everything runs locally: LLM, RAG, sandbox, hash-chained log. Only package names and versions
leave for the internet.

## 3. What the demo proves

| Claim | Proof |
|---|---|
| The server has no internet, yet installs packages | `curl https://pypi.org` fails; `pip install` works from the gateway (`infra/aws/verifier_h3.sh`) |
| A healthy version passes after its delay | demo package 1.1: waits, analysed, approved, signed, published |
| A poisoned version is blocked, with evidence | 1.2: static finding (`exfiltration`), sandbox (fake AWS keys read, attacker DNS), LLM explanation citing CWE / ATT&CK |
| Doubt goes to a human | 1.3: one strong signal → "to review"; an admin decides with a written reason |
| A forged publication is refused | `demo/forger.sh` → `401 invalid signature` |
| Taking over the platform gives neither the servers nor internet | 8 checks on AWS, each with its counter-test (`infra/aws/verifier_compromission.sh`) |
| The log cannot be rewritten silently | "Verify the chain": one altered entry breaks the chain at its number |

762 automated tests pass. Each new test was seen failing before the code was written, or the code
was broken on purpose to check that a test catches it.

## 4. The numbers

Final measurement, 11 October 2026 (`mesure/resultats.md`): 128 real malicious versions (Datadog
dataset) and 98 healthy ones (PyPI, 48 of them little-known). A version is stopped if any control
raises a strong or blocking signal.

| Controls | Malicious stopped | False alarms |
|---|---|---|
| Name + code checks | 93 / 128 (73%) | 0 / 98 |
| + sandbox | **103 / 128 (80%)** | **0 / 98** |
| + LLM / RAG | 103 / 128 (80%) | 0 / 98 |

- **The sandbox pays:** +10 detections with no false alarm (attacker DNS, cloud metadata probing,
  `/etc/passwd` read).
- **The LLM adds no detection, by design.** The code decides; the AI alerts and explains in plain
  language for a CTO without a security team. It can never approve, block, or lower another signal,
  and its alert only counts when another control has found something.
- **The context:** 454,600 new malicious open-source packages in 2025, +75% (Sonatype); a third
  party is involved in 30% of breaches, twice the year before (Verizon DBIR 2025).

## 5. Likely questions

**"Artifactory, Nexus or Socket already do this."** They are built for large, tooled teams with a
SOC behind them, at their price. We are local (AI included), the isolation is demonstrated (no
route, not a proxy rule), and the verdict is explained to a non-analyst — for €300–800 a month.

**"Package managers now have a cooldown for free."** Yes, and that proves the delay works. But a
cooldown protects only the developer who enabled it. Pipelad enforces it for the whole company,
adds analysis, isolation and a signed log, and nobody can bypass it from a server.

**"What about an urgent security fix?"** An emergency fix can itself be poisoned: ultralytics
8.3.42, published in December 2024 to fix a compromised release, carried the same malware. The
analysis runs during the wait, and the server keeps its working version. Today the delay is set per
company; a logged per-version override is next (§ 6).

**"An AI reading code can be wrong or manipulated."** Hence the rule: the code decides. Package
content is passed to the LLM as data between tags, its output is schema-validated, and it can only
raise a signal, never open the door.

**"What if the platform is compromised?"** A spoofed platform publishes nothing: it needs both the
mutual-TLS certificate and the signing key. A platform really taken over could sign a poisoned
version, but cannot reach the servers or give them internet (8 checks on AWS). Next step: the
signing key moves to hardware (YubiKey / HSM) with a human gesture.

**"Which regulation?"** We do not sell compliance; we provide the evidence our clients' clients
ask for. NIS2 art. 21 (supply-chain security, reaching suppliers indirectly), DORA since January
2025 (banks' ICT providers), CRA (exploited vulnerabilities reported from September 2026,
components documented by December 2027).

## 6. Limits, stated before you find them

- No per-version emergency override yet: the delay applies to all versions.
- The end of the log is not anchored: deleting the last entries is not detected.
- A platform really taken over can sign; hardware key planned.
- No SBOM export yet (CycloneDX / SPDX).
- The sandbox installs without dependencies: payloads that fire on import of a package that cannot
  import alone are missed (ultralytics). The delay and the advisory watch cover that case.
- Measured on datasets, not in production. The LLM runs on CPU: 50–60 s per version, invisible
  behind a 3-day delay.
- Automatic installation on servers covers pip; for npm the command is run by hand.
- No one-command installer or appliance yet: priority number one.

## 7. What's next (6 months)

- **First customers:** medical-AI startups selling to hospitals, B2B fintechs selling to banks,
  then managed service providers as the channel (one contract, 20+ SMEs).
- **Roadmap:** one-command appliance and logged emergency override; three design-partner pilots;
  one-click evidence pack for security questionnaires and SBOM export; multi-client console for
  MSPs and a guard for AI coding agents that install packages on their own.
- **Business model:** €300–800 per month per company, flat, not per developer; on site or at a
  European host.
- **What we need:** pre-seed funding (Bpifrance), three design partners (ESSEC Alumni network),
  cloud credits for pilots (AWS), a go-to-market co-founder.

## 8. Sources

- Sonatype, State of the Software Supply Chain, 2026 report.
- Verizon, 2025 Data Breach Investigations Report.
- IBM, Cost of a Data Breach Report 2025.
- ReversingLabs, Wiz: ultralytics compromise, December 2024.
- CISA alert on Shai-Hulud, 23 September 2025.
- EU: NIS2 Directive (2022/2555) art. 21; DORA Regulation (2022/2554); Cyber Resilience Act
  (2024/2847).
- Full list with links: `docs/defense.md` § 9 and `docs/business.md` § 13.
