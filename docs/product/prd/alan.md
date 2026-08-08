# Alan's PRD Suggestions & Feedback – Mesiri Daily

After thinking about Mesiri Daily as a standalone product, and based on learnings from construction site visits, here are key suggestions to incorporate into the product specifications.

---

## 1. Project Pulse
Instead of opening a dashboard full of complex charts, the project owner should see a single, simple summary for a 30-second understanding of the day's status:
* 🟢 **Project Healthy**
* **Today's Progress:** 85%
* ⚠️ **One Delay**
* 💰 **₹18,000 spent today**
* 👷 **24 workers present**
* 📸 **18 new photos**

---

## 2. AI Verification (Critical)
AI should not silently save extracted information. The workflow must include user verification:
1. **WhatsApp Message Sent**
2. **AI Extracts Data**
3. **Engineer Receives Verification Prompt:**
   > *"I understood:*
   > * *Cement: 20 bags*
   > * *Labour: 12*
   > * *Slab completed*
   > * **Is this correct?**"
4. **User Confirms / Edits**
5. **Data Saved**

This builds trust and reduces data ingestion errors.

---

## 3. Evidence-Backed Timeline Events
Every event on the timeline must be backed by concrete evidence (audio, visual, or textual):
* Voice note
* Photo
* Text message
* Document

**Example:**
* **10:30 AM** – Concrete poured
  * *Evidence:* 📷 3 Photos, 🎤 Voice Note
  * *Reported by:* Rahul

---

## 4. Daily Summary Review Before DPR
Introduce a review step before generating the final Daily Progress Report (DPR):
$$\text{Events} \longrightarrow \text{AI Summary} \longrightarrow \text{Engineer Reviews} \longrightarrow \text{Generate DPR}$$
This gives users a final chance to catch errors.

---

## 5. AI Daily Highlights
Every evening, generate high-level daily highlights for managers who don't need line-item details:
* Slab work completed.
* 25 cement bags consumed.
* Rain delayed work by 2 hours.
* ₹15,000 labour payment recorded.

---

## 6. Global Search
A single search box to query the entire project memory:
* *"Show all water issues."*
* *"Find cement deliveries."*
* *"Show last week's expenses."*
* *"Who reported this delay?"*

---

## 7. Evidence-Based "Ask Mesiri"
When users query the project history, answers must reference supporting timeline events rather than general statements:
* **User:** *"Why was the project delayed?"*
* **Mesiri:** *"The project was delayed because:*
  * *Rain (2 hrs)*
  * *Concrete pump breakdown (1 hr)*
  * *Electrician arrived one day late"*
  *(Each point links back to the supporting timeline events).*

---

## 8. Smart Notifications
Avoid notification fatigue by notifying only on critical alerts:
* Delay exceeds a defined threshold
* Large expense recorded
* Material shortage
* No updates received from site by evening
* Safety issue reported

---

## 9. Separate "Raw Events" from "Insights"
Maintain a strict logical separation:
* **Timeline (Facts):** Cement delivered, work completed, expense added.
* **Insights (AI Interpretation):** Cement usage is higher than average, labour productivity decreased, rain caused repeated delays this week.

---

## 10. Build for Extension
Store event data so it can feed future modules (Procurement, Inventory, Finance, HR, etc.) without re-entry:
* Expense events must capture structure reusable by a future Finance module.
* Material events should map to future Inventory schemas.
* Labour updates should support future HR/productivity analytics.

---

## Guiding Principle (Core Focus)
> [!IMPORTANT]
> *"If an event happens on a construction site, Mesiri Daily should be able to capture it in under 30 seconds through WhatsApp and make it permanently searchable, understandable, and useful for decision-making."*
> 
> This principle keeps the product focused and prevents it from bloat or turning into a mini ERP prematurely.
