# Harvester Operational Runbook

Common operations and failure recovery for the Harvester service.

---

## Starting and Stopping

```bash
./start.sh   # background launch, confirms /healthz
./stop.sh    # graceful shutdown
```

Logs stream to `data/logs/harvester.log`.

---

## Webhook Setup (One-Time — Cloudflare Tunnel)

Harvester receives GitHub webhooks at `POST /webhook`. Because it runs on your Mac Mini behind a home router, it must be exposed via Cloudflare Tunnel. This is a one-time configuration — not automated by Harvester.

### 1. Add a Harvester route to the existing tunnel config

The LAN-Central-Command Cloudflare tunnel config lives at:
```
~/Atlas/LAN-Central-Command/sysadmin-infrastructure/cloudflare-tunnel/
```

Add an ingress rule that maps a hostname to `localhost:8500`:

```yaml
ingress:
  - hostname: harvester.yourdomain.com
    service: http://localhost:8500
  # ... existing rules ...
  - service: http_status:404
```

Reload the tunnel after editing the config.

### 2. Configure the GitHub webhook on each watched repo

For each repo under Harvester's watch (starting with `hackstert/ezra-assistant`):

1. Go to **Settings → Webhooks → Add webhook**
2. **Payload URL:** `https://harvester.yourdomain.com/webhook`
3. **Content type:** `application/json`
4. **Secret:** the value of `GITHUB_WEBHOOK_SECRET` in your `.env`
5. **Which events?** Select individual events:
   - Issues
   - Pull requests
6. Ensure **Active** is checked
7. Click **Add webhook**

GitHub will send a `ping` event immediately. Check `data/logs/harvester.log` for:
```
Webhook received: event=ping action= delivery=<id>
```

### 3. Verify with Redeliver

After the webhook is active, use GitHub's **Redeliver** button on any event to test the round-trip without needing new activity on the repo.

---

## Adding a New Repo to Harvester

See `docs/onboarding-guide.md` for the full assessment process.

Quick checklist:
1. Run through the 5-phase onboarding guide to confirm the repo is suitable
2. Add an entry to `harvester-config.yaml` (validate with `python -m harvester validate`)
3. Ensure the fine-grained GitHub PAT has **Issues** and **Pull requests** write scope on the new repo
4. Configure a webhook on the new repo (see above)
5. Restart Harvester — label taxonomy auto-creates on startup

---

## Checking Queue State

```bash
python -m harvester queue list
```

Or inspect the directories directly:
```bash
ls data/queue/pending/
ls data/queue/failed/
```

---

## Failure Recovery

### Service not starting

Check `data/logs/harvester.log` for the error. Common causes:
- `harvester-config.yaml` malformed — run `python -m harvester validate`
- Missing env vars — confirm `.env` is populated from `.env.example`
- Port 8500 already in use — `lsof -ti:8500`

### Stale PID file

If `./start.sh` reports "already running" but the process is dead:
```bash
rm harvester.pid
./start.sh
```

### Agent run workspace contaminated

If a previous overnight run left a workspace dirty, the agent-runner.sh pre-flight handles cleanup with `git reset --hard origin/main`. No manual action needed unless the reset itself fails.

### Failed queue items

Items in `data/queue/failed/` have a `failure_reason` field in their JSON. Review, fix the underlying issue, and either:
- Move the file back to `data/queue/pending/` to retry, or
- Delete it and re-apply the `agent-ready` label on the GitHub issue to re-enqueue

---

## Label Taxonomy

Harvester auto-creates these labels on startup for every configured repo. Do not delete them manually — they will be recreated.

| Label | Purpose |
|---|---|
| `improvement` | All Harvester-generated issues |
| `priority:must-have` / `should-have` / `nice-to-have` | Triage priority |
| `status:triage` | Awaiting human review |
| `status:blocked` | Blocked, see issue comment |
| `agent-ready` | Approved for overnight run |
| `scanner:<name>` | Which scanner produced the finding |
| `domain:<value>` | Finding domain (code-health, memory, etc.) |
| `theological-review-required` | Selah only — requires manual review |
