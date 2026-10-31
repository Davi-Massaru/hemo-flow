Class HemoFlow.Authentication Extends %RegisteredObject
{
/// Dedicated password verifier. Never returns stored password hashes.
ClassMethod Login(username As %String, password As %String) As %String [ Language = python ]
{
import iris,json
from werkzeug.security import check_password_hash
obj=iris.cls('HemoFlow.User')._OpenId(username)
if obj is None or obj == '': return '{}'
user=json.loads(obj.Payload)
if not check_password_hash(user['password_hash'],password): return '{}'
return json.dumps({k:user[k] for k in ('id','name','scope','role')})
}
ClassMethod PublicUser(identity As %String) As %String [ Language = python ]
{
import iris,json
obj=iris.cls('HemoFlow.User')._OpenId(identity)
if obj is None or obj == '': return '{}'
user=json.loads(obj.Payload)
return json.dumps({k:user[k] for k in ('id','name','scope','role')})
}
}
