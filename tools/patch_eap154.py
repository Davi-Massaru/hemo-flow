"""Prepare a namespace-local override; never modify IRISLIB or its protections."""
import iris,xml.etree.ElementTree as ET,pathlib
version=iris.system.Version.GetVersion()
if '2026.3.0AI (Build 154' not in version:
    raise RuntimeError('EAP154 override refused for another build')
source=pathlib.Path('/tmp/hemoflow-eap154-original.xml')
tree=ET.parse(source)
count=0
for cls in tree.getroot().findall('Class'):
    if cls.get('name') not in ('%ML.AutoML.TrainedModel','%ML.AutoML.Provider'): continue
    for method in cls.findall('Method'):
        if method.get('name')!='%PredictAll': continue
        code=method.find('Implementation')
        if ',$G(tsm))' in (code.text or ''): count+=1;continue
        if (code.text or '').count(',tsm)')!=1 or '%SYS.SQLSRV' not in code.text:
            raise RuntimeError('Unexpected vendor implementation; override refused')
        code.text=code.text.replace(',tsm)',',$G(tsm))');count+=1
if count!=2: raise RuntimeError('Expected exactly two verified wrappers')
tree.write('/tmp/hemoflow-eap154-patched.xml',encoding='utf-8',xml_declaration=True)
backup=pathlib.Path('/durable/hemoflow-eap154-original.xml')
if not backup.exists(): backup.write_bytes(source.read_bytes())
print('EAP154_PATCH_PREPARED: two verified wrappers; IRISLIB unchanged')
