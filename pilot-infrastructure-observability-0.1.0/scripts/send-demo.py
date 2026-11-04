"""Send clearly named synthetic machines to a running local pilot."""
import datetime, json, os, urllib.request, uuid
key = os.environ['PILOT_API_KEY']
for name, cpu, memory, disk, age in [('demo-api-01', 32, 48, 61, 0), ('demo-db-01', 52, 93, 75, 0), ('demo-worker-01', 22, 35, 40, 300)]:
    body = dict(schemaVersion=1, id=uuid.uuid4().hex, machineId=name, name=name, os='Synthetic demo — no real host', observedAt=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=age)).isoformat(), metrics=dict(cpuPercent=cpu, memoryPercent=memory, diskPercent=disk))
    req=urllib.request.Request('http://127.0.0.1:5080/api/v1/observations',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Pilot-Key':key})
    with urllib.request.urlopen(req,timeout=10) as response: print(name,response.read().decode())
