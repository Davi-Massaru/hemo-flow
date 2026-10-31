Class HemoFlow.AIReadOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method OnMessage(request As HemoFlow.Message, Output response As HemoFlow.Response) As %Status [ PublicList = (%HemoFlowHost) ]
{
    new %HemoFlowHost
    set %HemoFlowHost=$this
    set response=##class(HemoFlow.Response).%New()
    set response.JSON=..Read(request.JSON)
    quit $$$OK
}
ClassMethod Read(json As %String) As %String [ Language = python ]
{
import sys,json as codec
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.intelligence import read_tool
from hemoflow.common import enable_iris_demo_clock
enable_iris_demo_clock()
request=codec.loads(json)
return read_tool(request['tool'],request['request_id'],phase='AGENT')
}
XData MessageMap
{
<MapItems><MapItem MessageType="HemoFlow.Message"><Method>OnMessage</Method></MapItem></MapItems>
}
}
