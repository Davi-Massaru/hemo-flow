Class HemoFlow.Runtime Extends %RegisteredObject
{
ClassMethod Lock(key As %String) As %Boolean
{
    lock +^HemoFlow.Lock(key):10
    quit $test
}
ClassMethod Unlock(key As %String)
{
    lock -^HemoFlow.Lock(key)
}
ClassMethod Begin()
{
    tstart
}
ClassMethod Commit()
{
    tcommit
}
ClassMethod Rollback()
{
    trollback
}
ClassMethod Submit(json As %String, target As %String = "DecisionBPL") As %String [ PublicList = (%HemoFlowHost) ]
{
    if $isobject($get(%HemoFlowHost)) {
        set service=%HemoFlowHost
    } else {
        $$$ThrowOnError(##class(Ens.Director).CreateBusinessService("InventoryEventService",.service))
    }
    set request=##class(HemoFlow.Message).%New()
    set request.JSON=json
    set request.CorrelationId=##class(%DynamicObject).%FromJSON(json).%Get("correlation_id")
    $$$ThrowOnError(service.SendRequestSync(target,request,.response,120))
    if '$isobject(response) quit "{""ok"":false,""status"":503,""error"":""Production response unavailable or timed out""}"
    quit response.JSON
}
ClassMethod Execute(json As %String, phase As %String = "") As %String [ Language = python ]
{
import sys
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.service import execute, execute_phase
from hemoflow.common import enable_iris_demo_clock
enable_iris_demo_clock()
return execute_phase(phase,json) if phase else execute(json)
}
}
