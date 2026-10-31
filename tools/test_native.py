import sys,json,pathlib,os
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow.provision import install
install()
import pytest
result=pytest.main(['/opt/hemoflow/tests','-q','-s','--tb=short','-p','no:cacheprovider'])
print('PYTEST_EXIT',result)
evidence=pathlib.Path('/durable/hemoflow-evidence');evidence.mkdir(exist_ok=True)
(evidence/'native-test-status.json').write_text(json.dumps({'exit_code':int(result)}))
