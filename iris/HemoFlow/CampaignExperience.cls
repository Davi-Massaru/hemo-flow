Class HemoFlow.CampaignExperience Extends %Persistent
{
Property ExternalId As %String(MAXLEN=128);
Property PartnerId As %String;
Property PartnerType As %String;
Property Region As %String;
Property Summary As %String(MAXLEN=4000);
Property ReleasedUsable As %Integer;
Property Metrics As %String(MAXLEN=10000);
Property Embedding As %Vector(DATATYPE="DOUBLE",LEN=384);
Property EmbeddingModel As %String(MAXLEN=128);
Property ContentHash As %String(MAXLEN=64);
Index Identity On ExternalId [ IdKey ];
}
