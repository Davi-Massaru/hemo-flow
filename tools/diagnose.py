import iris,sys
sys.path.insert(0,'/opt/hemoflow/python')
for r in iris.sql.exec('SELECT TOP 8 * FROM Ens_Util.Log ORDER BY ID DESC'):
    print(r[0],r[1],str(r[9])[:800])
for q in ["SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='INFORMATION_SCHEMA' AND TABLE_NAME %STARTSWITH 'ML_'",
          "SELECT Name,FormalSpec FROM %Dictionary.MethodDefinition WHERE Parent='Ens.Director' AND Name='SetAutoStart'"]:
    try: print([list(r) for r in iris.sql.exec(q)])
    except Exception as exc: print(str(exc))
