"""Five SSR screens, served by %SYS.Python.WSGI inside IRIS."""
import secrets, uuid, json
from datetime import timedelta
from flask import Flask, request, session, redirect, url_for, render_template, jsonify, g, flash
from werkzeug.security import check_password_hash
from .common import ROOT, Problem, require, stamp, now
from .settings import setting, demo
from . import repository as repo, federation, ttl
from .ui import t, label, display_name
from .analytics import visible
from .products import BLOOD_TYPES,validate_product
from .common import enable_iris_demo_clock
enable_iris_demo_clock()

app=Flask(__name__,template_folder=str(ROOT/'web/templates'),static_folder=str(ROOT/'web/static'))
app.secret_key=setting('HEMOFLOW_SESSION_SECRET')
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
                  SESSION_COOKIE_SECURE=not demo(),MAX_CONTENT_LENGTH=65536,
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=4))
PAGES={key:(t('nav.'+key),path) for key,path in [('panel','/dashboard'),('network','/blood-center-network'),
       ('transfers','/blood-transfers'),('campaigns','/donation-campaigns'),('audit','/audit-analytics')]}
app.jinja_env.globals['t']=t
app.jinja_env.filters.update(label=label,display_name=display_name)

@app.before_request
def authenticate():
    session.setdefault('csrf',secrets.token_urlsafe(32))
    if request.endpoint in ('login','static','health'): return
    identity=session.get('user_id')
    if not identity:
        if request.path.startswith('/api/'): raise Problem(401,'Authentication required')
        return redirect(url_for('login'))
    import iris
    g.user=json.loads(iris.cls('HemoFlow.Authentication').PublicUser(identity))
    require(g.user,'Account no longer available',401)
    if request.method not in ('GET','HEAD','OPTIONS'):
        require(secrets.compare_digest(request.headers.get('X-CSRF-Token',request.form.get('csrf','')),session['csrf']),'Invalid CSRF token',403)

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
    response.headers['Cache-Control']='no-store'
    return response

@app.errorhandler(Problem)
def problem(exc):
    if request.path.startswith('/api/'): return jsonify(error=exc.message),exc.status
    return render_template('error.html',error=exc.message,status=exc.status),exc.status

@app.get('/health')
def health(): return jsonify(status='ok',runtime='Embedded Python / IRIS WSGI')

@app.route('/login',methods=['GET','POST'])
def login():
    error=None
    if request.method=='POST':
        require(secrets.compare_digest(request.form.get('csrf',''),session['csrf']),'Invalid CSRF token',403)
        import iris
        user=json.loads(iris.cls('HemoFlow.Authentication').Login(request.form.get('username',''),request.form.get('password','')))
        if user:
            session.clear(); session.update(user_id=user['id'],csrf=secrets.token_urlsafe(32)); session.permanent=True
            return redirect(url_for('panel'))
        error=t('invalid_login')
    return render_template('login.html',error=error,csrf=session['csrf'],demo=demo())

@app.post('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

def scoped(kind):
    if kind=='InvitationLedger' and g.user['role']=='manager':
        return [r for r in repo.all(kind) if r.get('center_id')==g.user['scope']]
    if kind=='Transfer' and g.user['role']=='manager':
        return [r for r in repo.all(kind) if g.user['scope'] in (r['source_center_id'],r['target_center_id'])]
    if kind=='Campaign' and g.user['role'] in ('partner','donor'):
        ids={r['campaign_id'] for r in repo.all('InvitationLedger',scope=g.user['scope'])}
        return [r for r in repo.all(kind) if r['id'] in ids]
    return repo.all(kind,scope=None if g.user['role'] in ('admin','auditor') else g.user['scope'])

def screen(page):
    context=dict(page=page,pages=PAGES,title=PAGES[page][0],user=g.user,csrf=session['csrf'],demo=demo(),now=stamp(),blood_types=BLOOD_TYPES,
                 token_configured=bool(setting('OPENAI_API_KEY')))
    context.update(centers=repo.all('NetworkCenter'),partners=repo.all('Partner'),
        transfers=scoped('Transfer'),campaigns=scoped('Campaign'),decisions=scoped('DecisionAudit'),
        invitations=scoped('InvitationLedger'),pending=ttl.pending(None if g.user['role']=='admin' else g.user['scope']),
        events=repo.all('EventAudit') if g.user['role'] in ('admin','auditor') else [],ttl=repo.config('invite_ttl_hours',24),
        forecast_model=repo.config('forecast_model'),demo_runs=repo.all('DemoRun') if demo() else [])
    demo_centers={r['id'] for r in context['centers'] if r.get('demo_run_id')}
    if g.user['role']=='manager':context['pending']=[r for r in ttl.pending() if r.get('center_id')==g.user['scope']]
    for key in ('centers','partners','transfers','campaigns','decisions','invitations','pending','events'):
        context[key]=visible(context[key],demo_centers)
    if not demo():
        context['events']=[r for r in context['events'] if not r.get('event','').startswith('DEMO_') and r.get('correlation_id') not in {d['id'] for d in repo.all('DecisionAudit') if d.get('scope') in demo_centers}]
        if demo_centers: context['forecast_model']=None
    context['live_network']=[]
    return render_template(page+'.html',**context)

@app.get('/dashboard')
def panel(): return screen('panel')
@app.get('/blood-center-network')
def network(): return screen('network')
@app.get('/blood-transfers')
def transfers(): return screen('transfers')
@app.get('/donation-campaigns')
def campaigns(): return screen('campaigns')
@app.get('/audit-analytics')
def audit():
    require(g.user['role'] in ('admin','auditor'),'Audit access denied',403)
    return screen('audit')

def legacy_redirect(target):
    query=request.query_string.decode('ascii')
    return redirect(url_for(target)+('?' + query if query else ''),code=301)
for legacy,target in [('/','panel'),('/rede','network'),('/transferencias','transfers'),('/campanhas','campaigns'),('/auditoria','audit')]:
    app.add_url_rule(legacy,'legacy_'+target,lambda target=target:legacy_redirect(target))

def dispatch(op,entity_id=None,**extra):
    payload=request.get_json() if request.is_json else dict(request.form)
    payload.pop('csrf',None)
    payload.update(extra)
    for field in ('accept','handling_confirmed','receipt_confirmed'):
        if field in payload and isinstance(payload[field],str): payload[field]=payload[field]=='true'
    for field in ('hours','collected','released_usable','used_before_expiry','attended'):
        if field in payload:
            try: payload[field]=int(payload[field])
            except (ValueError,TypeError): raise Problem(422,t('invalid_number'))
    payload.update(op=op,actor_id=g.user['id'],correlation_id=str(uuid.uuid4()))
    if entity_id: payload['id']=entity_id
    payload['idempotency_key']=request.headers.get('Idempotency-Key',payload.pop('key',str(uuid.uuid4())))
    if op=='decide' and 'event_id' in payload:
        payload['idempotency_key']=payload['event_id']
    target='TransferBPL' if op in ('transfer_reply','dispatch','delivery') else 'CampaignBPL' if op.startswith('campaign') or op=='invitation_reply' else 'DecisionBPL'
    result=federation.call(target,payload)
    if request.is_json: return jsonify(result),200 if result.get('ok') else result.get('status',503)
    flash(result.get('result',{}).get('message',t('operation_complete')) if result.get('ok') else result.get('error',t('operation_failed')),
          'success' if result.get('ok') else 'critical')
    return redirect(request.referrer or url_for('panel'))

@app.post('/api/decisions')
@app.post('/api/inventory-events')
def decisions(): return dispatch('decide')
@app.post('/api/transfers/<identity>/reply')
def transfer_reply(identity): return dispatch('transfer_reply',identity)
@app.post('/api/transfers/<identity>/dispatch')
def transfer_dispatch(identity): return dispatch('dispatch',identity)
@app.post('/api/transfers/<identity>/delivery')
def transfer_delivery(identity): return dispatch('delivery',identity)
@app.post('/api/campaigns/<identity>/approve')
def campaign_approve(identity): return dispatch('campaign_approve',identity)
@app.post('/api/campaigns/<identity>/result')
def campaign_result(identity): return dispatch('campaign_result',identity)
@app.post('/api/invitations/<identity>/reply')
def invitation_reply(identity): return dispatch('invitation_reply',identity)
@app.route('/api/settings/invite-ttl',methods=['POST','PUT'])
def settings(): return dispatch('settings')
@app.post('/api/registry')
def registry(): return dispatch('registry')

@app.post('/api/demo/seed')
def demo_seed(): return dispatch('demo_seed')
@app.post('/api/demo/restore')
def demo_restore(): return dispatch('demo_restore')
@app.post('/api/demo/advance')
def demo_advance(): return dispatch('demo_advance')
@app.post('/api/demo/campaign/<identity>/process')
def demo_process(identity): return dispatch('demo_process',identity)
@app.post('/api/demo/scenario/<scenario>')
def demo_scenario(scenario):
    return dispatch('demo_scenario',scenario=scenario)

@app.get('/api/inventory/<identity>')
def inventory(identity):
    require(g.user['role'] in ('admin','manager'),'Inventory scope denied',403)
    require(demo() or not repo.get('NetworkCenter',identity).get('demo_run_id'),'Demo inventory is disabled',403)
    group=validate_product(request.args.get('blood_type','O-'))
    result=federation.inventory(identity,identity,stamp(now()+timedelta(days=7)),str(uuid.uuid4()),group)
    return jsonify(result),200 if result['status']=='AVAILABLE' else 503

@app.get('/api/analytics/<page>')
def chart_data(page):
    try: days=int(request.args.get('days','30'))
    except ValueError: raise Problem(422,'Unsupported reporting period')
    result=federation.call('AnalyticsOperation',dict(actor_id=g.user['id'],page=page,
        center=request.args.get('center','ALL'),days=days,blood_type=request.args.get('blood_type','O-')))
    require(result.get('ok'),result.get('error','Analytics source unavailable'),result.get('status',503))
    return jsonify(result['result'])
