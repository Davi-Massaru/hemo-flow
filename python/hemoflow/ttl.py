"""Reusable Dictionary-driven TTL. No ledger or campaign is ever deleted here."""
import iris
from . import repository as repo
from .common import now, stamp, date, checked

def expirable_classes():
    # Exact descendants are deliberately restricted to application-owned classes.
    return [r[0] for r in iris.sql.exec("SELECT Name FROM %Dictionary.ClassDefinition WHERE Super='HemoFlow.Expirable' AND Name %STARTSWITH 'HemoFlow.'")]

def expire(at=None,batch_size=100):
    current=stamp(at or now()); count=0
    runtime=iris.cls('HemoFlow.Runtime')
    if not runtime.Lock('mutations'): return 0
    try:
        runtime.Begin()
        for cls in expirable_classes():
            kind=cls.split('.')[-1]
            rows=list(iris.sql.exec('SELECT TOP '+str(min(batch_size,500))+' ExternalId FROM '+cls+' WHERE ExpiresAt<=? ORDER BY ExpiresAt',current))
            for row in rows:
                key=row[0]
                if kind=='PendingInvitation':
                    ledger=repo.get('InvitationLedger',key)
                    if ledger['status']=='PENDING':
                        ledger['status']='EXPIRED'; repo.put('InvitationLedger',ledger)
                        repo.audit('EventAudit',ledger['correlation_id'],'INVITATION_EXPIRED',invitation_id=key)
                        # Durable unique reassessment event. A dispatcher may process it once;
                        # it does not automatically re-publish another invitation.
                        repo.put('Outbox',dict(id='expired:'+key,status='PENDING',event='INVITATION_EXPIRED',
                            center_id=ledger['center_id'],correlation_id=ledger['correlation_id']))
                        from .workflow import timeout
                        timeout(ledger)
                checked(iris.cls(cls)._DeleteId(key));count+=1
        runtime.Commit()
    except Exception:
        runtime.Rollback(); raise
    finally: runtime.Unlock('mutations')
    return count

def pending(scope=None):
    current=stamp()
    rows=repo.all('PendingInvitation',scope=scope)
    return [row for row in rows if row['expires_at']>current]
