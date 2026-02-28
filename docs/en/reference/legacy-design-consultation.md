# Archived: Early Design Consultation Document

> This document is archived. For current architecture and requirements, see the main docs.  
> The full Chinese version is in [../zh/reference/legacy-design-consultation.md](../zh/reference/legacy-design-consultation.md).

---

## Summary

This was an early technical consultation document exploring how distributed, heterogeneous AI Agents could interact and collaborate without centralized platforms. It covered:

- **Core challenges**: Addressing, protocols, infrastructure, trust
- **Proposed solution**: Layered protocol stack (trust layer → agent capability layer → collaboration layer)
- **Typical flow**: Discovery → Connect & Auth → Negotiate → Contract → Execute & Settle

The current Open-A2A architecture (three-tier mesh) evolved from these ideas. See [03-architecture.md](../../en/03-architecture.md) for the current design.
