"""Run using the image's irispython, in USER. Read-only capability report."""
import iris, json, sys, pathlib

classes = ['%AI.Agent', '%AI.ToolSet', '%AI.Provider', '%AI.Agent.Session',
           'Ens.BusinessService', 'Ens.BusinessOperation', 'Ens.BusinessProcessBPL',
           'EnsLib.PEX.BusinessOperation', 'EnsLib.PEX.OutboundAdapter',
           'EnsLib.Workflow.TaskRequest', 'EnsLib.Workflow.TaskResponse',
           '%SYS.Python.WSGI', '%SYS.Task.Definition', '%SYS.Task',
           '%FHIRServer.API.Data.Request', '%AI.LLM.Response', 'Ens.Director',
           'EnsLib.Workflow.Engine', 'EnsLib.Workflow.Task', 'EnsLib.PEX.Common',
           'EnsLib.JavaGateway.Service', 'Security.Applications', '%SYS.Python',
           '%Library.EnsembleMgr', 'EnsLib.PEX.ProxyOperation']
report = {'python':sys.version, 'classes':{}}
for cls in classes:
    rows = iris.sql.exec('SELECT Name,Super FROM %Dictionary.ClassDefinition WHERE Name=?', cls)
    entry = {'definition': [list(r) for r in rows]}
    for table, fields in [('MethodDefinition','Name,FormalSpec,ReturnType,Description'),('PropertyDefinition','Name,Type,InitialExpression'),('ParameterDefinition','Name,Default')]:
        try:
            entry[table] = [list(r) for r in iris.sql.exec('SELECT '+fields+' FROM %Dictionary.'+table+' WHERE parent=?',cls)]
        except Exception as exc: entry[table] = str(exc)
    report['classes'][cls] = entry
evidence=pathlib.Path('/durable/hemoflow-evidence');evidence.mkdir(exist_ok=True)
(evidence/'runtime-probe.json').write_text(json.dumps(report,default=str,indent=2))
print(json.dumps({c:bool(v['definition']) for c,v in report['classes'].items()}))
