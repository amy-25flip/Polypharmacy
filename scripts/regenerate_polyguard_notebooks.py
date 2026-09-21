import base64
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "notebooks" / "polyguard_first_model_colab.py"
PLAIN_IPYNB = ROOT / "notebooks" / "PolyGuard_First_Model.ipynb"
SELF_IPYNB = ROOT / "notebooks" / "PolyGuard_First_Model_SelfContained.ipynb"
CSV_PATH = Path(r"E:\Polypharmacy\processed\polyguard_severity_pairs.csv")


def source_lines(text):
    return [line + "\n" for line in text.splitlines()]


def py_to_notebook(py_text):
    cells = []
    for chunk in py_text.split("# %%"):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue

        if chunk.startswith(" [markdown]"):
            body = chunk[len(" [markdown]") :].lstrip("\n")
            lines = []
            for line in body.splitlines():
                if line.startswith("# "):
                    lines.append(line[2:])
                elif line == "#":
                    lines.append("")
                else:
                    lines.append(line)
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": source_lines("\n".join(lines)),
                }
            )
        else:
            code = chunk.lstrip("\n")
            cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": source_lines(code),
                }
            )

    return {
        "cells": cells,
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def make_self_contained(nb):
    embedded = base64.b64encode(gzip.compress(CSV_PATH.read_bytes())).decode("ascii")
    self_nb = json.loads(json.dumps(nb))

    for cell in self_nb["cells"]:
        if cell["cell_type"] == "code" and any("files.upload()" in line for line in cell["source"]):
            cell["source"] = source_lines(
                "\n".join(
                    [
                        "import base64",
                        "import gzip",
                        "from pathlib import Path",
                        f'compressed_csv = """{embedded}"""',
                        'csv_path = Path("polyguard_severity_pairs.csv")',
                        "csv_path.write_bytes(gzip.decompress(base64.b64decode(compressed_csv)))",
                        'print(f"Dataset ready inside Colab: {csv_path}")',
                    ]
                )
            )
            break

    return self_nb


def main():
    nb = py_to_notebook(SOURCE_PATH.read_text(encoding="utf-8"))
    PLAIN_IPYNB.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    SELF_IPYNB.write_text(json.dumps(make_self_contained(nb), indent=1), encoding="utf-8")
    print(f"Regenerated {PLAIN_IPYNB}")
    print(f"Regenerated {SELF_IPYNB}")
    print(f"Cells: {len(nb['cells'])}")


if __name__ == "__main__":
    main()
