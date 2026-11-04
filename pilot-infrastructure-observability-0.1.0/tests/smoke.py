"""Black-box API checks; starts an isolated process and temporary data directory."""
import datetime as dt, json, os, pathlib, subprocess, tempfile, time, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
KEY='test-key-for-local-smoke-checks-only'
DOTNET=os.environ.get('DOTNET','dotnet')
def request(path, body=None, key=KEY):
    req=urllib.request.Request('http://127.0.0.1:5080'+path,data=None if body is None else json.dumps(body).encode(),headers={'X-Pilot-Key':key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=5) as r: return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:
        data=e.read(); return e.code,json.loads(data) if data else None

def payload(id='a',machine='host',age=0,metrics=None):
    return dict(schemaVersion=1,id=id,machineId=machine,name=machine,os='test',observedAt=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=age)).isoformat(),metrics=metrics if metrics is not None else dict(cpuPercent=20,memoryPercent=30,diskPercent=40))
with tempfile.TemporaryDirectory() as data, tempfile.TemporaryFile() as logs:
    env=dict(os.environ,PILOT_API_KEY=KEY,PILOT_DATA_DIR=data)
    def start():
        p=subprocess.Popen([DOTNET,'run','--no-build','--project',str(ROOT/'src/Pilot.Api')],env=env,stdout=logs,stderr=logs)
        for _ in range(100):
            if p.poll() is not None: logs.seek(0); raise RuntimeError(logs.read().decode())
            try:
                if request('/healthz')[0]==200:return p
            except OSError: pass
            time.sleep(.1)
        p.terminate();p.wait();raise RuntimeError('API failed to start')
    p=start()
    try:
        assert request('/api/v1/machines',key='wrong')[0]==401
        a=payload(); assert request('/api/v1/observations',a)==(200,{'status':'accepted'})
        assert request('/api/v1/observations',a)==(200,{'status':'duplicate'})
        a['name']='changed'; assert request('/api/v1/observations',a)[0]==409
        assert request('/api/v1/observations',payload('old',age=10))[1]['status']=='outOfOrder'
        assert request('/api/v1/observations',payload('bad',metrics={'cpuPercent':101}))[0]==400
        assert request('/api/v1/observations',payload('future',age=-300))[0]==400
        assert request('/api/v1/observations',payload('stale','stale-host',age=300))[0]==200
        assert request('/api/v1/observations',payload('partial','partial-host',metrics={'cpuPercent':10}))[0]==200
        assert request('/api/v1/observations',payload('hot','host',metrics={'cpuPercent':95,'memoryPercent':20,'diskPercent':40}))[0]==200
        rows=request('/api/v1/machines')[1]; health={r['machine']['id']:r['health'] for r in rows}
        assert health=={'host':'critical','stale-host':'stale','partial-host':'unknown'},health
        events=request('/api/v1/events')[1]; assert any(e['kind']=='healthChanged' and e['observationId']=='hot' for e in events)
        p.terminate();p.wait(timeout=10);p=start()
        assert len(request('/api/v1/machines')[1])==3
        assert request('/api/v1/events')[1]==events
        print('PASS: auth, ingestion, duplicate, conflict, ordering, range, future clock, stale, partial coverage, health transition, evidence and restart persistence')
    finally:
        p.terminate();p.wait(timeout=10)
