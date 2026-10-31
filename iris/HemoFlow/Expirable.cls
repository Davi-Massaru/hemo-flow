Class HemoFlow.Expirable Extends HemoFlow.Record [ Abstract, NoExtent ]
{
Parameter TTLSECONDS = 86400;
Property ExpiresAt As %String(MAXLEN = 32) [ Required ];
Index ExpiryIndex On ExpiresAt;
}
