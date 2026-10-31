Class HemoFlow.DemandFeature Extends %Persistent
{
Property CenterId As %String;
Property BloodType As %String [ InitialExpression = "O-" ];
Property Day As %Date;
Property Avg7 As %Double;
Property Avg28 As %Double;
Property DayOfWeek As %Integer;
Property MonthNumber As %Integer;
Property Target7d As %Double;
Property Split As %String;
Storage Default
{
<Data name="DemandFeatureDefaultData">
<Value name="1"><Value>%%CLASSNAME</Value></Value>
<Value name="2"><Value>CenterId</Value></Value>
<Value name="3"><Value>BloodType</Value></Value>
<Value name="4"><Value>Day</Value></Value>
<Value name="5"><Value>Avg7</Value></Value>
<Value name="6"><Value>Avg28</Value></Value>
<Value name="7"><Value>DayOfWeek</Value></Value>
<Value name="8"><Value>MonthNumber</Value></Value>
<Value name="9"><Value>Target7d</Value></Value>
<Value name="10"><Value>Split</Value></Value>
</Data>
<DataLocation>^HemoFlow.DemandFeatureD</DataLocation>
<DefaultData>DemandFeatureDefaultData</DefaultData>
<IdLocation>^HemoFlow.DemandFeatureD</IdLocation>
<IndexLocation>^HemoFlow.DemandFeatureI</IndexLocation>
<StreamLocation>^HemoFlow.DemandFeatureS</StreamLocation>
<Type>%Storage.Persistent</Type>
}
}
