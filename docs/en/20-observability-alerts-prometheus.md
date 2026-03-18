## Prometheus alert recommendations (minimal template)

> Goal: provide operators a copy-paste starting point. Thresholds must be tuned to your node size and traffic.

### 1) Relay (public entry)

```yaml
groups:
  - name: open-a2a-relay
    rules:
      - alert: OA2ARelayDown
        expr: oa2a_relay_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Relay is down"
          description: "Relay /metrics did not expose oa2a_relay_up=1."

      - alert: OA2ARelayClientsSpike
        expr: (oa2a_relay_clients - oa2a_relay_clients offset 5m) > 200
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Relay client spike"
          description: "Clients increased by >200 within 5 minutes (abuse or reconnect storm)."
```

### 2) Bridge (directory/adapter)

```yaml
groups:
  - name: open-a2a-bridge
    rules:
      - alert: OA2ABridgeDown
        expr: oa2a_bridge_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Bridge is down"

      - alert: OA2ABridgeNatsDisconnected
        expr: oa2a_bridge_nats_connected == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Bridge disconnected from NATS"

      - alert: OA2ABridgeProvidersDrop
        expr: (oa2a_bridge_discovery_providers_total - oa2a_bridge_discovery_providers_total offset 5m) < -50
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Providers dropped sharply"
          description: "Providers decreased by >50 within 5 minutes (mass offline / renewal failure / misconfigured cleanup)."
```

### 3) Federation SubjectBridge (X↔Y)

```yaml
groups:
  - name: open-a2a-federation
    rules:
      - alert: OA2AFedBridgeDown
        expr: oa2a_fed_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "SubjectBridge is down"

      - alert: OA2AFedErrorsGrowing
        expr: increase(oa2a_fed_errors_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "SubjectBridge forwarding errors"
          description: "errors increased by >10 within 5 minutes (NATS unreachable / permissions / subject misconfig)."
```

