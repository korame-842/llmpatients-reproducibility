# Modified 2026-10-27: read numeric CSV projections instead of withheld XLSX.
"""Recalculate Panel B from the original workbooks with the standard library."""
from pathlib import PurePosixPath
import csv,json,re,zipfile
import xml.etree.ElementTree as ET


def labels(path):
    rater = path.name.removesuffix('_completed.xlsx')
    data = path.parent.parent.parent / 'turn_labels.csv'
    rows = [r for r in csv.DictReader(data.open()) if r['rater_id'] == rater]
    out = {(r['transcript_id'], int(r['turn'])): r['positive'] == 'True' for r in rows}
    if len(out) != len(rows) or len(out) != 300:
        raise ValueError('Expected 300 unique projected therapist-turn labels')
    return out


def recompute(root):
    workbooks=root/'clinician_ratings'/'workbooks'
    first=labels(workbooks/'rater_1_completed.xlsx');second=labels(workbooks/'rater_2_completed.xlsx')
    predictions=json.loads((root/'predictions.json').read_text());units=[];detected={};scripted={}
    for row in predictions:
        transcript=row['transcriptId'];flags={int(x) for c in row['detectedCategories'] for x in c.get('therapistTurns',[])}
        for turn in range(1,int(row['summary']['therapistTurnCount'])+1):
            key=transcript,turn
            if key in detected:raise ValueError('Duplicate detector turn')
            units.append(key);detected[key]=turn in flags;scripted[key]=row['scriptVariant']=='seeded_misstep'
    if len(units)!=300 or set(units)!=set(first) or set(first)!=set(second):raise ValueError('Rater/detector coverage differs')
    references={'Rater 1':lambda x:first[x],'Rater 2':lambda x:second[x],
                'Either clinician positive':lambda x:first[x] or second[x],
                'Both clinicians positive':lambda x:first[x] and second[x],
                'Therapist turns with deliberately scripted missteps':lambda x:scripted[x]}
    expected={x['reference']:x for x in csv.DictReader((root/'expected_metrics.csv').open())};out={}
    for name,reference in references.items():
        tp=fp=tn=fn=0
        for key in units:
            predicted=detected[key];actual=reference(key)
            if predicted and actual:tp+=1
            elif predicted:fp+=1
            elif actual:fn+=1
            else:tn+=1
        precision=tp/(tp+fp);recall=tp/(tp+fn)
        row={'tp':tp,'fp':fp,'tn':tn,'fn':fn,'precision':round(precision,3),
             'recall':round(recall,3),'f1':round(2*precision*recall/(precision+recall),3),
             'accuracy':round((tp+tn)/len(units),3)}
        if any(value!=float(expected[name][key]) for key,value in row.items()):raise ValueError('Panel B changed: '+name)
        out[name]=row
    return out
