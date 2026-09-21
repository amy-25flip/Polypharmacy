# PolyGuard Notebooks

This folder contains the notebooks/scripts we are using while building and
testing the ML side of PolyGuard.

## First model

`polyguard_first_model_colab.py` is the first working model for the project. Run
it in Google Colab and upload:

```text
E:\Polypharmacy\processed\polyguard_severity_pairs.csv
```

The model predicts the severity of a drug pair:

```text
Drug A + Drug B + disease context -> Minor / Moderate / Major
```

For a patient taking multiple medicines, the script checks all possible drug
pairs in the regimen and uses the highest predicted pair risk as the overall
regimen risk. This gives us a usable multi-drug workflow while we work toward
the more advanced graph-based version.

This is our baseline model, not the final architecture. Once this is running
properly, the next step is to add stronger drug features such as SMILES/RDKit
graphs and then move toward the GNN model.
