# LivingADR — Local Run Guide

On this machine the one-time setup is **already done** (GitHub App, `.env`,
`living-adr.config.yaml`, `secrets/`, the Dev Tunnel, and the MCP registration).
To run the loop you just start two processes.

> New machine? Jump to [First-time setup](#first-time-setup-new-machine).

---

## Run it

Start both the receiver and the tunnel with **one command**:

```powershell
cd C:\repos\living-adr
.\scripts\start-all.ps1
```

This opens the **receiver** and the **tunnel** each in its own window (add
`-Detached` to run them hidden, logging to `var\*.log`). It is idempotent — it
skips whichever piece is already running and reports the receiver's health.

The tunnel window prints its public origin (look for **`Connect via browser`**).
If that origin differs from the one set in the GitHub App, update the App's
**Webhook URL** to `<origin>/webhooks/github`.

> Prefer two terminals you control directly? Run `scripts\run-workflow.ps1`
> (receiver) and `scripts\run-tunnel.ps1` (tunnel) separately instead.

---

## Verify

```powershell
# Local
(Invoke-WebRequest http://127.0.0.1:8000/healthz -UseBasicParsing).Content
# Public (substitute the current tunnel origin)
(Invoke-WebRequest https://<id>-8000.<cluster>.devtunnels.ms/healthz -UseBasicParsing).Content
```

Both should return `{"status":"ok"}`.

---

## Use it

1. **Merge a PR** on the tracked repo (`Sidsol/living-adr`).
2. If the change is architecture-significant, a draft is generated and pauses at
   the human-review gate.
3. **Approve** it in the review UI (send the `X-UI-Token` header):
   `GET http://127.0.0.1:8000/hitl/reviews/{thread_id}` with
   `X-UI-Token: <LIVING_ADR_UI_TOKEN>`.
4. On approve → the ADR is written to the graph and a **publish-back PR** is opened
   on the repo.
5. Query approved decisions via the `living-adr` MCP tools (`list_adrs`,
   `answer_why`, `fetch_adr`).

---

## Stop / restart

- **Stop:** `Ctrl-C` in each terminal (or `Stop-Process -Id <PID> -Force`).
- **After editing `.env` or `living-adr.config.yaml`:** restart **both**
  processes — there is no hot reload. Restart your MCP host (IDE/CLI) after
  editing `~/.copilot/mcp-config.json`.

---

## Already configured on this machine

| Item | Location |
|---|---|
| Repo + dependencies | `C:\repos\living-adr` (`uv sync` done, `.venv` present) |
| Secrets / env | `.env` (config path, webhook secret, storage path, App ID, key path, Anthropic key, UI token) |
| Tracked-repo config | `living-adr.config.yaml` (tracks `Sidsol/living-adr`) |
| GitHub App private key | `secrets\github-app-private-key.pem` (gitignored) |
| GitHub App | registered + installed; **Webhook URL** points at the tunnel |
| Public tunnel | `devtunnel` tunnel `living-adr` (port 8000) |
| MCP registration | `~/.copilot/mcp-config.json` (`LIVING_ADR_CONFIG` + `LIVING_ADR_STORAGE_PATH`) |

---

## Troubleshooting (quick)

| Symptom | Fix |
|---|---|
| `GITHUB_WEBHOOK_SECRET is required...` | Start via `scripts\run-workflow.ps1` (it loads `.env`) |
| `uv` can't remove `living-adr-mcp.exe` | Stop the running MCP server (by PID), then retry |
| Public URL not reachable | Re-host the tunnel; set the App **Webhook URL** to the current origin + `/webhooks/github` |
| MCP returns no ADRs | Both deployables must share the same `LIVING_ADR_STORAGE_PATH`; restart the MCP host |
| Config/`.env` change ignored | Restart the affected process (no hot reload) |

---

## First-time setup (new machine)

Only needed on a machine where the table above is **not** yet true. Condensed
checklist — see `README.md` (*Configuration*, *GitHub App setup*, *Exposing the
receiver*) for full detail.

1. **Install:** `git clone … && cd living-adr && uv sync` (then `uv run pytest` to
   verify).
2. **GitHub App:** create + install on the repo with *Contents* R&W, *Pull
   requests* R&W, *Metadata* read; subscribe to **Pull request**. Note the **App
   ID**, download the **`.pem`** to `secrets\github-app-private-key.pem`, and note
   the **installation id**.
3. **`.env`:** `Copy-Item .env.example .env` and fill in `LIVING_ADR_CONFIG`,
   `GITHUB_WEBHOOK_SECRET`, `LIVING_ADR_STORAGE_PATH`, `GITHUB_APP_ID`,
   `GITHUB_APP_PRIVATE_KEY_PATH`, `ANTHROPIC_API_KEY`, `LIVING_ADR_UI_TOKEN`.
   Generate secrets/tokens with:
   `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
4. **`living-adr.config.yaml`:** set the repo identity (`host`/`owner`/`repo`/
   `repo_id`), `github_app_installation_id`, `default_branch`,
   `adr_publication_policy: publish_to_github_and_livingadr`, `adr_target_branch`,
   `adr_path_template`, `external_llm_allowed: true`.
5. **Tunnel (one-time):** `winget install Microsoft.devtunnel`; `devtunnel user
   login`; `devtunnel create living-adr --allow-anonymous`; `devtunnel port create
   living-adr -p 8000 --protocol http`. Then run the tunnel and set the App
   **Webhook URL** = `<tunnel origin>/webhooks/github` with the matching secret.
6. **MCP:** add `living-adr` to `~/.copilot/mcp-config.json` with `LIVING_ADR_CONFIG`
   and the **same** `LIVING_ADR_STORAGE_PATH`.
7. **Validate:** load `.env`, then
   `uv run living-adr onboard validate --config living-adr.config.yaml`.

Then return to [Run it](#run-it).
