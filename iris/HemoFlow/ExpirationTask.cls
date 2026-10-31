Class HemoFlow.ExpirationTask Extends %SYS.Task.Definition
{
Parameter TaskName = "HemoFlow transient expiration";
Method OnTask() As %Status [ Language = python ]
{
import sys
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.ttl import expire
from hemoflow.common import enable_iris_demo_clock
enable_iris_demo_clock()
expire()
from hemoflow.service import dispatch_outbox
dispatch_outbox()
return 1
}
}
