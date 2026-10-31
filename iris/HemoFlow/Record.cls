Class HemoFlow.Record Extends %Persistent [ Abstract, NoExtent ]
{
Property ExternalId As %String(MAXLEN = 128) [ Required ];
Property Payload As %String(MAXLEN = 250000) [ Required ];
Property Scope As %String(MAXLEN = 128);
Property State As %String(MAXLEN = 40);
Property CreatedAt As %String(MAXLEN = 32);
Property CorrelationId As %String(MAXLEN = 128);
Index Identity On ExternalId [ IdKey ];
Index ScopeState On (Scope, State);
Index Correlation On CorrelationId;
}
