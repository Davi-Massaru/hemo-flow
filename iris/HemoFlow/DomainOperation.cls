Class HemoFlow.DomainOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method OnMessage(request As HemoFlow.Message, Output response As HemoFlow.Response) As %Status [ PublicList = (%HemoFlowHost) ]
{
    new %HemoFlowHost
    set %HemoFlowHost=$this
    set response=##class(HemoFlow.Response).%New()
    set response.JSON=##class(HemoFlow.Runtime).Execute(request.JSON,request.Phase)
    quit $$$OK
}
XData MessageMap
{
<MapItems><MapItem MessageType="HemoFlow.Message"><Method>OnMessage</Method></MapItem></MapItems>
}
}
