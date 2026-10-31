Class HemoFlow.DecisionBPL Extends Ens.BusinessProcessBPL
{
XData BPL [ XMLNamespace = "http://www.intersystems.com/bpl" ]
{
<process language="objectscript" request="HemoFlow.Message" response="HemoFlow.Response">
<context><property name="Work" type="HemoFlow.Message" instantiate="0"/><property name="Evaluate" type="%Boolean"/><property name="Route" type="%String"/><property name="Identity" type="%String"/></context>
<sequence>
<code name="Classify"><![CDATA[
 set context.Work=request
 set data=##class(%DynamicObject).%FromJSON(request.JSON)
 set context.Evaluate=$listfind($listbuild("decide","demo_scenario","recover_decision"),data.%Get("op"))>0
 if context.Evaluate set context.Work.Phase="prepare"
]]></code>
<call name="Prepare" target="DomainOperation" async="0"><request type="HemoFlow.Message"><assign property="callrequest" value="context.Work" action="set"/></request><response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response></call>
<if condition="context.Evaluate"><true>
<code name="Read preparation"><![CDATA[
 set data=##class(%DynamicObject).%FromJSON(response.JSON)
 set context.Evaluate=data.%Get("evaluate",0),context.Identity=data.%Get("request_id"),context.Route=data.%Get("route")
 set context.Work=##class(HemoFlow.Message).%New(),context.Work.JSON=response.JSON,context.Work.CorrelationId=context.Identity
]]></code>
<if condition="context.Evaluate"><true>
<call name="Agent" target="AIHubDecisionOperation" async="1"><request type="HemoFlow.Message"><assign property="callrequest" value="context.Work" action="set"/></request><response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response></call><sync calls="Agent" type="all" timeout="110"/>
<code name="Prepare guard"><![CDATA[
 set data={}
 do data.%Set("request_id",context.Identity)
 set data.ai=##class(%DynamicObject).%FromJSON(response.JSON)
 set context.Work.JSON=data.%ToJSON(),context.Work.Phase="guard"
]]></code>
<call name="Guard" target="DomainOperation" async="0"><request type="HemoFlow.Message"><assign property="callrequest" value="context.Work" action="set"/></request><response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response></call>
<code name="Read validated route"><![CDATA[
 set data=##class(%DynamicObject).%FromJSON(response.JSON)
 set context.Route=data.%Get("route")
]]></code>
</true></if>
<code name="Prepare branch"><![CDATA[
 set data={}
 do data.%Set("request_id",context.Identity)
 set context.Work.JSON=data.%ToJSON()
]]></code>
<if condition='context.Route="REQUEST_TRANSFER"'><true>
<assign property="context.Work.Phase" value='"start_transfer"' action="set"/>
<call name="Transfer" target="TransferBPL" async="0"><request type="HemoFlow.Message"><assign property="callrequest" value="context.Work" action="set"/></request><response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response></call>
</true><false><if condition='context.Route="REQUEST_CAMPAIGN"'><true>
<assign property="context.Work.Phase" value='"start_campaign"' action="set"/>
<call name="Campaign" target="CampaignBPL" async="0"><request type="HemoFlow.Message"><assign property="callrequest" value="context.Work" action="set"/></request><response type="HemoFlow.Response"><assign property="response" value="callresponse" action="set"/></response></call>
</true></if></false></if>
</true></if>
<reply/>
</sequence>
</process>
}
}

