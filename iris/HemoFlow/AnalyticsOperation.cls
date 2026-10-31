Class HemoFlow.AnalyticsOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method OnMessage(request As HemoFlow.Message, Output response As HemoFlow.Response) As %Status
{
    set response=##class(HemoFlow.Response).%New()
    set response.JSON=..Read(request.JSON)
    quit $$$OK
}
ClassMethod Read(json As %String) As %String [ Language = python ]
{
import sys,json as codec
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.analytics import build
from hemoflow import repository
from hemoflow.common import enable_iris_demo_clock,Problem,dumps
enable_iris_demo_clock()
request=codec.loads(json)
try:
    user=repository.get('User',request['actor_id'])
    return dumps(dict(ok=True,result=build(request['page'],user,request.get('center','ALL'),request.get('days',30),request.get('blood_type','O-'))))
except Problem as exc:
    return dumps(dict(ok=False,status=exc.status,error=exc.message))
except Exception:
    return dumps(dict(ok=False,status=503,error='Analytics source unavailable'))
}
XData MessageMap
{
<MapItems><MapItem MessageType="HemoFlow.Message"><Method>OnMessage</Method></MapItem></MapItems>
}
}
