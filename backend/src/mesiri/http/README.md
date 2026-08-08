# 🚪 HTTP (The Front Door)

## What is this folder?
Welcome to the `http` folder! If the `domains` folder is the brain and the `infrastructure` is the plumbing, this folder is the Receptionist Desk at the front of the building.

This folder is responsible for catching incoming network requests from the outside world (like from a mobile phone app or a web browser) and routing them to the correct department inside the building.

## What's inside right now?
*   **`app.py`:** This is the main "receptionist". It configures the FastAPI web server, sets up security badges (CORS), handles health checks (to prove the server isn't crashed), and connects all the different "routers" from the various domains.

## 🛠️ Workflow Example
Imagine a mobile app wants to **Create a New Project**.
1. The mobile app sends a standard internet HTTP `POST` request to a URL like `api.mesiri.com/projects/create`.
2. The `app.py` file in this folder is the very first thing to catch that request.
3. The receptionist (`app.py`) says: *"Ah, this is a request for the Projects department. Let me pass this message along to the `projects` domain."*
4. It hands the request off to the business logic (`domains/projects/`), which does the actual work.
5. Once the `domains` folder is finished, it hands a success message back to the receptionist.
6. The receptionist (`http`) packages that success message into an internet HTTP `200 OK` response and sends it back out to the mobile app.

## What should go here in the future?
*   **Middleware:** If you want to add a rule that applies to *every single request* entering the building (like a spam filter, or a logger that records how long every request takes), you would add that middleware code in this folder.
*   **Server Configuration:** Any settings related strictly to the web server (like how large of a file upload is allowed over the internet) go here.
*   **DO NOT** put business logic here. The receptionist shouldn't be deciding if a project is approved or denied; they just pass the message to the correct department!
