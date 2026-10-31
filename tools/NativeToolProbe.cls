Class HemoFlow.NativeToolProbe Extends %AI.ToolSet
{
XData Definition
{
<ToolSet Name="NativeProbe"><Tool Name="EchoNative" Method="EchoNative"/></ToolSet>
}
ClassMethod EchoNative(value As %String) As %String
{
    quit value
}
}
