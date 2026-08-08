# Mesiri.ai – Product Requirements Document (PRD)

**Product:** Mesiri.ai  
**Version:** Version 1.0 – Mesiri Daily  
**Status:** Proposal for Approval  
**Document Owner:** Ilan & Alan  

---

## 1. Product Vision & Core Principle

Mesiri.ai is an AI-powered construction operations platform designed to simplify project execution by allowing site teams to work through familiar communication channels instead of traditional ERP software.

Version 1 (Mesiri Daily) focuses on helping engineers and supervisors capture daily work updates through WhatsApp while giving project managers and company owners structured visibility into project progress through a mobile application.

### Guiding Principle
> [!IMPORTANT]
> **The Under-30-Seconds Rule:**  
> *"If an event happens on a construction site, Mesiri Daily must be able to capture it in under 30 seconds through WhatsApp and make it permanently searchable, understandable, and useful for decision-making."*
> 
> Every feature in Mesiri Daily must support this principle to maintain focus and prevent the application from expanding prematurely into a complex ERP system.

---

## 2. Problem Statement

Construction projects generate massive amounts of daily operational data (messages, voice notes, photos, documents) that are scattered across personal channels, leading to:
* High friction in preparing Daily Progress Reports (DPRs).
* Fragmented project history and lost decisions.
* Delayed recording of material usage and expenses.
* Lack of real-time project health visibility for company owners.

---

## 3. Target Users

* **Site Engineer / Supervisor:** Captures daily work activities, materials, and expenses from the field via WhatsApp.
* **Project Manager:** Monitors timeline events, reviews daily progress summaries, and generates official DPRs.
* **Company Owner (Managing Director):** Reviews high-level daily health metrics and key insights in a 30-second window.

---

## 4. Version 1 Scope

### In Scope:
* **WhatsApp Assistant:** Interface for field data capture.
* **AI Processing Engine:** Natural language extraction, parsing, and context maintenance.
* **Evidence-Backed Timeline:** Chronological feed of site events.
* **Daily Progress Reports (DPR):** Generated from verified summaries.
* **AI Memory Engine:** Evidence-linked natural language query interface.
* **Mobile-First Dashboard:** Real-time visibility and verification interface.

### Out of Scope:
* Procurement, Inventory, Purchase Orders, Finance, Accounting, HR, Payroll, BOQ, and Equipment Management.
* Desktop Application, Client Web Dashboard, and Super Admin Control Panel.

---

## 5. Functional Requirements & Feature Specifications

### A. WhatsApp Assistant & AI Verification Workflow
Users interact with Mesiri entirely through WhatsApp via text, voice notes, images, or documents. 
* **Verify-Before-Save Workflow:** The AI must never silently ingest data.
  1. User sends message/media (e.g., *"20 bags cement received, slab work finished"*).
  2. AI parses the input.
  3. AI replies with a structured confirmation prompt:
     > *"I understood:*
     > * *Cement: 20 bags received*
     > * *Progress: Slab work finished*
     > 
     > *Is this correct? [Yes/Edit]"*
  4. User confirms or adjusts the details.
  5. The event is saved to the timeline only after user confirmation.

### B. Evidence-Backed Chronological Timeline
The system structures and displays all site events (work completed, materials, expenses, delays, weather, site photos) in a chronological feed.
* **Evidence Obligation:** Every timeline event must link back to its raw source of truth (the specific voice note, photo, text message, or document) and identify the reporter (e.g., *"10:30 AM – Concrete poured. Evidence: [Photo1.jpg], [VoiceNote.mp3] | Reported by Rahul"*).
* **Data Separation:**
  * **Raw Events (Facts):** Direct data points (e.g., *"Cement delivered"*, *"₹15,000 paid to loaders"*).
  * **AI Insights (Interpretations):** Highlighted separately to keep data clean (e.g., *"Cement usage is 15% higher than average this week"*).

### C. Daily Summary Review & DPR Generation
Instead of auto-generating and sending a DPR immediately:
1. Daily events are accumulated into an **AI-generated Daily Summary**.
2. The Site Engineer reviews, edits, and approves this summary in the mobile app.
3. Upon approval, the structured **Daily Progress Report (DPR)** is officially generated and shared.

### D. Expense & Material Tracking
* **Expense Capture:** Extract structured line items (labor payments, transport, fuel, materials, miscellaneous) from natural language messages.
* **Material Tracking:** Record materials received, consumed, and requested.
* **Future-Proof Storage:** Even though ERP modules are out of scope for V1, the data schemas for expenses, materials, and labor hours must capture essential metadata to ensure compatibility with future Finance, Inventory, and HR modules.

### E. AI Memory & Evidence-Based Q&A ("Ask Mesiri")
Users can search or query the project's historical memory using natural language.
* **Search Box:** A single global search input in the mobile dashboard to locate events, issues, or details (e.g., *"Show cement deliveries"*).
* **Evidence-Based Answers:** When answering queries, the system must not make general assertions. It must list specific events and link back to their supporting timeline evidence:
  * *Query:* *"Why was the project delayed this week?"*
  * *Answer:* *"The project was delayed by 3 hours total due to: 1. Rain on Tuesday (2 hours) [Link to Event], 2. Concrete pump breakdown on Wednesday (1 hour) [Link to Event]."*

### F. Mobile-First Dashboard & Project Pulse
Designed for owners and managers to get a 30-second operational pulse:
* **Project Pulse Metrics:** Displays a clean card with high-level daily states:
  * 🟢 Project Healthy / ⚠️ Delay Reported
  * Today's Progress: X%
  * Daily Expenses: ₹Y
  * Headcount: Z workers present
  * New Media: N photos/videos uploaded
* **Smart Notifications:** Notifications are triggered only for critical thresholds:
  * Delays exceeding a set time limit.
  * Expenses above a configured monetary threshold.
  * Material shortages.
  * Missing end-of-day site updates.
  * Reported safety hazards.

---

## 6. Product Principles
1. **WhatsApp First:** Field teams should never have to log into a heavy portal to input data.
2. **AI as an Assistant, Not a Dictator:** AI simplifies data entry but the user always controls the final verification.
3. **Strict Facts/Insights Boundary:** Never merge raw site facts with AI inferences.
4. **Design for Extensibility:** Save data in standardized formats ready to power future modules.
