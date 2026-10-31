Class HemoFlow.FHIRTransferOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method OnMessage(request As HemoFlow.Message, Output response As HemoFlow.Response) As %Status
{
    set response=##class(HemoFlow.Response).%New()
    set response.JSON=..Exchange(request.JSON)
    quit $$$OK
}
ClassMethod Exchange(json As %String) As %String [ Language = python ]
{
import sys,json as codec,re
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.federation import http
from hemoflow.common import dumps,require,Problem,enable_iris_demo_clock
enable_iris_demo_clock()
request=codec.loads(json)
try:
    path=request['path']
    require(path in ('/fhir/SupplyRequest','/fhir/SupplyDelivery') or
            re.fullmatch(r'/transfers/[A-Za-z0-9-]+/(dispatch|receive)',path) or
            re.fullmatch(r'/campaigns/[A-Za-z0-9-]+/release',path),'FHIR operation path not allowed',403)
    return dumps(dict(ok=True,result=http(request['center_id'],path,request['body'],request.get('headers'))))
except Problem as exc:return dumps(dict(ok=False,status=exc.status,error=exc.message))
}
XData MessageMap
{
<MapItems><MapItem MessageType="HemoFlow.Message"><Method>OnMessage</Method></MapItem></MapItems>
}
}
