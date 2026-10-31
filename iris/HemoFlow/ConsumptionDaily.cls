Class HemoFlow.ConsumptionDaily Extends %Persistent
{
Property ExternalId As %String(MAXLEN=128);
Property CenterId As %String;
Property BloodType As %String [ InitialExpression = "O-" ];
Property Day As %Date;
Property UsedUnits As %Integer;
Property DemandUnmet As %Boolean;
Index Identity On ExternalId [ IdKey ];
Index CenterProductDay On (CenterId,BloodType,Day) [ Unique ];
Storage Default
{
<Data name="ConsumptionDailyDefaultData">
<Value name="1"><Value>%%CLASSNAME</Value></Value>
<Value name="2"><Value>CenterId</Value></Value>
<Value name="3"><Value>BloodType</Value></Value>
<Value name="4"><Value>Day</Value></Value>
<Value name="5"><Value>UsedUnits</Value></Value>
<Value name="6"><Value>DemandUnmet</Value></Value>
</Data>
<DataLocation>^HemoFlow.ConsumptionDailyD</DataLocation>
<DefaultData>ConsumptionDailyDefaultData</DefaultData>
<IdLocation>^HemoFlow.ConsumptionDailyD</IdLocation>
<IndexLocation>^HemoFlow.ConsumptionDailyI</IndexLocation>
<StreamLocation>^HemoFlow.ConsumptionDailyS</StreamLocation>
<Type>%Storage.Persistent</Type>
}
}
