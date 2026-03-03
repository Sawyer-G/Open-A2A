# Relay End-to-End Encryption – Local Verification

## Prerequisites

- Installed: `make venv && make install && make install-relay`
- For payload E2E verification: `make install-e2e`
- Local NATS: `docker run -p 4222:4222 nats:latest` (or an existing NATS service)

---

## 1. Basic Check: Connectivity via Relay (No Encryption)

Verify that a Consumer connecting via Relay and a Merchant connecting directly to NATS can talk to each other.

**Terminal 1 – NATS**

```bash
docker run -p 4222:4222 nats:latest
```

**Terminal 2 – Relay**

```bash
make run-relay
# You should see: [Relay] WebSocket listening on ws://0.0.0.0:8765
```

**Terminal 3 – Merchant (direct NATS)**

```bash
make run-merchant
```

**Terminal 4 – Consumer (via Relay)**

```bash
RELAY_WS_URL=ws://localhost:8765 .venv/bin/python example/consumer_via_relay.py
```

**Expected**:  
Consumer prints "received N offers", Merchant prints received intent and sent offer. This confirms the Relay bridge works.

---

## 2. Verify TLS (wss)

Enable TLS on Relay and connect clients using `wss://`.

**1. Generate a self-signed certificate (testing only)**

```bash
openssl req -x509 -newkey rsa:4096 -keyout relay-key.pem -out relay-cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

**2. Start Relay with TLS**

```bash
export RELAY_WS_TLS=1
export RELAY_WS_SSL_CERT=$(pwd)/relay-cert.pem
export RELAY_WS_SSL_KEY=$(pwd)/relay-key.pem
make run-relay
# You should see: TLS enabled (wss://), WebSocket listening on wss://0.0.0.0:8765
```

**3. Start Merchant (same as before, direct NATS)**

```bash
make run-merchant
```

**4. Test Consumer using wss**

```bash
export RELAY_WS_URL=wss://localhost:8765
# Self-signed cert will fail SSL verification; for local testing only, you can skip verification:
.venv/bin/python -c "
import os, ssl, asyncio, websockets
os.environ['RELAY_WS_URL'] = 'wss://localhost:8765'

async def run():
    ws = await websockets.connect(
        'wss://localhost:8765',
        ssl=ssl._create_unverified_context(),  # DO NOT use this in production
        close_timeout=1,
    )
    print('wss connection ok')
    await ws.close()

asyncio.run(run())
"
```

Or, use the provided Consumer example with environment flags:

```bash
RELAY_WS_URL=wss://localhost:8765 RELAY_WS_SSL_VERIFY=0 .venv/bin/python example/consumer_via_relay.py
```

**Expected**:  
The `wss` connection succeeds, confirming the TLS channel is established.

---

## 3. Verify Payload E2E (Relay Cannot See Plaintext)

Both ends use the same shared secret; Relay only sees ciphertext. Both ends go through Relay and use `EncryptedTransportAdapter`.

**1. Start NATS + Relay**  
(same as above, Terminals 1 and 2)

**2. Run the E2E verification script (simulated both ends in one process)**

```bash
make install-e2e
.venv/bin/python example/relay_e2e_verify.py
```

Inside the script:

- One side uses `EncryptedTransportAdapter(RelayClientTransport(...), shared_secret=b"test-secret")` to publish.
- The other side uses the same secret to subscribe and decrypt.

**Expected**:  
Script prints something like "received decrypted message: ..." which confirms payload E2E encryption/decryption works correctly.

---

## 4. Optional: Combine with Business Examples (Payload E2E)

If you want both `consumer_via_relay.py` and a Merchant to use payload E2E:

- Both sides must use `EncryptedTransportAdapter` with the **same** secret.
- Currently `merchant.py` connects directly to NATS; to test "Consumer via Relay + E2E, Merchant via Relay + E2E", you can:
  - Create a temporary `merchant_via_relay.py` that uses `EncryptedTransportAdapter(RelayClientTransport(...), shared_secret=...)`;
  - Configure the same secret on both sides (for example via an env var like `OPEN_A2A_RELAY_PAYLOAD_SECRET`).

This setup ensures the Relay node never sees the plaintext payload, while Agents still benefit from Relay-based reachability.

