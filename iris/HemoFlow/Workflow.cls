Class HemoFlow.Workflow Extends %RegisteredObject
{
ClassMethod Start(json As %String) As %Status [ PublicList = (%HemoFlowHost) ]
{
    if $isobject($get(%HemoFlowHost)) {
        set service=%HemoFlowHost
    } else {
        $$$ThrowOnError(##class(Ens.Director).CreateBusinessService("InventoryEventService",.service))
    }
    set request=##class(HemoFlow.Message).%New(),request.JSON=json
    set data=##class(%DynamicObject).%FromJSON(json)
    set request.CorrelationId=data.%Get("correlation_id"),request.EntityId=data.%Get("entity_id")
    quit service.SendRequestAsync("ApprovalBPL",request)
}
ClassMethod Complete(taskId As %String, action As %String) As %Status [ Language = python ]
{
import iris
task=iris.cls('EnsLib.Workflow.TaskResponse')._OpenId(taskId)
return task.CompleteTask(action)
}
}
