Class HemoFlow.InventoryEventService Extends Ens.BusinessService
{
Parameter ADAPTER = "";
Method OnProcessInput(input As HemoFlow.Message, Output output As HemoFlow.Response) As %Status
{
    quit ..SendRequestSync("DecisionBPL",input,.output,120)
}
}
