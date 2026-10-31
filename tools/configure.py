"""Create missing local configuration only; never overwrite an existing .env."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if not target.exists():
    content=(root/'.env.sample').read_text()
    for key in ('HEMOFLOW_CENTER_TOKEN','HEMOFLOW_SESSION_SECRET','HEMOFLOW_ADMIN_PASSWORD'):
        content=content.replace(key+'=\n',key+'='+secrets.token_urlsafe(32)+'\n')
    with target.open('x',encoding='utf-8') as output: output.write(content)
    print('Created .env; set OPENAI_API_KEY locally.')
else:
    content=target.read_text(encoding='utf-8-sig')
    keys={line.split('=',1)[0].strip() for line in content.splitlines() if '=' in line}
    additions=[]
    for key in ('HEMOFLOW_CENTER_TOKEN','HEMOFLOW_SESSION_SECRET','HEMOFLOW_ADMIN_PASSWORD'):
        if key not in keys: additions.append(key+'='+secrets.token_urlsafe(32))
    if additions:
        with target.open('a',encoding='utf-8') as output: output.write('\n'+'\n'.join(additions)+'\n')
    print('.env preserved; missing secret names initialized locally.')
