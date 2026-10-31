Class HemoFlow.ApprovalBPL Extends Ens.BusinessProcessBPL
{
XData BPL [ XMLNamespace = "http://www.intersystems.com/bpl" ]
{
<process language="objectscript" request="HemoFlow.Message" response="HemoFlow.Response">
<context><property name="Task" type="EnsLib.Workflow.TaskRequest" instantiate="0"/></context>
<sequence>
<code name="Prepare human task"><![CDATA[
 set data=##class(%DynamicObject).%FromJSON(request.JSON)
 set context.Task=##class(EnsLib.Workflow.TaskRequest).%New()
 set context.Task.%Subject=data.%Get("entity_id")
 set context.Task.%Message=data.description
 set context.Task.%UserName=data.%Get("actor_id")
 set context.Task.%Actions="ACCEPT,DECLINE,EXPIRED"
]]></code>
<call name="HumanApproval" target="Approvals" async="1">
<request type="EnsLib.Workflow.TaskRequest"><assign property="callrequest" value="context.Task" action="set"/></request>
</call>
<sync calls="HumanApproval" type="all" timeout="604800"/>
<reply/>
</sequence>
</process>
}
}
