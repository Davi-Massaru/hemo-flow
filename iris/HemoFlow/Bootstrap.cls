Class HemoFlow.Bootstrap Extends %RegisteredObject
{
ClassMethod PythonPath() [ Language = python ]
{
import sys
if '/opt/hemoflow/python' not in sys.path: sys.path.insert(0,'/opt/hemoflow/python')
}
ClassMethod Install() As %Status
{
    do ..PythonPath()
    $$$ThrowOnError($system.OBJ.LoadDir("/opt/hemoflow/iris/HemoFlow","ck",,1))
    quit $$$OK
}
ClassMethod Provision() [ Language = python ]
{
import sys
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.provision import install
install()
}
ClassMethod WebSQL() [ Language = python ]
{
import sys, iris
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.repository import table
# Explicit UI projection allowlist. No User, DonorContact, DecisionContext,
# Command, Outbox or WorkflowLink SQL grant is made to the WSGI role.
for kind in ('NetworkCenter','Partner','Transfer','Campaign','InvitationLedger',
             'PendingInvitation','DecisionAudit','EventAudit','SystemConfig','DemoRun'):
    result=iris.cls('%SQL.Statement')._ExecDirect('','GRANT SELECT ON '+table(kind)+' TO HemoFlowWeb')
    if result._SQLCODE not in (0,100): raise RuntimeError(result._Message)
}
ClassMethod Seed() [ Language = python ]
{
import sys
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow import demo,repository
print(demo.install(repository.get('User','admin')))
}
ClassMethod IPMActivate() As %Status
{
    new $namespace
    zn "%SYS"
    $$$ThrowOnError(##class(%EnsembleMgr).EnableNamespace("USER"))
    zn "USER"
    do ..PythonPath(),..Provision()
    $$$ThrowOnError(..Web())
    do ..WebSQL()
    quit $$$OK
}
ClassMethod Web() As %Status
{
    new $namespace
    zn "%SYS"
    if '##class(Security.Roles).Exists("HemoFlowWeb") {
        $$$ThrowOnError(##class(Security.Roles).Create("HemoFlowWeb","HemoFlow WSGI runtime","%DB_USER:RW,%Service_EmbeddedPython:USE"))
    }
    set role("Resources")="%DB_USER:RW,%Service_EmbeddedPython:USE"
    $$$ThrowOnError(##class(Security.Roles).Modify("HemoFlowWeb",.role))
    set p("AutheEnabled")=64,p("Enabled")=1,p("NameSpace")="USER"
    set p("DispatchClass")="%SYS.Python.WSGI",p("WSGIAppName")="hemoflow.web",p("WSGICallable")="app"
    set p("WSGIAppLocation")="/opt/hemoflow/python",p("WSGIDebug")=0,p("WSGIType")=1
    set p("UseCookies")=2,p("CSPZENEnabled")=1,p("ResourceRequired")=""
    set p("MatchRoles")=":HemoFlowWeb"
    set p("ServeFiles")=0
    if ##class(Security.Applications).Exists("/csp/hemoflow") {
        quit ##class(Security.Applications).Modify("/csp/hemoflow",.p)
    }
    quit ##class(Security.Applications).Create("/csp/hemoflow",.p)
}
}
