"""FHIR R4 resources. Inventory availability is explicitly a custom operation."""
from .common import COMPONENT, BLOOD, stamp, require, date, now
from .products import validate_product

def validate(resource):
    from importlib import import_module
    cls = getattr(import_module('fhir.resources.'+resource['resourceType'].lower()),resource['resourceType'])
    cls.parse_obj(resource)
    return resource

def parameter(name, kind, value):
    return {'name':name, 'value'+kind:value}

def availability_input(requester, need_by, blood_type=BLOOD):
    validate_product(blood_type)
    return validate({'resourceType':'Parameters','parameter':[
        parameter('requestingCenterId','String',requester),parameter('componentCode','Code',COMPONENT),
        parameter('bloodType','Code',blood_type),parameter('horizonDays','Integer',7),
        parameter('needBy','DateTime',need_by)]})

def parse_parameters(resource):
    validate(resource)
    require(resource['resourceType']=='Parameters','Expected Parameters')
    result = {}
    for part in resource.get('parameter',[]):
        if 'part' in part:
            result.setdefault(part['name'],[]).append({p['name']:next(v for k,v in p.items() if k.startswith('value')) for p in part['part']})
        else:
            require(part['name'] not in result,'Duplicate FHIR parameter')
            result[part['name']] = next(v for k,v in part.items() if k.startswith('value'))
    return result

def parse_availability(resource, expected_center, blood_type=BLOOD):
    p = parse_parameters(resource)
    for field in ('centerId','componentCode','bloodType','availableUnits','transferableUnits','observedAt','dataVersion','responseStatus','handlingLeadTimeHours'):
        require(field in p,'Missing inventory field '+field)
    require(p['centerId']==expected_center and p['componentCode']==COMPONENT and p['bloodType']==blood_type,'Inventory identity mismatch')
    require(p['responseStatus']=='AVAILABLE','Remote unavailable',503)
    for field in ('availableUnits','transferableUnits','handlingLeadTimeHours'):
        require(type(p[field]) is int and p[field]>=0,'Invalid '+field)
    require(p['transferableUnits']<=p['availableUnits'],'Inconsistent transferable quantity')
    age = (now()-date(p['observedAt'])).total_seconds()
    require(-30<=age<=120,'Stale inventory')
    buckets = p.get('expiryBucket',[])
    for bucket in buckets:
        require(type(bucket.get('units')) is int and bucket['units']>=0,'Invalid expiry units')
        date(bucket['expiresAt'])
    require(sum(b['units'] for b in buckets)==p['transferableUnits'],'Expiry bucket total mismatch')
    return dict(center_id=p['centerId'],blood_type=blood_type,component=COMPONENT,status='AVAILABLE',available_units=p['availableUnits'],
                transferable_units=p['transferableUnits'],expiry_buckets=buckets,
                usable_buckets=p.get('usableExpiryBucket',buckets),
                observed_at=p['observedAt'],data_version=p['dataVersion'],
                handling_lead_hours=p['handlingLeadTimeHours'])

def supply_request(transfer):
    return validate({'resourceType':'SupplyRequest','id':transfer['id'], 'status':'active',
        'identifier':[{'system':'urn:hemoflow:transfer','value':transfer['id']}],
        'itemCodeableConcept':{'coding':[{'system':'urn:hemoflow:component','code':COMPONENT},{'system':'urn:hemoflow:blood-type','code':validate_product(transfer.get('blood_type',BLOOD))}], 'text':'Red blood cells '+transfer.get('blood_type',BLOOD)},
        'quantity':{'value':transfer['requested_units'],'unit':'unit','system':'http://unitsofmeasure.org','code':'[arb\'U]'},
        'authoredOn':stamp(), 'occurrenceDateTime':transfer['need_by'],
        'supplier':[{'reference':'Organization/'+transfer['source_center_id']}],
        'deliverTo':{'reference':'Location/'+transfer['target_center_id']}})

def supply_delivery(transfer,received):
    return validate({'resourceType':'SupplyDelivery','id':'delivery-'+transfer['id'], 'status':'completed',
        'basedOn':[{'reference':transfer.get('fhir_request_uri','SupplyRequest/'+transfer['id'])}],
        'suppliedItem':{'quantity':{'value':received,'unit':'unit'},
            'itemCodeableConcept':{'coding':[{'system':'urn:hemoflow:component','code':COMPONENT},{'system':'urn:hemoflow:blood-type','code':validate_product(transfer.get('blood_type',BLOOD))}],'text':'Red blood cells '+transfer.get('blood_type',BLOOD)}},
        'occurrenceDateTime':stamp(), 'destination':{'reference':'Location/'+transfer['target_center_id']}})
