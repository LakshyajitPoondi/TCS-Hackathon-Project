import io
import subprocess
import sys
import pandas as pd
from backend.services.documents import extract
from backend.core import config
from backend import db
from engine import llm

def test_live_missing_key(monkeypatch,capsys):
    from evals.live_llm_check import run
    monkeypatch.setattr(config,'LLM_API_KEY','');assert run()==0
    assert 'no live LLM_API_KEY' in capsys.readouterr().out
def test_pdf_page_and_doc_metadata(client):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 150 Td (Inspect coolant flow.) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
    buffer=io.BytesIO();writer.write(buffer);parts=extract('guide.pdf',buffer.getvalue())
    assert parts[0]['location']=='Page 1' and 'Inspect coolant flow' in parts[0]['text']
    r=client.patch('/api/documents/SOP-007',json={'scope':'plant','targets':[],'title':'Cooling System Troubleshooting','doc_type':'sop'})
    assert r.status_code==200 and r.json()['status']=='pending_mapping'
    assert client.post('/api/documents/SOP-007/confirm',json={'scope':'plant','targets':[]}).status_code==200
def test_registry_upload_plausibility(client):
    frame=pd.read_csv('data/incidents/incident_001.csv');frame['machine']='UNKNOWN'
    assert client.post('/api/incidents/upload',files={'file':('bad.csv',frame.to_csv(index=False).encode())}).status_code==422
    frame=pd.read_csv('data/incidents/incident_001.csv');frame['vibration']=80
    assert client.post('/api/incidents/upload',files={'file':('bad.csv',frame.to_csv(index=False).encode())}).status_code==422
