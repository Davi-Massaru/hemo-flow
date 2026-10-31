"""End-to-end read-only UI/API checks against IRIS WSGI; never prints credentials."""
import json,re,sys,urllib.request,urllib.parse,http.cookiejar
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.settings import setting

base='http://127.0.0.1:52773/csp/hemoflow'
def client(username,password):
    connection=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    page=connection.open(base+'/login').read().decode()
    csrf=re.search('name="csrf" value="([^"]+)"',page)[1]
    connection.open(base+'/login',urllib.parse.urlencode(dict(username=username,password=password,csrf=csrf)).encode()).read()
    return connection

c=client('admin',setting('HEMOFLOW_ADMIN_PASSWORD'))
screens={'panel':('/dashboard','Blood Supply Dashboard',5),'network':('/blood-center-network','Blood Center Network',2),
         'transfers':('/blood-transfers','Blood Transfers',3),'campaigns':('/donation-campaigns','Donation Campaigns',3),'audit':('/audit-analytics','Audit &amp; Analytics',3)}
for key,(path,title,count) in screens.items():
    html=c.open(base+path).read().decode()
    assert '<html lang="en">' in html and title in html,(key,'English screen')
    assert 'data-analytics-url=' in html
    payload=json.load(c.open(base+'/api/analytics/'+key+'?days=180'))
    assert len(payload['charts'])==count,(key,'chart count')
    assert not any(chart.get('error') for chart in payload['charts']),(key,'chart error')
    if key=='audit' and setting('HEMOFLOW_DEMO')=='1':
        validation=next(chart for chart in payload['charts'] if chart['id']=='actual_predicted')
        assert validation['categories'] and all(len(s['data'])==len(validation['categories']) for s in validation['series']),'Empty validation cohort'
    for chart in payload['charts']:
        assert all(chart.get(k) for k in ('title','source','unit','period','updated_at','note'))
    print('UI_ANALYTICS_OK',key,len(payload['charts']))
for path in ('app.css','app.js','locales/en.json','vendor/echarts/echarts.min.js'):
    assert c.open(base+'/static/'+path).status==200
print('UI_LOCAL_ASSETS_OK')
network=c.open(base+'/rede').read().decode()
assert '<option value="NetworkCenter">Blood center</option>' in network
assert '<option value="COMPANY">Company</option>' in network
print('UI_FORM_CONTRACTS_OK')
try:c.open(base+'/api/analytics/panel?days=invalid');raise AssertionError('Invalid period accepted')
except urllib.error.HTTPError as exc:assert exc.code==422
anonymous=urllib.request.build_opener()
try:anonymous.open(base+'/api/analytics/panel');raise AssertionError('Unauthenticated charts exposed')
except urllib.error.HTTPError as exc:assert exc.code==401
if setting('HEMOFLOW_DEMO')=='1':
    donor=client('doador-1','DemoHemoFlow2026!')
    try:donor.open(base+'/api/analytics/network');raise AssertionError('Donor inventory exposed')
    except urllib.error.HTTPError as exc:assert exc.code==403
    manager=client('gestor-b','DemoHemoFlow2026!')
    assert manager.open(base+'/transferencias').status==200
    assert manager.open(base+'/campanhas').status==200
    try:manager.open(base+'/api/analytics/audit');raise AssertionError('Audit permission bypass')
    except urllib.error.HTTPError as exc:assert exc.code==403
print('UI_ACCESS_AND_VALIDATION_OK')
for old,new in [('/','/dashboard'),('/rede','/blood-center-network'),('/transferencias','/blood-transfers'),('/campanhas','/donation-campaigns'),('/auditoria','/audit-analytics')]:
    assert c.open(base+old+'?blood_type=A%2B').url==base+new+'?blood_type=A%2B'
print('UI_ENGLISH_ROUTES_OK')
if setting('HEMOFLOW_DEMO')=='1':
    payload=json.load(c.open(base+'/api/analytics/panel?center=HEMO-A&blood_type=A%2B'))
    assert len(payload['observations'])==24 and len(payload['summary'])==5
    assert {r['blood_type'] for r in payload['observations']}=={'O-','O+','A-','A+','B-','B+','AB-','AB+'}
    distribution=next(r for r in payload['charts'] if r['id']=='blood_distribution')
    assert all(isinstance(n,(int,float)) for n in distribution['series'][0]['data'])
    projection=next(r for r in payload['charts'] if r['id']=='supply_projection')
    assert len(projection['categories'])==7
    print('UI_MULTITYPE_PROJECTION_OK')
