import sys,os,iris,importlib,pathlib
print('PYTHON_PATH',sys.path)
print('ML_PACKAGES',[p.name for p in pathlib.Path('/usr/irissys/mgr/python').iterdir() if 'auto' in p.name.lower() or 'inter' in p.name.lower()])
for module in ('iris_automl',):
    try: print('IMPORT',module,importlib.import_module(module))
    except Exception as exc: print('IMPORT_ERROR',module,type(exc).__name__,str(exc))
for q in ["SELECT Name FROM %Dictionary.ClassDefinition WHERE Name %STARTSWITH '%ML'",
    "SELECT Parent,Name,FormalSpec FROM %Dictionary.CompiledMethod WHERE Parent IN ('%ML.AutoML.Provider','%ML.Provider','%ML.Utils')"]:
    print([list(r) for r in iris.sql.exec(q)])
