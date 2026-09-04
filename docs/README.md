# Software Design Document (SDD) - WiFi Tickets API

Welcome to the **Software Design Document (SDD)** and system specification repository for the WiFi Tickets backend platform.

This documentation serves as the **Single Source of Truth (SSOT)** for architecture design, domain rules, system invariants, and engineering standards.

> [!IMPORTANT]
> **Working Language Policy (100% English):**  
> The official working language of this repository is strictly **English**. All source code, identifiers, comments, docstrings, git commit messages, and technical documentation must be written in English. Non-English text is permitted exclusively within translation catalogs (`locale/<lang>/LC_MESSAGES/django.po`) and test assertions verifying localized responses.

---

## 🧭 Documentation Structure

```text
docs/
├── README.md                          # This document: master index and core architectural principles
│
├── general/                           # Cross-cutting guidelines across the entire API
│   ├── i18n_guidelines.md             # Internationalization system, Accept-Language, and response envelopes
│   ├── testing_guidelines.md          # Testing standards, sub-domains, and sub-second performance pillars
│   └── api_architecture.md            # DRF conventions, standard envelopes (data/error), and idiomatic serializers
│
└── domains/                           # Domain-specific specifications and business rules
    ├── users.md                       # Authentication, password lifecycle, Google Sign-In, and JWT
    ├── routers.md                     # MikroTik connectivity, multi-tenant memberships, and RBAC
    ├── tickets.md                     # Batch voucher generation, lifecycle, and strict cancellation rules
    ├── hotspot.md                     # Active sessions, captive portal templates, and path traversal security
    └── scripts.md                     # Jinja2 template rendering engine and remote RouterOS execution
```

---

## 🏛️ Core Architectural Principles

1. **Sub-Domain Oriented Architecture**:
   - The backend is partitioned into bounded contexts: `users`, `routers`, `tickets`, `hotspot`, and `scripts`.
   - Each domain encapsulates its own models, serializers, viewsets, services, and isolated test suites.

2. **Design by Contract & Invariant Enforcement**:
   - Business invariants (e.g., *"tickets can only be cancelled while in PENDING status"*, *"a user cannot hold more than one role per router"*) are enforced at both the database layer (constraints) and API layer (native DRF validators).

3. **Native Internationalization (i18n)**:
   - All client-facing messages (errors, validation feedback, operation details) are marked for translation and dynamically negotiate language based on the `Accept-Language` HTTP header.

4. **1:1 Traceability between Specifications and Tests**:
   - Every rule outlined in the domain specifications is backed by an automated test within `apps/<domain>/tests/test_<subdomain>.py`.
   - No business rule is deployed without accompanying automated acceptance tests.

5. **High-Performance Test Suite (Deterministic, Sub-Second)**:
   - The test suite executes in sub-seconds (~0.47s) via three pillars: `setUpTestData` (class-level database setup), `MD5PasswordHasher` (lightweight hashing during tests), and `--keepdb` (test schema reuse).

---

## 🔗 Quick Links

* [Internationalization Guidelines (i18n)](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/general/i18n_guidelines.md)
* [Testing & Performance Guidelines](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/general/testing_guidelines.md)
* [API Architecture & DRF Conventions](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/general/api_architecture.md)
* [Domain: Users](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/domains/users.md)
* [Domain: Routers](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/domains/routers.md)
* [Domain: Tickets](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/domains/tickets.md)
* [Domain: Hotspot](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/domains/hotspot.md)
* [Domain: Scripts](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/docs/domains/scripts.md)
