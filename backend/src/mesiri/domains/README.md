# 🧠 Domains (The Business Logic)

## What is this folder?
Welcome to the `domains` folder! If the whole backend is a company, this folder is the collection of all the different departments (HR, Accounting, Operations). 

This is the most important folder in the entire system when it comes to "What does our app actually do?". It is organized by **Features** (or "Domains"), not by technical file types. Every set of rules for how your business operates lives here.

## What's inside right now?
If you look around, you'll see folders like:
*   **`users/`:** The "HR Department". Everything related to managing employees, user profiles, and their status.
*   **`projects/`:** The "Operations Department". Everything related to creating, updating, or assigning construction projects.
*   **`approvals/`:** The "Compliance Department". The specific rules for who can approve what, and what steps are required.

Inside each of these folders, you will typically find the logic that answers questions like "Is this user allowed to do this?" or "What happens after a project is completed?".

## 🛠️ Workflow Example
Imagine a manager uses the web dashboard to **Approve a new Vendor**.
1. The request enters the backend.
2. It is routed directly to the `domains/vendors/` folder.
3. The code in `vendors/` checks the business rules: *"Does this manager have the correct permissions? Has the vendor uploaded their insurance documents?"*
4. If everything looks good, it marks the vendor as "Approved" and might send a signal to the `domains/notifications/` folder to email the vendor.

## What should go here in the future?
*   **New Features:** If you are building a completely new feature, like a system to track "Vehicles" (trucks, cranes), you would create a brand new folder here called `vehicles/`.
*   **Business Rules:** Any time you need to change a rule (e.g., *"Projects now require 2 approvals instead of 1"*), you will edit the files inside the relevant folder here.
*   **DO NOT** put database connection logic (like SQL queries) or internet routing (like API endpoints) directly into the core logic files here. The business logic should just focus on the rules, and let other folders handle the plumbing!
