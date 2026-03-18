# Open-A2A Documentation (English)

> Decentralized Agent-to-Agent Protocol — The TCP/IP of the Post-Internet Era

## Documentation

| Document | Description |
|----------|-------------|
| [**00-design-principles.md**](./00-design-principles.md) | **Design principles**: core goals, relationship to example scenarios (required) |
| [01-project-overview.md](./01-project-overview.md) | Project overview: background, vision, target users |
| [02-requirements.md](./02-requirements.md) | Product requirements: features, user story, constraints |
| [03-architecture.md](./03-architecture.md) | System architecture: three-tier mesh, tech stack |
| [04-roadmap.md](./04-roadmap.md) | Development roadmap: MVP phases |
| [05-development-guide.md](./05-development-guide.md) | Development guide: resource stack, competitors |
| [06-progress.md](./06-progress.md) | **Project progress**: completed items and verification |
| [07-multi-language-sdk.md](./07-multi-language-sdk.md) | Multi-language SDK planning: future expansion reference |
| [08-solid-self-hosted.md](./08-solid-self-hosted.md) | **Self-hosted Solid Pod**: recommended for data sovereignty |
| [09-deployment-and-openclaw-integration.md](./09-deployment-and-openclaw-integration.md) | **Deployment & OpenClaw integration** |
| [09-openclaw-docker-quickstart.md](./09-openclaw-docker-quickstart.md) | **OpenClaw (Docker) quickstart**: avoid common network pitfalls |
| [10-nats-cluster-federation.md](./10-nats-cluster-federation.md) | NATS cluster & federation: multi-node shared subject space |
| [11-relay-e2e-verify.md](./11-relay-e2e-verify.md) | Relay end-to-end encryption verification |
| [12-cross-ip-testing.md](./12-cross-ip-testing.md) | **Cross-IP testing guide**: real-world network validation |
| [13-security-considerations.md](./13-security-considerations.md) | **Security considerations**: threat model, risks, and best practices |
| [14-user-story-pizza-delivery.md](./14-user-story-pizza-delivery.md) | **User story (pizza delivery)**: an end-to-end A/B/C flow via a public node X |
| [15-node-x-operator-kit.md](./15-node-x-operator-kit.md) | **Node X operator kit**: copyable config checklist, ports, and a diagnose script |
| [16-multi-operator-federation-subject-bridge.md](./16-multi-operator-federation-subject-bridge.md) | **Multi-operator federation (Option 2)**: independent NATS + selective subject bridging (MVP) |
| [17-identity-and-trust.md](./17-identity-and-trust.md) | **Identity & trust (operator guide)**: DID, signatures, and optional VC (RFC-004) |
| [18-dht-bootstrap-guide.md](./18-dht-bootstrap-guide.md) | **DHT bootstrap guide**: preferred cross-node discovery path (OPEN_A2A_DHT_BOOTSTRAP) |
| [openclaw-tool-example.md](./openclaw-tool-example.md) | OpenClaw Tool configuration example |

## Standards

| Document | Description |
|----------|-------------|
| [standards/01-project-structure.md](./standards/01-project-structure.md) | Project structure, code organization, naming |
| [standards/02-documentation.md](./standards/02-documentation.md) | Documentation standards |
| [standards/03-contribution.md](./standards/03-contribution.md) | Contribution guide, commit & PR conventions |
| [standards/git.md](./standards/git.md) | Git workflow, branch strategy |

## Reference

| Document | Description |
|----------|-------------|
| [reference/legacy-design-consultation.md](./reference/legacy-design-consultation.md) | Archived: early design consultation (Chinese) |

## Reading Order

1. **Newcomers**: 00 (design principles) → 01 → 02 → 03 → 04
2. **Developers**: 00 → 03 → 05 → 04, then `standards/01-project-structure.md`
3. **Contributors**: All docs + all standards
