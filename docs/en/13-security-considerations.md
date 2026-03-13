# Security Considerations & Threat Model

> This document summarizes the current security capabilities, known risks, and recommended practices of Open-A2A.  
> It clarifies what the protocol layer does (and does not) cover, so that runtimes and applications can add their own safeguards.

---

## 1. Threat Model & Scope

- **What Open-A2A is responsible for**
  - Message structure and subject naming between Agents (Intent / Offer / OrderConfirm / Logistics*, etc.);
  - Transport abstraction and implementations (NATS / Relay / DHT);
  - Identity & integrity (DID signatures), preference storage abstraction (File / Solid Pod);
  - Infrastructure components such as Bridge and Relay.
- **What Open-A2A is not directly responsible for**
  - Business-level risk control and authorization (who may call which Tool, transfer how much value, etc.);
  - LLM / prompt-level security (prompt injection defenses, meta-instruction filtering, etc.);
  - Economic incentives and consensus (reputation systems, token economics, penalties).

**Design principle**: the protocol guarantees that “who says what to whom” is delivered reliably and (optionally) securely.  
Whether to trust and how to act on that message is the responsibility of each Agent runtime and application.

---

## 2. Existing Security-Related Capabilities (What We Can Already Defend Against)

- **Transport encryption & MITM protection (optional)**
  - Both NATS and Relay can be deployed with TLS (wss) to prevent passive eavesdropping and on-path tampering.
  - Relay supports server-side TLS certificates (see `11-relay-e2e-verify.md` and related configs).

- **Identity & integrity (who sent this, has it changed?)**
  - `AgentIdentity` in `identity.py` is based on `did:key` + JWS:
    - Outgoing Intents / Offers can be signed;
    - Subscribers can verify signatures and populate `sender_did`.

- **Data sovereignty (who controls preferences & constraints)**
  - `PreferencesProvider` + `FilePreferencesProvider` + `SolidPodPreferencesProvider`:
    - Users can store their preferences in a self-hosted Solid Pod;
    - Agents access them via OAuth2 client credentials instead of hardcoding private data.

- **Structured message formats**
  - Intent / Offer / OrderConfirm, etc. use structured JSON models:
    - Separate structural fields from natural language descriptions;
    - Enable field-level filtering and policy evaluation at the runtime layer.

These capabilities help prevent **eavesdropping / tampering / impersonation / plain-text leakage**,  
assuming infrastructure is deployed correctly. They **do not automatically prevent** prompt injection, business misuse, or spam.

---

## 3. Main Risk Categories (Given the Current State)

> This section mirrors the Chinese document and is intentionally high-level.  
> See that document for more detailed explanations and mitigation ideas.

### 3.1 Transport & Routing Risks

1. **Unsecured NATS (no auth / no TLS)**
   - Anyone who can reach the NATS server may subscribe to `intent.*` and publish arbitrary messages.

2. **Relay (WebSocket ↔ NATS) without auth / rate limiting**
   - Publicly exposed Relay endpoints can become a spam / DoS vector if left unauthenticated and unthrottled.

3. **DHT discovery (Kademlia) routing & privacy risks**
   - Public DHT bootstrap nodes can be used to poison capability records or scrape global capability metadata.

---

### 3.2 Identity & Authentication Risks

4. **Poor DID private key management**
   - Plaintext keys on disk, no rotation / revocation process.

5. **Lack of DID trust policies / whitelists**
   - Treating all DIDs as equally trusted makes impersonation easier.

6. **Bridge / OpenClaw integration without proper auth**
   - `POST /api/publish_intent` and NATS forwarding exposed without access control.

---

### 3.3 Data & Privacy Risks

7. **Metadata leakage**
   - Even with encrypted payloads, timing, subjects, and traffic volume can reveal sensitive patterns.

8. **Content-level privacy & compliance**
   - Broadcasting raw PII / detailed orders over unsecured topics may violate privacy regulations.

9. **Preference & Solid Pod configuration risks**
   - Misconfigured Solid Pods or leaked OAuth2 client credentials expose user preference data.

---

### 3.4 Availability & Abuse Risks

10. **Spam Intents & wasted compute**
    - Malicious Agents can flood the network with low-quality requests / offers.

11. **Denial-of-Service (DoS / DDoS)**
    - Excessive connections / subscriptions / large payloads can overload NATS / Relay / Bridge.

---

### 3.5 Protocol / Implementation Drift

12. **RFC vs implementation mismatches**
    - Diverging specs and code can create exploitable inconsistencies across nodes.

13. **Insufficient input validation**
    - Weak JSON / WebSocket message validation can lead to crashes or resource exhaustion.

---

### 3.6 Prompt Injection & Runtime Logic Risks

14. **Prompt injection via Agent-to-Agent collaboration**
    - Malicious Agents may send natural-language payloads that, if naively embedded into LLM prompts, hijack behavior.
    - This is **explicitly a runtime / LLM-layer problem**, not something the protocol can decide on its own.

---

## 4. Recommended Practices (High-Level)

- **Secure deployment of NATS / Relay / Bridge**
  - Enable TLS, require authentication, and use NATS `permissions` for subject-level access control;
  - Add basic rate limiting and connection limits, especially for public endpoints.

- **DID & key management**
  - Encrypt private keys at rest, restrict access, and define rotation / incident response procedures;
  - Maintain DID trust policies (whitelists / allowlists) in the Agent runtime.

- **Data minimization & privacy**
  - Only broadcast the minimum necessary information; prefer end-to-end encryption for sensitive content;
  - Use private discovery where appropriate instead of public DHT.

- **Runtime-level defenses (prompt injection, over-privileged tools)**
  - Treat all Open-A2A content as untrusted input in LLM prompts;
  - Wrap messages in strict templates and enforce tool-level permissions / quotas.

- **Towards reputation & abuse detection (future work)**
  - Collect metrics, design basic reputation / blacklisting mechanisms;
  - Iterate towards more advanced incentive and punishment schemes if the community needs them.

---

## 5. Future Work

- Add “Security Considerations” sections to each RFC;
- Provide dedicated “Secure Deployment Guides” for NATS / Relay / Bridge / Solid;
- Extend tests and CI to cover malformed / adversarial inputs and high-load scenarios;
- Refine this document based on real-world deployments and community feedback.

