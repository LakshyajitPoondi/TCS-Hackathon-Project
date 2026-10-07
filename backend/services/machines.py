from sqlalchemy import select
from backend import db
from backend.services.data_loader import list_incidents,load_incident

def seed_machines(session):
    import pandas as pd
    baselines=[]
    for ref in list_incidents():
        frame=load_incident(ref['id'])
        for _,group in frame.groupby('machine'):
            baselines.append(group.head(round(len(group)*.25)))
    baseline=pd.concat(baselines)
    for (line,short),group in baseline.groupby(['line','machine']):
        uid=line+'/'+short
        if session.get(db.Machine,uid):continue
        ranges={signal:{'min':round(float(group[signal].min()),3),'max':round(float(group[signal].max()),3),'normal':round(float(group[signal].mean()),3)} for signal in ('temperature','speed','vibration','motor_current')}
        data={'display_name':uid,'type':'Injection molding (synthetic)','manufacturer':'Unknown (synthetic)','serial_number':None,'install_date':None,'status':'running','normal_ranges':ranges,'range_provenance':'First 25% of timesteps per machine in each existing CSV; combined by physical line/machine. Descriptive baseline ranges, not safety limits.'}
        session.add(db.Machine(machine_uid=uid,short_name=short,line=line,model='IMM',data=data))

def serialize(machine):
    return {**machine.data,'machine_uid':machine.machine_uid,'short_name':machine.short_name,'line':machine.line,'model':machine.model}
