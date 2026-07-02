# Mesiri.ai – Product Requirements Document (PRD)

**Product:** Mesiri.ai  
**Version:** Version 1.0 – Mesiri Daily  
**Status:** Draft  
**Document Owner:** Ilan & Alan  

---

## 1. Product Vision

Mesiri.ai is an AI-powered construction operations platform designed to simplify project execution by allowing site teams to work through familiar communication channels instead of traditional ERP software.

Version 1 (Mesiri Daily) focuses on helping engineers and supervisors capture daily work updates through WhatsApp while giving project managers and company owners structured visibility into project progress through a mobile application.

This version serves as the foundation of the future Mesiri platform, where additional operational modules such as Procurement, Inventory, Finance, HR, BOQ, and Equipment Management can be introduced without changing the core product.

---

## 2. Problem Statement

Construction projects generate large amounts of operational information every day.

This information is usually shared through:
* WhatsApp messages
* Voice notes
* Images
* Phone calls
* Handwritten notes

As a result:
* Daily Progress Reports (DPRs) are difficult to prepare.
* Project history becomes fragmented.
* Important decisions are lost.
* Material usage is not tracked consistently.
* Expenses are recorded late or forgotten.
* Owners lack real-time visibility into project status.

Teams spend more time documenting work than managing it.

---

## 3. Product Goal

Create the easiest way for construction teams to record and understand daily site activities.

The system should require minimal training by allowing users to continue using WhatsApp while AI automatically converts conversations into structured project data.

---

## 4. Target Users

* **Site Engineer**: Captures daily activities.
* **Site Supervisor**: Shares work updates from the field.
* **Project Manager**: Monitors project progress.
* **Company Owner**: Receives high-level project insights.

---

## 5. Version 1 Scope

Mesiri Daily consists of:
* WhatsApp Assistant
* Mobile Application
* AI Processing Engine
* Project Timeline
* Daily Progress Reports (DPR)
* AI Memory
* Daily Analytics

No ERP modules are included in Version 1.

---

## 6. Core Features

### WhatsApp Assistant
Users interact with Mesiri entirely through WhatsApp.

Supported inputs:
* Text messages
* Voice notes
* Images
* Documents

The assistant should understand natural language and maintain conversation context.

### Daily Timeline
Automatically create a chronological timeline of project activities.

Examples include:
* Work completed
* Material deliveries
* Expenses
* Site observations
* Delays
* Weather-related updates
* Photos
* Voice recordings

### Daily Progress Reports (DPR)
Generate structured DPRs automatically from collected project information.

Reports should summarize:
* Completed work
* Ongoing work
* Delays
* Material consumption
* Expenses
* Supporting media
* AI-generated summary

### Expense Capture
Allow users to submit expenses directly through WhatsApp.

Examples:
* Labour payments
* Transport
* Fuel
* Equipment
* Miscellaneous site expenses

AI should extract structured information from messages.

### Material Usage
Capture:
* Materials received
* Materials consumed
* Material requests

AI converts conversational updates into structured records.

### Field Updates
Users can quickly report:
* Progress
* Issues
* Risks
* Delays
* Blockers

### AI Memory
The assistant remembers previous project activities.

Users can ask questions such as:
* What work was completed yesterday?
* When was the cement delivered?
* Show expenses from last week.
* What delays happened this month?

### Mobile Dashboard
Provide a mobile-first dashboard showing:
* Active projects
* Daily timeline
* DPRs
* Expenses
* Material usage
* Notifications
* Project summary
* AI insights

---

## 7. Out of Scope (Version 1)

The following features are intentionally excluded from Version 1:
* Procurement
* Inventory Management
* Purchase Orders
* Vendor Management
* Finance & Accounting
* HR & Payroll
* BOQ Management
* Equipment Management
* CRM
* Desktop Application
* Client Web Dashboard
* Internal Control Panel

These will be introduced in future platform versions.

---

## 8. Functional Requirements

The platform must:
* Support multiple companies (multi-tenant architecture).
* Support multiple projects per company.
* Support multiple users per project.
* Store project history permanently.
* Process text, voice, image, and document inputs.
* Generate structured project records.
* Generate DPRs automatically.
* Allow natural-language querying of project history.
* Send intelligent WhatsApp responses.
* Synchronize data with the mobile application.

---

## 9. Non-Functional Requirements

* Mobile-first experience.
* Fast response times.
* Secure authentication.
* Tenant data isolation.
* Scalable architecture.
* AI processing pipeline.
* Reliable media storage.
* Auditability of captured data.

---

## 10. Success Metrics

Version 1 will be considered successful if it can:
* Reduce manual DPR preparation time significantly.
* Capture daily updates consistently through WhatsApp.
* Generate reliable project timelines.
* Improve visibility for project managers.
* Be actively adopted by pilot construction companies.

---

## 11. Product Principles

* WhatsApp is the primary interaction interface.
* AI should reduce manual data entry, not increase it.
* The product should feel simple despite handling complex workflows.
* Every feature should save time for field teams.
* Mobile experience takes priority in Version 1.
* Future ERP capabilities must build on the same platform rather than becoming separate products.

---

## 12. Future Roadmap

After Mesiri Daily is validated with real customers, the platform will expand through modular capabilities, including:
* Procurement
* Inventory
* Finance
* HR
* BOQ
* Vendor Management
* Equipment Management
* Quality & Safety
* Analytics
* Web Dashboard
* Desktop Application
* Internal Control Panel

Each module will extend the existing Mesiri platform without requiring customers to migrate to a different product.
