Class HemoFlow.DecisionTools Extends %AI.ToolSet
{
XData Definition
{
<ToolSet Name="HemoFlow">
<Tool Name="forecast_demand" Method="ForecastDemand"/>
<Tool Name="query_network_inventory" Method="QueryNetworkInventory"/>
<Tool Name="search_campaign_experience" Method="SearchCampaignExperience"/>
<Tool Name="list_campaign_partners" Method="ListCampaignPartners"/>
<Tool Name="get_active_campaigns" Method="GetActiveCampaigns"/>
</ToolSet>
}
/// Forecast the authorized request with IntegratedML.
ClassMethod ForecastDemand(requestId As %String) As %String
{
    quit ..Dispatch("forecast_demand",requestId)
}
/// Query institution systems live through Java PEX and the custom adapter.
ClassMethod QueryNetworkInventory(requestId As %String) As %String
{
    quit ..Dispatch("query_network_inventory",requestId)
}
/// Retrieve historical campaigns with IRIS Vector Search.
ClassMethod SearchCampaignExperience(requestId As %String) As %String
{
    quit ..Dispatch("search_campaign_experience",requestId)
}
/// List authorized partners and declared capacity.
ClassMethod ListCampaignPartners(requestId As %String) As %String
{
    quit ..Dispatch("list_campaign_partners",requestId)
}
/// List confirmed campaigns; targets do not count as blood.
ClassMethod GetActiveCampaigns(requestId As %String) As %String
{
    quit ..Dispatch("get_active_campaigns",requestId)
}
/// Native-only SDK trampoline: direct Python callbacks segfault in EAP154.
/// Python executes in the independent AIReadOperation job, outside Rust callbacks.
ClassMethod Dispatch(name As %String, requestId As %String) As %String
{
    if requestId'=$get(^HemoFlow.ActiveAgent($job)) throw ##class(%Exception.General).%New("Tool request not authorized")
    set input={}
    do input.%Set("request_id",requestId),input.%Set("correlation_id",requestId)
    set input.tool=name
    quit ##class(HemoFlow.Runtime).Submit(input.%ToJSON(),"AIReadOperation")
}
}
