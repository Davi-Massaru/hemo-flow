Class HemoFlow.Message Extends Ens.Request
{
Property JSON As %String(MAXLEN = 250000);
Property CorrelationId As %String(MAXLEN = 128);
Property Phase As %String(MAXLEN = 32);
Property EntityId As %String(MAXLEN = 128);
}
