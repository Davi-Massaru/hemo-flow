Class HemoFlow.TransferBPL Extends Ens.BusinessProcessBPL
{
XData BPL [ XMLNamespace = "http://www.intersystems.com/bpl" ]
{
<process language="objectscript" request="HemoFlow.Message" response="HemoFlow.Response">
<sequence><call name="Revalidate and transition transfer" target="DomainOperation" async="0">
<request type="HemoFlow.Message"><assign property="callrequest" value="request" action="set"/></request>
<response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response>
</call><reply/></sequence>
</process>
}
}
