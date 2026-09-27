"""
Minimal Unsafe Subset Certificate.

For a 3-5 drug regimen where Model 3 (HODDI DeepSets) flags an elevated
combination-risk signal, this answers a question the pair-by-pair review and
the combination-signal note both leave open: which drugs in the regimen are
actually RESPONSIBLE for that warning?

Exhaustive: for at most 5 drugs there are only 2^5 - 6 = 26 relevant proper
subsets (size 3 or 4), each a single cheap CPU forward pass through the
already-loaded HODDI model - no training, no new model.

Two things this can reveal:
  - The warning reduces to a smaller sub-combination ("really just Warfarin +
    Amiodarone + Aspirin - the other drugs aren't adding risk").
  - A genuine higher-order effect: no subset alone is elevated, only the full
    set - that's a real finding the pairwise view cannot show at all.

This is a model counterfactual over the single trained HODDI model, not a
stability-tested causal claim - framed that way in every output string.
"""
from __future__ import annotations

from itertools import combinations


def build_certificate(
    drug_names: list[str],
    name_to_id: dict[str, str],
    fp_lookup: dict,
    hoddi_model,
    normalize,
) -> dict | None:
    resolved: list[tuple[str, str]] = []  # (name, drugbank_id)
    for name in drug_names:
        did = name_to_id.get(normalize(name))
        if did and did in fp_lookup:
            resolved.append((name, did))

    if len(resolved) < 4:
        # Need at least one proper subset of size >= 3 to say anything a
        # minimal-subset analysis could add beyond the full-set result itself.
        return None

    resolved = resolved[:5]  # HODDI trained on sets of 3-5, same cap as predict_hoddi_signal
    names = [n for n, _ in resolved]
    ids = [i for _, i in resolved]
    n = len(resolved)

    full_prob = hoddi_model.predict_proba(ids, fp_lookup)
    if full_prob < 0.5:
        return {
            "applicable": False,
            "reason": "The combination signal for this regimen was not elevated, so there is no "
                      "multi-drug warning to explain with a subset certificate.",
        }

    def prob_for(idx_subset: tuple[int, ...]) -> float:
        return hoddi_model.predict_proba([ids[i] for i in idx_subset], fp_lookup)

    # All proper subsets of size 3..n-1, smallest first.
    elevated_subsets: list[dict] = []
    for size in range(3, n):
        for combo in combinations(range(n), size):
            p = prob_for(combo)
            if p >= 0.5:
                elevated_subsets.append({
                    "drugs": [names[i] for i in combo],
                    "probability": round(p, 3),
                    "size": size,
                })

    # Keep only inclusion-minimal elevated subsets (drop any that fully contain a smaller one already found).
    elevated_subsets.sort(key=lambda s: s["size"])
    minimal: list[dict] = []
    for s in elevated_subsets:
        s_set = set(s["drugs"])
        if not any(set(m["drugs"]).issubset(s_set) for m in minimal):
            minimal.append(s)

    # When many same-size subsets are all independently elevated (a genuinely entangled
    # regimen, not a rare edge case - e.g. several interacting psychoactive drugs), showing
    # every one is noisy. Surface the strongest few and report an honest count of the rest.
    minimal.sort(key=lambda s: -s["probability"])
    total_minimal_found = len(minimal)
    minimal_display = minimal[:5]

    # Per-drug removal impact: does dropping this one drug (keeping the rest) still trigger the warning?
    removal_impact = []
    for i, name in enumerate(names):
        remaining = tuple(j for j in range(n) if j != i)
        if len(remaining) < 3:
            continue
        p_without = prob_for(remaining)
        removal_impact.append({
            "drug": name,
            "probability_without_this_drug": round(p_without, 3),
            "still_elevated_without_it": p_without >= 0.5,
            "change": round(p_without - full_prob, 3),
        })
    removal_impact.sort(key=lambda r: r["change"])  # most risk-reducing removal first

    if total_minimal_found == 1:
        certificate_type = "reducible"
        summary = (
            f"This warning is explained by a smaller combination: "
            f"{' + '.join(minimal[0]['drugs'])}. The other drug"
            f"{'s' if n - minimal[0]['size'] > 1 else ''} in the regimen "
            f"{'do' if n - minimal[0]['size'] > 1 else 'does'} not materially add to this signal."
        )
    elif total_minimal_found > 1:
        certificate_type = "entangled"
        summary = (
            f"{total_minimal_found} different {minimal[0]['size']}-drug combinations from this "
            f"regimen each independently trigger the signal - the risk isn't isolated to one "
            f"specific combination, it's spread across much of this regimen. "
            f"Strongest: {' + '.join(minimal[0]['drugs'])}."
        )
    else:
        certificate_type = "higher_order"
        summary = (
            f"No smaller combination of these {n} drugs triggers this warning on its own - "
            f"it appears to require all {n} drugs together. This is a genuine higher-order "
            f"effect the pair-by-pair review cannot show."
        )

    return {
        "applicable": True,
        "certificate_type": certificate_type,
        "full_regimen_probability": round(full_prob, 3),
        "summary": summary,
        "minimal_elevated_subsets": minimal_display,
        "total_minimal_subsets_found": total_minimal_found,
        "removal_impact": removal_impact,
        "caveat": (
            "This is a model counterfactual over a single trained model, not a validated causal "
            "or clinical claim - it shows what this model's signal depends on, not medical advice "
            "to discontinue any specific medication."
        ),
    }
