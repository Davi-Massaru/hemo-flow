Class HemoFlow.Probe Extends %RegisteredObject
{
ClassMethod Run() [ Language = python ]
{
import runpy
runpy.run_path('/opt/hemoflow/tools/probe.py', run_name='__main__')
}
ClassMethod File(path As %String) [ Language = python ]
{
import runpy, sys
sys.path.insert(0,'/opt/hemoflow/python')
runpy.run_path(path,run_name='__main__')
}
}
