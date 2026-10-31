"""Independent institutional system: local SQLite inventory and FHIR R4 HTTP API.

No operational inventory is stored in the coordinating IRIS namespace.
"""
import os, sqlite3, json, threading, hmac, math, uuid
from datetime import timedelta
from pathlib import Path
from flask import Flask, request, jsonify
from hemoflow.common import now, stamp, date, require, Problem, COMPONENT, BLOOD, dumps,set_clock
from hemoflow.fhir import validate, parameter, parse_parameters
from hemoflow.products import validate_product

app = Flask(__name__)
CENTER = os.environ.get('CENTER_ID','HEMO-A')
DB = os.environ.get('CENTER_DB','/data/center.sqlite')
TOKEN = os.environ.get('CENTER_TOKEN','')
DEMO = os.environ.get('HEMOFLOW_DEMO')=='1'
Path(DB).parent.mkdir(parents=True,exist_ok=True)

def connection():
    db = sqlite3.connect(DB,timeout=10,isolation_level=None)
    db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS units(id TEXT PRIMARY KEY, expires TEXT NOT NULL,
        reserved INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'AVAILABLE');
        CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(id TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS seed_runs(id TEXT PRIMARY KEY,manifest TEXT);
        CREATE TABLE IF NOT EXISTS ownership(kind TEXT,id TEXT,run TEXT,PRIMARY KEY(kind,id));''')
    columns={r[1] for r in db.execute("PRAGMA table_info(units)")}
    if "blood_type" not in columns:
        try: db.execute("ALTER TABLE units ADD COLUMN blood_type TEXT NOT NULL DEFAULT 'O-'")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc): raise
    return db

def track(db,kind,key,run=None):
    owner=run or request.headers.get('X-Demo-Run')
    if owner:
        require(DEMO and db.execute('SELECT 1 FROM seed_runs WHERE id=?',(owner,)).fetchone(),'Unknown demonstration owner',403)
        db.execute('INSERT OR IGNORE INTO ownership VALUES(?,?,?)',(kind,key,owner))

def clock_offset():
    try:
        with sqlite3.connect(DB) as db:
            row=db.execute("SELECT value FROM settings WHERE id='clock_offset'").fetchone()
            return float(row[0]) if row else 0
    except sqlite3.OperationalError:return 0
if DEMO:set_clock(clock_offset)

def setting(db,key,default):
    r=db.execute('SELECT value FROM settings WHERE id=?',(key,)).fetchone()
    return r[0] if r else default

def inventory(db,blood_type=BLOOD):
    rows=db.execute("SELECT * FROM units WHERE state='AVAILABLE' AND reserved=0 AND blocked=0 AND expires>? AND blood_type=? ORDER BY expires,id",(stamp(),blood_type)).fetchall()
    reserve=int(setting(db,'reserve','4'))
    transferable=rows[:max(0,len(rows)-reserve)]
    buckets={}
    for row in transferable: buckets[row['expires']]=buckets.get(row['expires'],0)+1
    version=str(db.execute("SELECT COUNT(*) FROM commands").fetchone()[0])+':'+str(len(rows))
    parts=[parameter('centerId','String',CENTER),parameter('componentCode','Code',COMPONENT),
        parameter('bloodType','Code',blood_type),parameter('availableUnits','Integer',len(rows)),
        parameter('transferableUnits','Integer',len(transferable)),parameter('observedAt','Instant',stamp()),
        parameter('dataVersion','String',version),parameter('responseStatus','Code','AVAILABLE'),
        parameter('handlingLeadTimeHours','Integer',int(setting(db,'lead_hours','4')))]
    for expiry,count in buckets.items():
        parts.append({'name':'expiryBucket','part':[parameter('expiresAt','DateTime',expiry),
            parameter('daysUntilExpiry','Integer',max(0,(date(expiry)-now()).days)),parameter('units','Integer',count)]})
    usable={}
    for row in rows: usable[row['expires']]=usable.get(row['expires'],0)+1
    for expiry,count in usable.items():
        parts.append({'name':'usableExpiryBucket','part':[parameter('expiresAt','DateTime',expiry),parameter('units','Integer',count)]})
    return validate({'resourceType':'Parameters','parameter':parts})

@app.before_request
def authenticate():
    if request.path=='/health': return
    require(bool(TOKEN) and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+TOKEN),'Unauthorized',401)

@app.errorhandler(Problem)
def problem(exc): return jsonify(error=exc.message),exc.status

@app.get('/health')
def health(): return jsonify(center_id=CENTER,status='ok')

@app.get('/fhir/Organization/<identity>')
def organization(identity):
    require(identity==CENTER,'Unknown organization',404)
    return jsonify(validate({'resourceType':'Organization','id':CENTER,'active':True,'name':CENTER}))

@app.post('/fhir/$inventory-availability')
def availability():
    p=parse_parameters(request.get_json())
    blood_type=validate_product(p.get('bloodType'),p.get('componentCode'))
    require(p.get('requestingCenterId') in ('HEMO-A','HEMO-B','HEMO-C') and p.get('horizonDays')==7,'Invalid request scope or horizon')
    date(p['needBy'])
    with connection() as db:
        require(setting(db,'offline','0')!='1','Remote temporarily unavailable',503)
        return jsonify(inventory(db,blood_type))

@app.post('/fhir/SupplyRequest')
def reserve():
    resource=validate(request.get_json())
    key=resource['id']
    codes=resource.get('itemCodeableConcept',{}).get('coding',[])
    blood_type=validate_product(next((c['code'] for c in codes if c.get('system')=='urn:hemoflow:blood-type'),BLOOD))
    require(any(c.get('system')=='urn:hemoflow:component' and c.get('code')==COMPONENT for c in codes),'Unsupported component')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM commands WHERE id=?',(key,)).fetchone()
        if old:
            original=db.execute('SELECT payload FROM resources WHERE id=?',(key,)).fetchone()
            require(original and json.loads(original[0])==resource,'Idempotency key reused with different supply request',409)
            return jsonify(json.loads(old[0]))
        require(setting(db,'decline','0')!='1','Source declined request',409)
        count=resource['quantity']['value']
        require(type(count) is int and count>0,'Invalid quantity')
        need=date(resource['occurrenceDateTime'])
        arrival=now()+timedelta(hours=int(setting(db,'lead_hours','4')))
        require(arrival<=need,'Delivery deadline infeasible',409)
        # Destination must use units after arrival; application sends latest required use time.
        latest_use=stamp(arrival+timedelta(days=1))
        daily=float(request.headers.get('X-Daily-Use','100'))
        require(math.isfinite(daily) and 0<daily<=100,'Invalid destination consumption capacity')
        eligible=db.execute("SELECT id,expires,blood_type FROM units WHERE reserved=0 AND blocked=0 AND state='AVAILABLE' AND expires>? AND blood_type=? ORDER BY expires,id",(latest_use,blood_type)).fetchall()
        rows=[]
        for row in eligible:
            days=max(0,min(7,(date(row['expires'])-arrival).total_seconds()/86400-1))
            if len(rows)<math.floor(days*daily):rows.append(row)
        total=db.execute("SELECT COUNT(*) FROM units WHERE reserved=0 AND blocked=0 AND state='AVAILABLE' AND expires>? AND blood_type=?",(stamp(),blood_type)).fetchone()[0]
        require(count<=len(rows) and total-count>=int(setting(db,'reserve','4')),'Availability changed',409)
        selected=[dict(r) for r in rows[:count]]
        for row in selected: db.execute('UPDATE units SET reserved=1 WHERE id=?',(row['id'],))
        result={'resourceType':'Parameters','parameter':[parameter('transferId','String',key),parameter('reservedUnits','Integer',count)]}
        db.execute('INSERT INTO commands VALUES(?,?)',(key,dumps(result)))
        db.execute('INSERT INTO resources VALUES(?,?)',(key,dumps(resource)))
        db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value',('allocation:'+key,dumps(selected)))
        track(db,'commands',key);track(db,'resources',key);track(db,'settings','allocation:'+key)
        db.commit()
        return jsonify(result)

@app.post('/transfers/<key>/dispatch')
def dispatch(key):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        allocation=json.loads(setting(db,'allocation:'+key,'[]'))
        require(allocation,'Reservation missing',409)
        for row in allocation:
            require(date(row['expires'])>now()+timedelta(hours=int(setting(db,'lead_hours','4'))),'Reserved stock expired',409)
        for row in allocation: db.execute("UPDATE units SET state='SHIPPED' WHERE id=? AND reserved=1",(row['id'],))
        db.commit()
        return jsonify(transfer_id=key,units=allocation,dispatched_at=stamp(),source_center_id=CENTER)

@app.post('/transfers/<key>/receive')
def receive(key):
    p=request.get_json()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM commands WHERE id=?',('receive:'+key,)).fetchone()
        if old: return jsonify(json.loads(old[0]))
        for row in p['units']:
            require(date(row['expires'])>now(),'Expired shipment',409)
            validate_product(row.get('blood_type',BLOOD))
            db.execute('INSERT INTO units(id,expires,blood_type) VALUES(?,?,?)',('received:'+key+':'+row['id'],row['expires'],row.get('blood_type',BLOOD)))
            track(db,'units','received:'+key+':'+row['id'])
        result={'received_units':len(p['units']),'received_at':stamp()}
        db.execute('INSERT INTO commands VALUES(?,?)',('receive:'+key,dumps(result)))
        track(db,'commands','receive:'+key)
        db.commit()
        return jsonify(result)

@app.post('/campaigns/<key>/release')
def release(key):
    p=request.get_json()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM commands WHERE id=?',('release:'+key,)).fetchone()
        if old: return jsonify(json.loads(old[0]))
        blood_type=validate_product(p.get('blood_type',BLOOD))
        count=p['released_units']
        require(type(count) is int and count>=0,'Invalid released units')
        for i in range(count):
            identity=f'campaign:{key}:{i}'
            db.execute('INSERT INTO units(id,expires,blood_type) VALUES(?,?,?)',(identity,p['expires_at'],blood_type))
            track(db,'units',identity)
        result={'released_units':count}
        db.execute('INSERT INTO commands VALUES(?,?)',('release:'+key,dumps(result)))
        track(db,'commands','release:'+key)
        db.commit()
        return jsonify(result)

@app.get('/fhir/<kind>/<key>')
def resource(kind,key):
    with connection() as db:
        row=db.execute('SELECT payload FROM resources WHERE id=?',(key,)).fetchone()
        require(row is not None,'Not found',404)
        return jsonify(json.loads(row[0]))

@app.post('/fhir/SupplyDelivery')
def delivery_resource():
    resource=validate(request.get_json());require(resource['resourceType']=='SupplyDelivery' and resource['status']=='completed','Expected completed SupplyDelivery')
    transfer_id=resource['basedOn'][0]['reference'].split('/')[-1]
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        receipt=db.execute('SELECT payload FROM commands WHERE id=?',('receive:'+transfer_id,)).fetchone()
        require(receipt is not None,'A FHIR resource alone is not confirmation of receipt',409)
        received=json.loads(receipt[0])['received_units']
        require(resource['suppliedItem']['quantity']['value']==received,'Receipt quantity mismatch',409)
        old=db.execute('SELECT payload FROM resources WHERE id=?',(resource['id'],)).fetchone()
        if old:
            require(json.loads(old[0])==resource,'Delivery resource conflict',409)
        else:
            db.execute('INSERT INTO resources VALUES(?,?)',(resource['id'],dumps(resource)));track(db,'resources',resource['id'])
        db.commit()
        return jsonify(resource)

@app.get('/fhir/OperationDefinition/inventory-availability')
def operation_definition():
    return jsonify(validate(json.loads((Path(__file__).parent/'inventory-availability.json').read_text())))

def demo_guard(payload):
    require(DEMO,'Demonstration maintenance disabled',403)
    require(payload.get('run_id')=='hemoflow-demo-v1','Unknown demonstration run',403)

def foreign_rows(db):
    return any(db.execute('SELECT 1 FROM '+kind+' t WHERE NOT EXISTS(SELECT 1 FROM ownership o WHERE o.kind=? AND o.id=t.id) LIMIT 1',(kind,)).fetchone()
               for kind in ('units','commands','resources','settings'))

def insert_demo(db,manifest):
    run=manifest['run_id']
    for unit in manifest['units']:
        date(unit['expires'])
        require(unit['id'].startswith('DEMO-'),'Invalid seed unit ID')
        db.execute('INSERT INTO units(id,expires,reserved,blocked,blood_type) VALUES(?,?,?,?,?)',
            (unit['id'],unit['expires'],unit.get('reserved',0),unit.get('blocked',0),validate_product(unit.get('blood_type',BLOOD))))
        track(db,'units',unit['id'],run)
    for key,value in manifest['settings'].items():
        db.execute('INSERT INTO settings VALUES(?,?)',(key,str(value)));track(db,'settings',key,run)

@app.post('/demo/seed')
def seed():
    payload=request.get_json();demo_guard(payload)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT manifest FROM seed_runs WHERE id=?',(payload['run_id'],)).fetchone()
        if old:return jsonify(status='ALREADY_LOADED',center_id=CENTER)
        require(not foreign_rows(db),'Existing institution data: seed refused without overwrite',409)
        db.execute('INSERT INTO seed_runs VALUES(?,?)',(payload['run_id'],dumps(payload)))
        insert_demo(db,payload);db.commit()
        return jsonify(status='LOADED',center_id=CENTER,units=len(payload['units']))

@app.post('/demo/restore')
def restore():
    payload=request.get_json();demo_guard(payload)
    with connection() as db:
        record=db.execute('SELECT manifest FROM seed_runs WHERE id=?',(payload['run_id'],)).fetchone()
        require(record is not None,'Seed not installed',409)
        require(not foreign_rows(db),'Non-demo data present: restore refused',409)
        backup_dir=Path(DB).parent/'snapshots';backup_dir.mkdir(exist_ok=True)
        backup_name=payload['run_id']+'-'+uuid.uuid4().hex+'.sqlite'
        destination=sqlite3.connect(str(backup_dir/backup_name))
        db.backup(destination);destination.close()
        db.execute('BEGIN IMMEDIATE')
        require(not foreign_rows(db),'Institution changed during restore',409)
        for kind in ('units','commands','resources','settings'):
            db.execute('DELETE FROM '+kind+' WHERE id IN (SELECT id FROM ownership WHERE kind=? AND run=?)',(kind,payload['run_id']))
        db.execute('DELETE FROM ownership WHERE run=?',(payload['run_id'],))
        manifest=payload.get('manifest') or json.loads(record[0])
        require(manifest['run_id']==payload['run_id'],'Manifest owner mismatch',403)
        insert_demo(db,manifest);db.commit()
        return jsonify(status='RESTORED',center_id=CENTER,backup=backup_name)

@app.post('/demo/status')
def demo_status():
    payload=request.get_json();demo_guard(payload)
    with connection() as db:
        return jsonify(safe_to_restore=not foreign_rows(db),seeded=bool(db.execute('SELECT 1 FROM seed_runs WHERE id=?',(payload['run_id'],)).fetchone()))

@app.post('/demo/extend')
def extend_demo():
    payload=request.get_json();demo_guard(payload)
    marker=payload['run_id']+':multitype-v2'
    with connection() as db:
        require(db.execute('SELECT 1 FROM seed_runs WHERE id=?',(payload['run_id'],)).fetchone(),'Seed missing',409)
        if db.execute('SELECT 1 FROM seed_runs WHERE id=?',(marker,)).fetchone():return jsonify(status='ALREADY_LOADED')
        require(not foreign_rows(db),'Non-demo data prevents seed extension',409)
        backup_dir=Path(DB).parent/'snapshots';backup_dir.mkdir(exist_ok=True)
        backup=backup_dir/('multitype-v2-'+uuid.uuid4().hex+'.sqlite')
        destination=sqlite3.connect(str(backup));db.backup(destination);destination.close()
        db.execute('BEGIN IMMEDIATE')
        require(not foreign_rows(db),'Institution changed during extension',409)
        count=0
        for unit in payload['units']:
            group=validate_product(unit.get('blood_type',BLOOD));date(unit['expires'])
            require(unit['id'].startswith('DEMO-'),'Invalid seed identity')
            if group==BLOOD or db.execute('SELECT 1 FROM units WHERE id=?',(unit['id'],)).fetchone():continue
            db.execute('INSERT INTO units(id,expires,reserved,blocked,blood_type) VALUES(?,?,?,?,?)',
                (unit['id'],unit['expires'],unit.get('reserved',0),unit.get('blocked',0),group))
            track(db,'units',unit['id'],payload['run_id']);count+=1
        db.execute('INSERT INTO seed_runs VALUES(?,?)',(marker,dumps(dict(backup=str(backup),added=count))))
        db.commit()
        return jsonify(status='EXTENDED',added=count,backup=backup.name)

@app.post('/demo/clock')
def advance_clock():
    payload=request.get_json();demo_guard(payload)
    offset=payload['offset_seconds']
    require(type(offset) in (int,float) and 0<=offset<=30*86400,'Simulation clock limit exceeded')
    with connection() as db:
        require(db.execute('SELECT 1 FROM seed_runs WHERE id=?',(payload['run_id'],)).fetchone(),'Seed missing',409)
        db.execute("INSERT INTO settings VALUES('clock_offset',?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",(str(offset),))
        track(db,'settings','clock_offset',payload['run_id'])
    return jsonify(status='CLOCK_SET',offset_seconds=offset)

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','8080')),threaded=True)
