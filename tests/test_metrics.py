from hemoflow import metrics
from test_policy import context

def test_comparison_keeps_receipt_separate_from_use_and_offline_unknown():
    c=context();before=metrics.risk(c)
    decision=dict(status='DECIDED',forecast=c['forecast'],kpi_before=before)
    result=metrics.dashboard([decision],[dict(received_units=12,used_units=0)],[],c['network'])
    assert result['before']['deficit']==result['after']['deficit']
    assert result['received']==12 and result['used']==0
    c['network'][0]={'center_id':'HEMO-A','status':'UNAVAILABLE'}
    result=metrics.dashboard([decision],[],[],c['network'])
    assert result['after']['deficit'] is None and not result['after']['complete']
