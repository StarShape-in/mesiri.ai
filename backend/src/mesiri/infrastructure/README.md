# 🚰 Infrastructure (The Plumbing)

## What is this folder?
Welcome to the `infrastructure` folder! If the `domains` folder is the brain of the company making decisions, this folder is the physical filing cabinets, the warehouse, and the telephone lines.

This folder is responsible for talking to the "outside world" or any external services. It doesn't know *why* a project needs to be saved, it just knows *how* to save it to a PostgreSQL database or *how* to cache it in Redis.

## What's inside right now?
*   **`postgres/`:** The adapters and models for talking to your main relational database. This is where the physical tables (like `users` and `organizations`) are defined.
*   **`redis/`:** The adapters for talking to your fast, temporary memory cache.
*   **`objectstorage/` (or similar like `r2`):** The adapters for saving actual physical files, like uploading a PDF document or a photo of a construction site.

## 🛠️ Workflow Example
Imagine a user edits their profile and changes their phone number.
1. The `domains/users/` folder (the brain) decides that the new phone number is valid and the user is allowed to make this change.
2. The brain then hands the new phone number down to the `infrastructure/postgres/` folder.
3. The code in `postgres/` actually writes the SQL query (`UPDATE users SET phone = ...`) and sends it over the wire to the physical database server.
4. The database saves it, and the infrastructure reports back to the brain: *"Done! The filing cabinet is updated."*

## What should go here in the future?
*   **Database Models:** If you add a new feature (like "Invoices") in the `domains` folder, you will need to create a new file in `infrastructure/postgres/models/` to define exactly what an "Invoice" looks like in the database (which columns it has).
*   **New Integrations:** If you decide to start sending SMS text messages using Twilio, you would create a `twilio/` folder in here. The `infrastructure` folder handles the raw connection to Twilio's servers.
*   **DO NOT** put business rules here. This folder should not care if a user is an admin or a regular user; it should only do exactly what it's told to do by the `domains` folder!
