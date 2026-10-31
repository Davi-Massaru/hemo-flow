import iris
for cls in ('%ML.AutoML.TrainedModel','%ML.AutoML.Provider'):
    q="SELECT Name,FormalSpec,ProcedureBlock FROM %Dictionary.CompiledMethod WHERE Parent=? AND Name IN ('%PredictAll','%PredictAll0')"
    print(cls,[list(r) for r in iris.sql.exec(q,cls)])
