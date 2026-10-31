Class HemoFlow.AIHubDecisionOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method OnMessage(request As HemoFlow.Message, Output response As HemoFlow.Response) As %Status [ PublicList = (%HemoFlowHost) ]
{
    new %HemoFlowHost
    set %HemoFlowHost=$this
    set response=##class(HemoFlow.Response).%New()
    try {
        set input=##class(%DynamicObject).%FromJSON(request.JSON)
        set config=##class(%DynamicObject).%FromJSON(..Configuration())
        if config.%Get("api_key")="" { set response.JSON="{""error"":""OPENAI_NOT_CONFIGURED""}" quit }
        set provider=##class(%AI.Provider).Create("openai",config)
        set agent=##class(HemoFlow.DecisionAgent).%New(provider)
        set agent.Model=config.%Get("model"),agent.MaxIterations=8
        $$$ThrowOnError(agent.%Init())
        do ..ActiveRequest(input.%Get("request_id"))
        set session=agent.CreateSession({"timeout_ms":60000,"max_tokens":900,"temperature":0})
        set result=agent.Chat(session,..Prompt(request.JSON))
        set selection=..Catalog(input.%Get("request_id"))
        set result=agent.Chat(session,"Choose exactly one candidate from this current catalog. Copy every candidate field and add reason only. Return decision JSON only. "_selection)
        set repairs=0
        for attempt=0:1 {
            set feedback=""
            try {
                set decision=##class(%DynamicObject).%FromJSON(result.Content)
                set feedback=..Validate(decision.%ToJSON(),input.%Get("request_id"),selection)
            } catch parseError { set feedback="Return a valid JSON object matching the supplied schema." }
            if feedback="" quit
            if attempt=1 { throw ##class(%Exception.General).%New("Invalid decision after one repair: "_feedback) }
            set repairs=1
            set selection=..Catalog(input.%Get("request_id"))
            set result=agent.Chat(session,"Correct your previous JSON. "_feedback_" Copy exactly one current candidate, including every field and evidence ID; add only reason. Return only JSON. "_selection)
        }
        $$$ThrowOnError(session.%Save())
        set output={}
        set output.decision=##class(%DynamicObject).%FromJSON(result.Content)
        do output.%Set("session_id",session.%Id())
        set output.stats=session.GetStats(),output.usage=result.Usage
        do output.%Set("model",agent.Model)
        do output.%Set("repair_attempts",repairs)
        set response.JSON=..Finalize(output.%ToJSON(),input.%Get("request_id"))
    } catch error {
        set response.JSON=..Failure(error.DisplayString())
        if $isobject($get(session)) {
            do session.%Save()
            set failure=##class(%DynamicObject).%FromJSON(response.JSON)
            do failure.%Set("session_id",session.%Id())
            set failure.stats=session.GetStats()
            set response.JSON=failure.%ToJSON()
        }
    }
    do ..ActiveRequest("")
    quit $$$OK
}
ClassMethod Configuration() As %String [ Language = python ]
{
import sys
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.settings import setting
from hemoflow.common import dumps
return dumps(dict(api_key=setting('OPENAI_API_KEY'),base_url=setting('OPENAI_BASE_URL','https://api.openai.com/v1'),model=setting('OPENAI_MODEL','gpt-4.1-mini')))
}
ClassMethod ActiveRequest(identity As %String)
{
    if identity="" { kill ^HemoFlow.ActiveAgent($job) } else { set ^HemoFlow.ActiveAgent($job)=identity }
}
ClassMethod Prompt(json As %String) As %String [ Language = python ]
{
import json as codec
from hemoflow.common import dumps
from hemoflow.policy import SCHEMA
request=codec.loads(json)
return dumps(dict(requestId=request['request_id'],goal='Investigate this authorized blood supply need. Call all five tools, choose their order, refresh if needed. When evidence is complete return EVIDENCE_READY. Do not choose an action until the candidate catalog is supplied.'))
}
ClassMethod Catalog(identity As %String) As %String [ Language = python ]
{
from hemoflow.intelligence import catalog
return catalog(identity)
}
ClassMethod Finalize(json As %String, identity As %String) As %String [ Language = python ]
{
from hemoflow.intelligence import finalize_agent
return finalize_agent(json,identity)
}
ClassMethod Validate(json As %String, identity As %String, request As %String) As %String [ Language = python ]
{
import json as codec
from hemoflow import policy, repository as repo
from hemoflow.intelligence import TOOL_NAMES
try:
    called={row.get('tool') for row in repo.all('EventAudit',correlation=identity) if row.get('event')=='AI_TOOL'}
    missing=sorted(set(TOOL_NAMES)-called)
    if missing:
        return 'Call missing tools '+','.join(missing)+' with exact requestId '+identity+' before answering.'
    policy.guard(codec.loads(json),repo.get('DecisionContext',identity),codec.loads(request)['candidates'])
    return ''
except Exception as error:
    return str(error).split('\n')[0][:400]
}
ClassMethod Failure(detail As %String) As %String [ Language = python ]
{
from hemoflow.settings import setting
from hemoflow.common import dumps
key=setting('OPENAI_API_KEY')
return dumps(dict(error='AI_HUB_UNAVAILABLE_OR_INVALID_OUTPUT',detail=detail.replace(key,'[redacted]')[:500] if key else detail[:500]))
}
XData MessageMap
{
<MapItems><MapItem MessageType="HemoFlow.Message"><Method>OnMessage</Method></MapItem></MapItems>
}
}
