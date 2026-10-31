Class HemoFlow.ToolProbe Extends %AI.ToolSet
{
XData Definition
{
<ToolSet Name="Probe"><Tool Name="EchoPython" Method="EchoPython"/><Tool Name="EchoNative" Method="EchoNative"/></ToolSet>
}
ClassMethod EchoPython(value As %String) As %String [ Language = python ]
{
return value
}
ClassMethod EchoNative(value As %String) As %String
{
    quit value
}
}
