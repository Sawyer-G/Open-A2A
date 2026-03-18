## Prometheus 告警建议（最小模板）

> 目标：给运营者一个“能直接抄走”的告警起点。阈值需要按你节点规模与流量再调优。

### 1) Relay（公网入口）

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
          summary: "Relay 进程不可用"
          description: "Relay /metrics 未返回 oa2a_relay_up=1。"

      - alert: OA2ARelayClientsSpike
        expr: (oa2a_relay_clients - oa2a_relay_clients offset 5m) > 200
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Relay client 数异常增长"
          description: "5 分钟内增加超过 200，可能被滥用或出现重连风暴。"
```

### 2) Bridge（目录/适配层）

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
          summary: "Bridge 进程不可用"

      - alert: OA2ABridgeNatsDisconnected
        expr: oa2a_bridge_nats_connected == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Bridge 与 NATS 断开"

      - alert: OA2ABridgeProvidersDrop
        expr: (oa2a_bridge_discovery_providers_total - oa2a_bridge_discovery_providers_total offset 5m) < -50
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "目录在线 providers 明显下降"
          description: "5 分钟内下降超过 50，可能是大面积掉线/续租失败/清理误配。"
```

### 3) Federation SubjectBridge（X↔Y）

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
          summary: "SubjectBridge 进程不可用"

      - alert: OA2AFedErrorsGrowing
        expr: increase(oa2a_fed_errors_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "SubjectBridge 转发错误增长"
          description: "5 分钟内 errors 增量 > 10，可能是目标 NATS 不可达/权限不足/主题不允许。"
```

