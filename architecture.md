# Lab 2: Observing Cloud Architectures in Practice

**Course**: Cloud Computing — Bachelor Computer Science  
**Week**: 2 — Architectures of Distributed and Cloud Systems  
**Duration**: 60 minutes  
**Platform**: Local (Docker) — required. Azure — optional extension.  
**Submission**: Written answers to all reflection questions (Q1.1 – Q3.3)

---

## Prerequisites

### Required (everyone)
- Docker Desktop installed and running ([docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop))
- Terminal / shell access (macOS Terminal, Windows PowerShell, Linux bash)
- The lab repository cloned or downloaded:
  ```bash
  git clone https://github.com/eberhardinger-b/cloud-computing-02-architectures.git
  cd 2_Architecture
  ```

### Optional (Azure extension tasks)
- Azure for Students account activated ([azure.microsoft.com/free/students](https://azure.microsoft.com/free/students)) — use your university email, no credit card required
- Azure CLI installed ([learn.microsoft.com/cli/azure/install-azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli))

> **Note**: Every graded requirement in this lab can be completed without Azure. The Azure extension tasks are marked with 🔵 and are optional. They do not affect your grade but are good preparation for later labs.

---

## Application Overview

You will work with a simple **Notes** application — a three-tier web app that lets users create, read, and delete short text notes.

The application consists of three components:

| Component | Technology | Role |
|-----------|-----------|------|
| `frontend` | nginx (static HTML/JS) | UI served on port 8080 |
| `api` | Python / Flask REST API | Business logic, served on port 5001 |
| `db` | PostgreSQL 15 | Persistent storage |

The `api` service exposes three endpoints:
- `GET  /api/notes` — list all notes
- `POST /api/notes` — create a new note (body: `{"text": "..."}`)
- `DELETE /api/notes/<id>` — delete a note by ID

---

## Part 1 — Deploy and Inspect the Architecture (15 min)

### Task

Start the application:

```bash
docker compose up -d
```

Verify all three containers are running:

```bash
docker compose ps
```

Open the frontend in your browser: [http://localhost:8080](http://localhost:8080)

Create two or three notes using the UI, then verify the API directly:

```bash
curl http://localhost:8080/api/notes
```

Inspect the running containers and their network connections:

```bash
# See all containers and their ports
docker compose ps

# Inspect the network connecting the containers
docker network ls
docker network inspect "$(docker compose ps -q frontend | xargs docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}')"

# Check the environment variables of the api container
docker compose exec api env | grep -E '^(DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD|APP_VERSION)='
```

Look at the `docker-compose.yml` file in the repository and read through it carefully.

---

### Reflection Questions — Part 1

> **Q1.1** Draw a component diagram of the running application. Use boxes for the three components and label the arrows (connectors) with the communication mechanism used (e.g., "HTTP REST", "SQL over TCP/IP", "HTTP"). Which architectural style best describes this system — layered, service-oriented, or microservice? Justify your answer in 2–3 sentences.

> **Q1.2** Open `docker-compose.yml` and find where the database connection details (hostname, username, password) are configured for the `api` service. They are not hardcoded in the Python source code — they are passed as environment variables. Which 12-factor principle does this follow? In your own words, explain why this matters when deploying the same application to a development, staging, and production environment.

> **Q1.3** The `db` container uses a Docker **volume** to persist data. Run `docker compose down` and then `docker compose up -d` again. Are your notes still there? Now run `docker compose down -v` (which removes the volume) and restart. Are your notes still there? What does this tell you about the difference between ephemeral container storage and externalized persistent storage? Relate your answer to the stateless/stateful concepts from the lecture.

---

## Part 2 — Scaling and Stateless Behavior (20 min)

### Task

Scale the `api` service to three instances:

```bash
docker compose up -d --scale api=3
```

Verify three API containers are running:

```bash
docker compose ps
```

The `frontend` nginx container proxies requests to the `api` service. Each API instance returns its container hostname in a custom response header `X-Instance-ID`. Run the following to send 15 requests and observe which instance handles each one:

```bash
for i in $(seq 1 15); do
  curl -s -I http://localhost:8080/api/notes | grep X-Instance-ID
done
```

If all requests show the same `X-Instance-ID`, treat this as part of the exercise: scaling replicas alone is not enough; traffic distribution also depends on load-balancer and service-discovery behavior.

Your task is to debug and improve the nginx/API routing setup so requests are distributed across instances.

Acceptance criterion:
- In 30 requests, at least 2 different `X-Instance-ID` values appear.

Use this command to verify distribution:

```bash
for i in $(seq 1 30); do
  curl -s -I http://localhost:8080/api/notes | awk -F': ' '/X-Instance-ID/ {print $2}'
done | sort | uniq -c
```

Hints:
- First confirm scaling actually happened: run `docker compose ps` and verify that 3 `api` containers are `Up`.
- Compare your `frontend/nginx.conf` with the baseline and focus on the `upstream api_backend` block.
- Ask yourself: does nginx resolve `api` only once, or can it refresh DNS results over time?
- In the upstream config, investigate directives related to dynamic DNS updates (for example `resolver` and `resolve`).
- Keep `/api/` proxying simple while debugging. Change one thing at a time, then retest.
- After each nginx change, rebuild/restart frontend (`docker compose up -d --build frontend`) before measuring again.
- Re-run the 30-request check after every change and compare counts (`sort | uniq -c`) to see whether distribution improved.

Now simulate a configuration change (the equivalent of updating an environment variable in a cloud deployment). Stop all API instances and restart them with a new environment variable:

```bash
docker compose stop api
APP_VERSION=v2 docker compose up -d --scale api=3
```

Observe how quickly the new instances start and become available:

```bash
docker compose logs api --tail=20
```

---

### Reflection Questions — Part 2

> **Q2.1** Your 15 requests were distributed across 3 instances. Suppose each API instance stored the currently logged-in user's session (e.g., user ID, authentication token) in its own **local memory** — not in a shared external store. Sketch the following scenario and explain what goes wrong:
> - Request 1 (login): routed to Instance A → session created in Instance A's memory
> - Request 2 (get notes): routed to Instance B → what happens?
>
> What is the standard cloud-native solution to this problem, and which specific Azure service would you use?

> **Q2.2** After stopping and restarting the API instances, your notes were still available. Why? Which component holds the permanent state, and which component is stateless? Could you replace all three API instances with brand new containers right now without losing any data? Explain why or why not.

> **Q2.3** Each API instance started in under 3 seconds. The 12-factor principle IX (*Disposability*) states that processes should have fast startup and graceful shutdown. Why is this critical for horizontal auto-scaling in a cloud environment? What would happen if each instance took 3 minutes to start instead?

---

## Part 3 — Observing Partial Failure (15 min)

### Task

Simulate a database failure by stopping only the `db` container — leaving the `frontend` and `api` containers running:

```bash
docker compose stop db
```

Now try to use the application. First via the UI at [http://localhost:8080](http://localhost:8080), then directly via the API:

```bash
# This should fail — observe the response carefully
curl -v http://localhost:8080/api/notes

# Try to create a note
curl -v -X POST http://localhost:8080/api/notes \
  -H "Content-Type: application/json" \
  -d '{"text": "test note"}'
```

Note:
- How long does it take before you get a response?
- What HTTP status code is returned?
- Is the `api` container still running? (`docker compose ps`)
- Is the `frontend` still reachable? ([http://localhost:8080](http://localhost:8080))

Then restore the database and verify recovery:

```bash
docker compose start db
# Wait a few seconds, then:
curl http://localhost:8080/api/notes
```

---

### Reflection Questions — Part 3

> **Q3.1** When the database was stopped, the `api` container was still running and the `frontend` was still reachable — but the application could not serve data. This is a **partial failure**. How does this differ from a failure in a traditional single-server (centralized) application? Why is partial failure described in the lecture as one of the defining challenges of distributed systems?

> **Q3.2** From the client's perspective, when the API call to `/api/notes` failed, could you tell whether:
> - (a) The database container had crashed
> - (b) The network between `api` and `db` was broken
> - (c) The database was alive but slow to respond
>
> What mechanism eventually returned an error to you? Why is this mechanism inherently imprecise — what are its failure modes (false positives and false negatives)?

> **Q3.3** Imagine a user submits a new note at exactly the moment the database becomes unavailable. The `POST /api/notes` request times out after 5 seconds. The user sees an error and clicks "Save" again. What risk does this create? What property would the `POST` endpoint need to have to make it safe to retry, and how could you implement this in the API? (Hint: think about what information the client could send with the request.)

---

## 🔵 Optional Azure Extension Tasks

> These tasks are not required to complete the lab. They extend the local observations onto a real cloud platform. Complete them if you have activated your Azure for Students subscription.

### 🔵 Extension A — Deploy to Azure App Service

Deploy the same API to Azure App Service and observe the same stateless behavior in the cloud:

```bash
az login
az group create --name lab2-rg --location westeurope

# Deploy the API container image to App Service
az appservice plan create --name lab2-plan --resource-group lab2-rg \
  --is-linux --sku B1

az webapp create --name lab2-api-<yourname> --resource-group lab2-rg \
  --plan lab2-plan \
  --deployment-container-image-name ghcr.io/th-ulm-cloud/lab02-api:latest
```

Inspect the configuration:

```bash
az webapp config appsettings list \
  --name lab2-api-<yourname> --resource-group lab2-rg
```

> **🔵 Q-A1**: Where are the database connection settings stored in App Service? How does this compare to what you saw in the local `docker-compose.yml`? What would you need to change to point this deployment at a different database (e.g., Azure SQL instead of local PostgreSQL)?

### 🔵 Extension B — Observe Scaling in the Cloud

Scale out your App Service to 3 instances and observe the instance IDs:

```bash
az appservice plan update --name lab2-plan --resource-group lab2-rg \
  --number-of-workers 3

for i in $(seq 1 15); do
  curl -s -I https://lab2-api-<yourname>.azurewebsites.net/api/notes \
    | grep X-Instance-ID
done
```

> **🔵 Q-B1**: Do requests distribute across instances the same way they did locally? What does Azure use to distribute the load — and how does this compare to the nginx container acting as load balancer in the local setup?

### 🔵 Cleanup

Always delete your resources after the lab to avoid consuming credit:

```bash
az group delete --name lab2-rg --yes --no-wait
```

---

## Submission

Submit a **single PDF or Markdown document** containing:

1. Your answers to **Q1.1 through Q3.3** (all 9 questions)
2. The component diagram for Q1.1 (hand-drawn and photographed is fine)
3. The sketch for Q2.1

**Each written answer should be 3–8 sentences.** You are expected to use your own words — not copy from the lecture slides. AI tools (code assistants, documentation search) are permitted and encouraged for exploring commands and APIs, but reasoning and written answers must be your own.

**Optional**: Answers to 🔵 Extension questions if you completed them.

---


## Troubleshooting

**Docker Desktop not starting**: Make sure virtualization is enabled in BIOS. On Windows, WSL2 must be installed.

**Port 8080 or 5001 already in use**: Edit `docker-compose.yml` and change the host port mapping, e.g., `"8081:80"`.

**`curl` not available on Windows**: Use PowerShell's `Invoke-WebRequest` or install Git Bash. Alternatively, use the browser and browser DevTools (Network tab) for inspecting headers.

**Containers start but API returns 500**: The database may still be initializing. Wait 10 seconds and try again — PostgreSQL takes a few seconds to be ready on first start.

**Cannot pull images**: Ensure you are connected to the internet and Docker Desktop is running. Try `docker pull ghcr.io/th-ulm-cloud/lab02-api:latest` manually.
