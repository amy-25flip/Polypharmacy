# %% [markdown]
# # PolyGuard First ML Model
#
# This notebook trains the first working severity model for PolyGuard.
# It uses the cleaned DDInter severity dataset:
#
# ```text
# polyguard_severity_pairs.csv
# ```
#
# The model learns:
#
# ```text
# Drug A + Drug B + disease context -> Minor / Moderate / Major
# ```
#
# This is our baseline model. The final project can later improve this with
# SMILES/RDKit graphs, GNNs, and stronger multi-drug modeling.

# %%
from google.colab import files

uploaded = files.upload()
csv_path = next(iter(uploaded))

print(f"Uploaded file: {csv_path}")

# %% [markdown]
# **What this cell does:**  
# This asks us to upload the cleaned CSV file from our system into Google Colab.
# Colab runs in the cloud, so it cannot automatically see the file stored on our
# laptop/PC. After upload, `csv_path` stores the filename so the next cells can
# read it.

# %%
import itertools

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import label_binarize

RANDOM_STATE = 42

SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
SEVERITY_RANK = {"Minor": 0, "Moderate": 1, "Major": 2}

# %% [markdown]
# **What this cell does:**  
# This imports the Python libraries needed for data handling, model training, and
# evaluation. We use `pandas` for the dataset, `scikit-learn` for the baseline ML
# model, and `joblib` to save the trained model. `RANDOM_STATE` makes the results
# repeatable when the notebook is rerun.

# %%
df = pd.read_csv(csv_path)

print("Dataset shape:", df.shape)
df.head()

# %% [markdown]
# **What this cell does:**  
# This loads the uploaded CSV into a dataframe and prints its size. `df.head()`
# shows the first few rows, which helps us quickly confirm that the correct file
# was uploaded and that the columns look as expected.

# %%
required_columns = {"drug_a", "drug_b", "severity"}
missing_columns = required_columns.difference(df.columns)

if missing_columns:
    raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

df = df.copy()
df["severity"] = df["severity"].astype(str).str.strip()
df = df[df["severity"].isin(SEVERITY_ORDER)].copy()

disease_cols = [
    "disease_diabetes",
    "disease_ckd",
    "disease_heart_failure",
    "disease_hypertension",
]

for col in disease_cols:
    if col not in df.columns:
        df[col] = 0
    df[col] = df[col].fillna(0).astype(int)

df["drug_a"] = df["drug_a"].fillna("").astype(str)
df["drug_b"] = df["drug_b"].fillna("").astype(str)
df["diseases"] = df.get("diseases", "").fillna("").astype(str)

pair_parts = np.sort(df[["drug_a", "drug_b"]].values.astype(str), axis=1)
df["pair_text"] = (
    pair_parts[:, 0]
    + " [DRUG_PAIR] "
    + pair_parts[:, 1]
    + " [DISEASE_SCOPE] "
    + df["diseases"]
)

df = df.drop_duplicates(subset=["pair_text", "severity"]).reset_index(drop=True)

print("Cleaned dataset shape:", df.shape)
print(df["severity"].value_counts())

# %% [markdown]
# **What this cell does:**  
# This checks that the important columns are present, keeps only valid severity
# labels, fills missing disease flags, and creates `pair_text`. `pair_text` is the
# main text feature for this baseline model. The drug names are sorted before
# joining, so `Metformin + Warfarin` and `Warfarin + Metformin` are treated as the
# same pair.

# %% [markdown]
# ## Standard Train/Validation/Test Split
#
# This split gives us the first estimate of model performance. It is useful for
# checking whether the model learns patterns from the available dataset.

# %%
train_df, temp_df = train_test_split(
    df,
    test_size=0.30,
    random_state=RANDOM_STATE,
    stratify=df["severity"],
)

val_df, test_df = train_test_split(
    temp_df,
    test_size=0.50,
    random_state=RANDOM_STATE,
    stratify=temp_df["severity"],
)

print("Train:", train_df.shape, train_df["severity"].value_counts().to_dict())
print("Validation:", val_df.shape, val_df["severity"].value_counts().to_dict())
print("Test:", test_df.shape, test_df["severity"].value_counts().to_dict())

# %% [markdown]
# **What this cell does:**  
# This divides the dataset into training, validation, and test sets. We use a
# stratified split so the `Minor`, `Moderate`, and `Major` classes stay in similar
# proportions across all three sets. That matters because the dataset has many
# more `Moderate` examples than the other two classes.

# %%
feature_cols = ["pair_text", *disease_cols]

def make_model() -> Pipeline:
    preprocess = ColumnTransformer(
        transformers=[
            (
                "pair_text",
                TfidfVectorizer(
                    lowercase=True,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                ),
                "pair_text",
            ),
            ("disease_flags", "passthrough", disease_cols),
        ],
        remainder="drop",
    )

    return Pipeline(
        steps=[
            ("features", preprocess),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="saga",
                    n_jobs=-1,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

model = make_model()
model.fit(train_df[feature_cols], train_df["severity"])

# %% [markdown]
# **What this cell does:**  
# This builds a fresh baseline model and trains it. `TfidfVectorizer` converts
# drug-pair text into numeric features, while the disease columns are passed in
# as normal numeric inputs. `class_weight="balanced"` helps the model pay
# attention to smaller classes like `Minor` and `Major`, instead of mostly
# predicting `Moderate`.

# %%
def evaluate_model(model: Pipeline, data: pd.DataFrame, name: str) -> dict[str, float]:
    y_true = data["severity"]
    y_pred = model.predict(data[feature_cols])
    y_proba = model.predict_proba(data[feature_cols])
    classes = list(model.named_steps["classifier"].classes_)

    print(f"\n{name}")
    print("=" * len(name))
    print("Accuracy:", round(accuracy_score(y_true, y_pred), 4))
    print("Macro-F1:", round(f1_score(y_true, y_pred, average="macro"), 4))
    print()
    print(classification_report(y_true, y_pred, digits=4))

    y_bin = label_binarize(y_true, classes=classes)
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
    }

    if y_bin.shape[1] == y_proba.shape[1]:
        metrics["macro_auroc_ovr"] = roc_auc_score(
            y_bin,
            y_proba,
            average="macro",
            multi_class="ovr",
        )
        metrics["macro_auprc"] = average_precision_score(
            y_bin,
            y_proba,
            average="macro",
        )
        print("Macro AUROC OvR:", round(metrics["macro_auroc_ovr"], 4))
        print("Macro AUPRC:", round(metrics["macro_auprc"], 4))

    cm = confusion_matrix(y_true, y_pred, labels=classes)
    ConfusionMatrixDisplay(cm, display_labels=classes).plot(xticks_rotation=45)

    return metrics


val_metrics = evaluate_model(model, val_df, "Validation Set")
test_metrics = evaluate_model(model, test_df, "Standard Test Set")

# %% [markdown]
# **What this cell does:**  
# This evaluates the model using the validation and test sets. We report accuracy,
# macro-F1, precision, recall, AUROC, AUPRC, and a confusion matrix. Macro-F1 is
# especially important here because it treats all severity classes equally, even
# when one class has many more examples.

# %% [markdown]
# ## Cold-Start Test
#
# A normal random split can make performance look better than it really is,
# because the same drugs may appear in both training and test data. A cold-start
# split is stricter because some drugs are completely held out from training.

# %%
all_drugs = pd.Index(
    pd.concat(
        [
            df["drug_a"].str.lower().str.strip(),
            df["drug_b"].str.lower().str.strip(),
        ]
    )
    .dropna()
    .unique()
)

rng = np.random.default_rng(RANDOM_STATE)
cold_drugs = set(
    rng.choice(
        all_drugs,
        size=max(1, int(len(all_drugs) * 0.20)),
        replace=False,
    )
)

has_cold_drug = (
    df["drug_a"].str.lower().str.strip().isin(cold_drugs)
    | df["drug_b"].str.lower().str.strip().isin(cold_drugs)
)

cold_train_df = df[~has_cold_drug].copy()
cold_test_df = df[has_cold_drug].copy()

print("Cold-start train:", cold_train_df.shape, cold_train_df["severity"].value_counts().to_dict())
print("Cold-start test:", cold_test_df.shape, cold_test_df["severity"].value_counts().to_dict())

# %% [markdown]
# **What this cell does:**  
# This creates a cold-start split by holding out 20% of the unique drugs. Any pair
# containing one of those held-out drugs goes into the cold-start test set. This
# tells us how well the model handles medicines it did not see during training.

# %%
cold_model = make_model()
cold_model.fit(cold_train_df[feature_cols], cold_train_df["severity"])
cold_metrics = evaluate_model(cold_model, cold_test_df, "Cold-Start Test Set")

# %% [markdown]
# **What this cell does:**  
# This trains a second version of the same baseline model using only the
# cold-start training data, then evaluates it on the held-out-drug test data. We
# expect this score to be lower than the standard test score, but it is a more
# honest check for real-world generalization.

# %% [markdown]
# ## Save the Trained Model

# %%
model_filename = "polyguard_pairwise_severity_model.joblib"

joblib.dump(model, model_filename)
files.download(model_filename)

# %% [markdown]
# **What this cell does:**  
# This saves the trained standard-split model as a `.joblib` file and downloads it
# from Colab. We can later load this file inside a backend/API or use it for demo
# predictions without retraining every time.

# %% [markdown]
# ## Multi-Drug Regimen Prediction
#
# The model predicts one pair at a time, but PolyGuard accepts a full medicine
# list. For a multi-drug regimen, we score every unique pair and then use the
# highest pair severity as the overall regimen risk.

# %%
def predict_pair(drug_a: str, drug_b: str, diseases: str = "") -> dict[str, object]:
    row = pd.DataFrame(
        [
            {
                "pair_text": " [DRUG_PAIR] ".join(sorted([drug_a, drug_b]))
                + " [DISEASE_SCOPE] "
                + diseases,
                "disease_diabetes": int("diabetes" in diseases.lower()),
                "disease_ckd": int("kidney" in diseases.lower() or "ckd" in diseases.lower()),
                "disease_heart_failure": int("heart" in diseases.lower()),
                "disease_hypertension": int("hypertension" in diseases.lower()),
            }
        ]
    )

    predicted_severity = model.predict(row[feature_cols])[0]
    probabilities = model.predict_proba(row[feature_cols])[0]
    classes = list(model.named_steps["classifier"].classes_)

    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "predicted_severity": predicted_severity,
        "confidence": float(np.max(probabilities)),
        **{
            f"prob_{severity_class}": float(probabilities[index])
            for index, severity_class in enumerate(classes)
        },
    }


def predict_regimen(drugs: list[str], diseases: str = "") -> tuple[str, pd.DataFrame]:
    pair_results = [
        predict_pair(drug_a, drug_b, diseases)
        for drug_a, drug_b in itertools.combinations(drugs, 2)
    ]

    results = pd.DataFrame(pair_results)

    if results.empty:
        return "No pair to score", results

    results["severity_rank"] = results["predicted_severity"].map(SEVERITY_RANK)
    highest_risk_row = results.sort_values(
        ["severity_rank", "confidence"],
        ascending=False,
    ).iloc[0]

    overall_severity = highest_risk_row["predicted_severity"]
    return overall_severity, results.drop(columns=["severity_rank"])


example_drugs = ["Metformin", "Warfarin", "Furosemide", "Lisinopril"]

overall_severity, pair_table = predict_regimen(
    example_drugs,
    diseases="Diabetes|Hypertension|Heart Failure",
)

print("Overall regimen severity:", overall_severity)
pair_table.sort_values(["predicted_severity", "confidence"], ascending=False)

# %% [markdown]
# **What this cell does:**  
# This is the first multi-drug workflow. If the user enters four medicines, the
# code checks all six possible pairs, predicts a severity for each pair, and then
# reports the highest risk as the regimen-level result. This keeps the project
# multi-drug at the application level while the first ML model remains pairwise.

# %% [markdown]
# ## Notes for the Next Version
#
# This baseline is useful because it gives us a working model and clear metrics.
# For the next version, we should improve the drug representation. The main next
# step is to connect each drug to a reliable SMILES string, convert SMILES into
# molecular graphs using RDKit, and train the GNN/GATv2 model.
