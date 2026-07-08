# 🏢 Backend (The Core Engine)

## What is this folder?
Welcome to the `backend`! Think of this entire folder as the main engine of a car. While the mobile app or the WhatsApp bot is the steering wheel and dashboard that the user interacts with, this folder is where the actual heavy lifting happens. It contains the central logic for the entire Mesiri platform. 

It handles security (who is allowed to do what), stores all the important data (users, projects, materials), and makes sure all the different parts of the platform run smoothly.

## What's inside right now?
Here are the main pieces you'll see in this root folder:

*   **`src/` (Source Code):** This is the actual engine block. It contains all the Python code that makes the backend work (the business logic, the database connections, the API routes). 
*   **`migrations/` (Database History):** Think of this as the architectural blueprints for your database. Every time you want to add a new table (like a new "Invoices" table), you write a migration file here. It keeps a history of how your database structure changes over time.
*   **`apps/`:** Scripts or mini-applications that help manage this backend environment.
*   **`tests/`:** The quality assurance department. It contains code that automatically checks if the engine (`src/`) is working correctly without having to test it manually.

## 🛠️ Workflow Example
Imagine a user opens the mobile app and tries to view a list of their assigned projects.
1. The mobile app sends a request over the internet asking for the projects.
2. That request arrives at this **`backend`** engine.
3. The engine checks if the user is logged in and authorized.
4. The engine asks the database for the user's projects.
5. The engine packages that data up and sends it back to the mobile app.

## What should go here in the future?
*   **Configuration Files:** If you need to add a new global setting (like a new `.env` file template, or a docker-compose configuration file to run the server), it usually goes in this root folder.
*   **DO NOT** put direct business logic (like a new file called `calculate_taxes.py`) directly in this root folder. All the actual working code belongs deep inside the `src/mesiri/` folder, which we will explore next!
