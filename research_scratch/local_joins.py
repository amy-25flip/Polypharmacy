import ast
import collections
import csv
import json
from pathlib import Path
from rdkit import Chem

root = Path(__file__).resolve().parent.parent
name_to_db = json.load(open(root/'processed/drug_name_to_drugbank_id.json',encoding='utf-8'))
db_to_name = {v:k for k,v in name_to_db.items()}
vocab = {x.casefold() for x in json.load(open(root/'processed/drug_vocabulary.json',encoding='utf-8'))}
dd = set()
dd_known = set()
with open(root/'Datasets/ddinter_all_combined.csv',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        pair = tuple(sorted((r['Drug_A'].casefold(),r['Drug_B'].casefold())))
        if all(x in vocab for x in pair):
            dd.add(pair)
            if r['Level'] != 'Unknown': dd_known.add(pair)
hpairs = set()
for fn in ['3_drug.csv','4_drug.csv','5_drug.csv']:
    with open(root/'Datasets'/fn,encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            ids = ast.literal_eval(r['DrugBankID'])
            for i,a in enumerate(ids):
                for b in ids[i+1:]:
                    if a in db_to_name and b in db_to_name:
                        hpairs.add(tuple(sorted((db_to_name[a],db_to_name[b]))))

dbsmiles = collections.defaultdict(set)
def canon(s, stereo=False):
    if not s: return None
    m=Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m,isomericSmiles=stereo) if m else None
with open(root/'Datasets/DrugBankID2SMILES.csv',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        if r['drugbank_id'] in db_to_name:
            c=canon(r['smiles'])
            if c: dbsmiles[c].add(db_to_name[r['drugbank_id']])
cid_smiles={}
cid_pairs=set()
with open(root/'Datasets/TWOSIDES.csv',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        cid_smiles[r['Drug1_ID']]=r['Drug1']
        cid_smiles[r['Drug2_ID']]=r['Drug2']
        cid_pairs.add(tuple(sorted((r['Drug1_ID'],r['Drug2_ID']))))
cid_names={cid:dbsmiles.get(canon(s),set()) for cid,s in cid_smiles.items()}
resolved={cid:next(iter(names)) for cid,names in cid_names.items() if len(names)==1}
twopairs={tuple(sorted((resolved[a],resolved[b]))) for a,b in cid_pairs if a in resolved and b in resolved}
result={
 'dd_pairs_both_vocab':len(dd),'dd_pairs_known_severity':len(dd_known),
 'hoddi_projected_pairs_mapped':len(hpairs),'hoddi_dd_overlap':len(hpairs&dd),
 'twosides_cids':len(cid_smiles),'cids_unique_smiles_join':len(resolved),
 'twosides_cid_pairs':len(cid_pairs),'twosides_pairs_resolved':len(twopairs),
 'twosides_dd_overlap':len(twopairs&dd),
 'twosides_dd_known_overlap':len(twopairs&dd_known)
}
strict_dbsmiles=collections.defaultdict(set)
with open(root/'Datasets/DrugBankID2SMILES.csv',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        if r['drugbank_id'] in db_to_name:
            c=canon(r['smiles'],True)
            if c: strict_dbsmiles[c].add(db_to_name[r['drugbank_id']])
strict_names={cid:strict_dbsmiles.get(canon(s,True),set()) for cid,s in cid_smiles.items()}
strict_resolved={cid:next(iter(names)) for cid,names in strict_names.items() if len(names)==1}
strict_twopairs={tuple(sorted((strict_resolved[a],strict_resolved[b]))) for a,b in cid_pairs if a in strict_resolved and b in strict_resolved}
result.update({'strict_cids_unique_join':len(strict_resolved),'strict_twosides_pairs_resolved':len(strict_twopairs),'strict_twosides_dd_overlap':len(strict_twopairs&dd),'strict_twosides_dd_known_overlap':len(strict_twopairs&dd_known)})
with open(root/'research_scratch/local_joins.json','w',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
