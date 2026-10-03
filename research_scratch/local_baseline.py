import ast
import collections
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
vocab = {x.casefold() for x in json.load(open(root / 'processed/drug_vocabulary.json', encoding='utf-8'))}
db = json.load(open(root / 'processed/drug_name_to_drugbank_id.json', encoding='utf-8'))
id_to_name = {v: k for k, v in db.items()}
result = {'vocab': len(vocab), 'drugbank_mapped': len(db)}
for filename in ['ddinter_all_combined.csv', 'ddinter2_all_combined.csv']:
    pairs = set()
    drugs = set()
    sev = collections.Counter()
    with open(root / 'Datasets' / filename, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            a, b = r['Drug_A'].casefold(), r['Drug_B'].casefold()
            pairs.add(tuple(sorted((a, b))))
            drugs.update((a, b))
            sev[r['Level']] += 1
    result[filename] = {'unique_pairs': len(pairs), 'drugs': len(drugs), 'drugs_in_vocab': len(drugs & vocab), 'pairs_both_in_vocab': sum(a in vocab and b in vocab for a,b in pairs), 'severity_rows': sev}

twopairs = set()
ys = set()
with open(root / 'Datasets/TWOSIDES.csv', encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        twopairs.add(tuple(sorted((r['Drug1_ID'], r['Drug2_ID']))))
        ys.add(int(r['Y']))
result['local_TWOSIDES'] = {'unique_cid_pairs': len(twopairs), 'unique_y': len(ys), 'y_min': min(ys), 'y_max': max(ys)}

hpairs = set()
hrows = 0
for filename in ['3_drug.csv','4_drug.csv','5_drug.csv']:
    with open(root / 'Datasets' / filename, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            hrows += 1
            ids = ast.literal_eval(r['DrugBankID'])
            for i,a in enumerate(ids):
                for b in ids[i+1:]:
                    hpairs.add(tuple(sorted((a,b))))
result['HODDI'] = {'positive_rows': hrows, 'pair_projection_unique': len(hpairs), 'pairs_both_ids_mapped': sum(a in id_to_name and b in id_to_name for a,b in hpairs)}
with open(root / 'research_scratch/local_baseline.json','w',encoding='utf-8') as f:
    json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
