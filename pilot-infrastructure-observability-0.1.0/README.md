# Infrastructure Observability Pilot — 0.1.0

First bottom-up development slice for .NET software teams: machine inventory, CPU/memory/disk observations, freshness-aware health and evidence timeline. Separate from distributed-consensus-lab; no remote repository modifications.

## Run

Requires .NET 10 SDK. The Windows launch example uses PowerShell 7+. No third-party NuGet dependencies. From this directory:

```powershell
$env:PILOT_API_KEY = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
dotnet run --project src/Pilot.Api
```

Open http://127.0.0.1:5080 and enter that key. Keep the key out of source control. In another terminal set the SAME PILOT_API_KEY and run:

```powershell
./scripts/collect-windows.ps1 -Once
# Omit -Once to collect every 15 seconds.
```

Linux/macOS launch:

```bash
export PILOT_API_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
dotnet run --project src/Pilot.Api
```

Synthetic demo, with the same key in its terminal:

```bash
python3 scripts/send-demo.py
```

All demo machines are explicitly labeled synthetic. There is no automatic fake-data seeding.

## Validate

Stop other pilot processes on port 5080, then:

```bash
dotnet build src/Pilot.Api
python3 tests/smoke.py
```

Set DOTNET to the absolute executable path if needed. The smoke suite starts its own API with isolated temporary storage.

## Contract

POST /api/v1/observations (X-Pilot-Key header required):

```json
{"schemaVersion":1,"id":"unique-observation-id","machineId":"stable-host-id","name":"api-01","os":"Windows Server","observedAt":"2026-11-05T00:00:00Z","metrics":{"cpuPercent":35,"memoryPercent":62,"diskPercent":48}}
```

Use the actual UTC timestamp. Accepted window: last 24 hours, up to two minutes future skew. IDs: ASCII letters/digits/underscore/hyphen, max 100 characters. Metrics: only these three percentage names, 0–100. GET /api/v1/machines returns health and missing coverage; GET /api/v1/events returns latest 200 discovery/health-change events. /healthz is public liveness/readiness for the local process.

Health rule v1: observed age >120 seconds is stale; any metric >=90 critical, >=80 warning; otherwise fewer than three metrics is unknown, else healthy. Healthy only means these resource-pressure checks passed; it does not establish application health. Timestamp is collector supplied; receivedAt is recorded separately.

## Limits and implementation decisions

- Local-only preview bound to 127.0.0.1:5080. Single operator, shared key, no remote deployment or multi-tenancy yet. UI key stays in memory; no browser persistence.
- Supported inventory cap is 100, a safety bound rather than benchmarked capacity. Begin with 3–10 machines.
- Atomic snapshot replacement serializes writes within one process. Not a transactional database or power-loss durability guarantee. Default storage: src/Pilot.Api/data/pilot.json; PILOT_DATA_DIR overrides it. Do not run two instances on the same directory. Back up while stopped.
- Deduplication covers last 1,000 accepted observation IDs. Same ID with different content returns 409. Older/equal observations do not overwrite latest state. At most 2,000 evidence records retained.
- Staleness is computed on query. A host becoming stale does not yet emit a background event. Notification delivery is not implemented.
- Windows collector uses CIM and MachineGuid; CPU is processor load average, disk is system volume only. It is not a complete hardware inventory. No durable offline queue yet. A collection/transmission failure is reported, never converted to a zero reading.
- API and UI are real implementations; the Windows collector requires validation on Windows. IIS, SQL Server, traces, dependency graph and automatic root cause analysis are future work.
- Plain HTML/CSS/JS is used for this first screen to avoid frontend build dependencies; React migration is planned when investigation views expand.

See docs/BACKLOG.md and docs/VALIDATION.md for next steps and actual validation evidence.
