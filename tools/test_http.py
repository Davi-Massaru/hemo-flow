"""Real HTTP through the IRIS WSGI dispatcher. Prints status only, never secrets."""
import sys,re,urllib.request,urllib.parse,http.cookiejar
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.settings import setting
base='http://127.0.0.1:52773/csp/hemoflow'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
try:
    page=client.open(base+'/login').read().decode()
    match=re.search('name="csrf" value="([^"]+)"',page)
    assert match,'Login form did not render'
    data=urllib.parse.urlencode(dict(username='admin',password=setting('HEMOFLOW_ADMIN_PASSWORD'),csrf=match[1])).encode()
    result=client.open(base+'/login',data).read()
    for path in ('/','/rede','/transferencias','/campanhas','/auditoria'):
        response=client.open(base+path)
        assert response.status==200
        assert b'HemoFlow' in response.read()
        print('HTTP_WSGI_OK',path,response.status)
    assert client.open(base+'/static/app.css').status==200
    page=client.open(base+'/').read().decode()
    token=re.search('name="csrf" value="([^"]+)"',page)[1]
    body=urllib.parse.urlencode(dict(hours=24,csrf=token)).encode()
    response=client.open(base+'/api/settings/invite-ttl',body)
    assert response.status==200
    print('HTTP_PRODUCTION_MUTATION_OK',response.status)
except Exception as exc:
    print('HTTP_WSGI_ERROR',type(exc).__name__,str(exc))
    if hasattr(exc,'read'): print(exc.read().decode(errors='replace')[:1000])
