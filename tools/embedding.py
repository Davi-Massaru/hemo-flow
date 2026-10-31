import sys
sys.path.insert(0,'/opt/hemoflow/python')
try:
    from hemoflow.intelligence import embedding
    result=embedding('Blood donation campaign at a university with released red blood cells')
    print('EMBEDDING_OK',len(result.split(',')))
except Exception as exc: print('EMBEDDING_ERROR',type(exc).__name__,str(exc))
