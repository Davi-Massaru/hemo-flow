"""Disposable technical fixture, not the final demonstration seed."""
import sys,traceback
from datetime import timedelta
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from hemoflow.common import now
from hemoflow import intelligence, repository as repo
identity='TEST-ML-CENTER'
try:
    from hemoflow.provision import install
    install()
    print('ML_PHASE fixture')
    for i in range(180):
        day=(now()-timedelta(days=180-i)).date().isoformat()
        iris.sql.exec('''INSERT INTO HemoFlow.ConsumptionDaily
            (ExternalId,CenterId,Day,UsedUnits,DemandUnmet) VALUES(?,?,TO_DATE(?,'YYYY-MM-DD'),?,?)''',
            'TEST-ML-'+str(i),identity,day,2+(i%11)//4+(i//21)%2,0)
    print('ML_PHASE train')
    print('TRAIN_RESULT',intelligence.train())
    print('FORECAST_RESULT',intelligence.forecast(identity))
except Exception as exc:
    print('ML_ERROR',type(exc).__name__,repr(exc),getattr(exc,'args',None))
    print('ML_TRACE',traceback.format_exc())
    for query in ["SELECT Split,COUNT(*) FROM HemoFlow.DemandFeature GROUP BY Split",
                  "SELECT TOP 3 Target7d,Avg7 FROM HemoFlow.DemandFeature WHERE Split='VALIDATION'",
                  "SELECT * FROM INFORMATION_SCHEMA.ML_TRAINED_MODELS"]:
        try: print('ML_DIAG',query,[list(r) for r in iris.sql.exec(query)])
        except Exception as nested: print('DIAG_ERROR',str(nested))
    try:
        rs=iris.cls('%SQL.Statement')._ExecDirect('',"SELECT Target7d,PREDICT(Demand7d),Avg7*7 FROM HemoFlow.DemandFeature WHERE Split='VALIDATION'")
        print('SQL_NATIVE',rs._SQLCODE,rs._Message)
        while rs._Next(): print('NATIVE_ROW',rs._Get(1),rs._Get(2),rs._Get(3))
        print('SQL_NATIVE_FINAL',rs._SQLCODE,rs._Message)
    except Exception as nested: print('NATIVE_ERROR',str(nested))
finally:
    for cls in ('ConsumptionDaily','DemandFeature'):
        try:
            if list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.'+cls+' WHERE CenterId=?',identity))[0][0]:
                iris.sql.exec('DELETE FROM HemoFlow.'+cls+' WHERE CenterId=?',identity)
        except Exception as exc: print('CLEANUP_ERROR',cls,repr(exc))
