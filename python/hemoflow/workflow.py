"""Native Workflow Engine tasks; application identities are scoped before completion."""
import iris
from . import repository as repo
from .common import dumps, checked, require

def start(entity,actor,description):
    existing=repo.get('WorkflowLink',entity['id'],False)
    if existing and existing['status']!='PENDING':return existing
    # A durable message may already exist even if its link update was interrupted.
    sent=list(iris.sql.exec("""SELECT TOP 1 ID FROM Ens.MessageHeader
        WHERE TargetConfigName='ApprovalBPL' AND MessageBodyClassName='HemoFlow.Message'
        AND MessageBodyId IN (SELECT ID FROM HemoFlow.Message WHERE EntityId=?)""",entity['id']))
    if sent:return existing or repo.put('WorkflowLink',dict(id=entity['id'],actor_id=actor,status='PENDING',correlation_id=entity['correlation_id']))
    link=existing or repo.put('WorkflowLink',dict(id=entity['id'],actor_id=actor,status='PENDING',correlation_id=entity['correlation_id']),create=True)
    checked(iris.cls('HemoFlow.Workflow').Start(dumps(dict(entity_id=entity['id'],actor_id=actor,
           description=description,correlation_id=entity['correlation_id']))))
    return link

def complete(entity,actor,action):
    link=repo.get('WorkflowLink',entity['id'])
    require(actor==link['actor_id'],'Wrong workflow assignee',403)
    if link['status']==action:return link
    # SQL names are discovered from the native class projection in build 154.
    rows=list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',entity['id']))
    require(rows,'Native approval task is not ready',409)
    task=iris.cls('EnsLib.Workflow.TaskResponse')._OpenId(str(rows[-1][0]))
    checked(task.CompleteTask(action))
    link['status']=action; link['native_task_id']=str(rows[-1][0]); repo.put('WorkflowLink',link)

def timeout(entity):
    link=repo.get('WorkflowLink',entity['id'],False)
    if not link or link['status']!='PENDING':return
    rows=list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=? AND TaskStatus_IsComplete=0',entity['id']))
    for row in rows:
        checked(iris.cls('EnsLib.Workflow.TaskResponse')._OpenId(str(row[0])).CompleteTask('EXPIRED'))
    link['status']='EXPIRED';repo.put('WorkflowLink',link)
