# Project Overview

## 1. Background & Vision: A "Free Protocol" Without Middlemen

### Core Pain Point: Platform Monopoly & Tax

- Current interactions (food delivery, ride-hailing, services) must go through centralized platforms
- Platforms control data and take 10%–30% commission from every transaction
- Platforms manipulate consumer choices through algorithms

### Vision: The Agentic Economy

- **Agent-to-Agent Direct Connection**: When AI assistants become ubiquitous, interactions should happen directly between Agents  
  A-Agent (Consumer) ➔ B-Agent (Merchant) ➔ C-Agent (Delivery)
- **Zero Commission**: Remove intermediaries; value flows 100% to participants
- **Taste Sovereignty**: AI assistants serve their owners, not platform bidding rankings

### Target Users

- Open source developers worldwide
- Web3 enthusiasts
- Researchers

---

## 2. Product Positioning

Our goal is to define **"the TCP/IP of the post-internet era"**. We don't sell software; we build rules.

### Design Premises

- **Compute is cheap**: Assume inference cost is acceptable
- **Each user has an Agent**: Consumers, merchants, riders each run their own AI Agent
- **No reinventing the wheel**: Core AI capabilities come from mature runtimes like [OpenClaw](https://github.com/openclaw/openclaw) and [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw); Open-A2A focuses on the protocol layer

### Repository Structure

| Directory | Description |
|-----------|-------------|
| `/spec` | Core protocol docs (how Agents handshake, negotiate, etc.) |
| `/core` | Python reference implementation (SDK) |
| `/example` | Full Demo: food delivery scenario |
