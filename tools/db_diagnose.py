import iris
for cls in ('SYS.Database','Config.Databases'):
    print(cls,[list(r) for r in iris.sql.exec("SELECT Name,FormalSpec FROM %Dictionary.CompiledMethod WHERE Parent=? AND (Name LIKE '%ount%' OR Name LIKE '%eadOnly%')",cls)])
    print('PROPERTIES',[list(r) for r in iris.sql.exec("SELECT Name FROM %Dictionary.CompiledProperty WHERE Parent=? AND (Name LIKE '%ount%' OR Name LIKE '%eadOnly%')",cls)])
db=iris.cls('SYS.Database')._OpenId('/usr/irissys/mgr/irislib/')
print('DB_STATE',db.ReadOnly,db.ReadOnlyMounted,db.Mounted)
print('RO_REASON',db.ROReasonCode,db.ROReasonText)
for cls in ('Config.MapPackages','Config.Namespaces'):
    print(cls,[list(r) for r in iris.sql.exec("SELECT Name,FormalSpec FROM %Dictionary.CompiledMethod WHERE Parent=? AND Name IN ('Create','Modify','Exists','Get')",cls)])
