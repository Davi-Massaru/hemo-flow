Class HemoFlow.ExpirationService Extends Ens.BusinessService
{
Parameter ADAPTER = "Ens.InboundAdapter";
Method OnProcessInput(input As %RegisteredObject, Output output As %RegisteredObject) As %Status
{
    set task=##class(HemoFlow.ExpirationTask).%New()
    quit task.OnTask()
}
}
