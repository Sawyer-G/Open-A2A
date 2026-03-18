# Identity & Trust (operator guide): DID + signatures + optional VC

> This is a practical “how to use it” guide. Protocol details live in `spec/rfc-004-identity-and-trust.md`.

---

## 1. What do you get?

- **Unique identity** via `did:key`
- **Verifiability**: prove a meta document (and optionally messages) is authored by the DID key holder
- **Pluggable trust policy**: the protocol provides verification; “who to trust” is a local policy decision
- **Optional VC**: an attachment point for attestations, without forcing a credit system

---

## 2. Recommended MVP choices (modern + interoperable)

- DID method: `did:key`
- Signature: JWS (`alg=EdDSA`, Ed25519)
- Signing input: hash of canonical JSON (reduces cross-language differences)

---

## 3. Enable meta proof in Bridge (recommended for discovery/directory use)

By default, discovery meta is “unverified”.  
When enabled, Bridge will attach:

- `did`: Bridge’s `did:key`
- `proof`: a JWS over the canonical hash of `meta_without_proof`

### 3.1 Environment variables

In `.env` (or container env):

```bash
BRIDGE_ENABLE_META_PROOF=1

# Written into meta.endpoints (optional)
BRIDGE_PUBLIC_URL=https://bridge.example.org

# Optional: keep DID stable across restarts (base64 seed)
# Do not commit real seeds into the repo.
BRIDGE_DID_SEED_B64=BASE64_SEED
```

If no seed is provided, the identity may be ephemeral (restart can change it). In production, keep a stable seed and store it securely.

---

## 4. What happens when verification fails?

Following RFC-004 recommended semantics:

- **Discovery/directory**: mark meta as `unverified`; do not auto-route by default (still ok to display with warnings).
- **Message exchange**: drop invalid messages by default and log security events (optional downgrade mode is possible but not recommended as default).

---

## 5. Optional VC: where to attach attestations?

You may add (optional) fields like:

```json
{
  "credentials": [
    { "type": "vc", "uri": "https://issuer.example.org/vc/123", "issuer": "did:key:..." }
  ]
}
```

Whether you trust an issuer/schema is a local policy decision.

