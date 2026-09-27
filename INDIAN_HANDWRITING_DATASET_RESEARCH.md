# Top-line answer

**No — as of 27 September 2026, I could not verify any publicly downloadable dataset that contains enough real Indian doctors’ handwritten instances of specific Indian drug names to train PolyGuard’s five-class classifier.**

There are now several relevant Indian collections, including two genuinely strong ones, but their images have **not been publicly released**. The publicly accessible alternatives are either:

- full-page prescriptions without trustworthy word-level labels;
- synthetic handwriting;
- generic handwriting;
- Indian drug-name text catalogues without handwriting; or
- prescription datasets from Bangladesh or other countries.

## Closest verified results

| Dataset/source | What it contains | Access and licence | Suitability |
|---|---|---|---|
| **RxScribe Bench** | 200 real, de-identified Indian outpatient prescriptions, double-annotated and adjudicated; full-page images with structured field-level ground truth | The [paper](https://arxiv.org/abs/2609.13280) and [benchmark report](https://zstate.ai/research/rxscribe-bench) are public. I found no image archive, Hugging Face dataset, GitHub repository, DOI deposit or download link. The paper says the prescriptions were collected directly from clinics rather than an existing public dataset. | **Exact target domain, but not accessible.** Even if released, it is a full-page extraction benchmark rather than ready-made five-class word crops. |
| **Google Research weakly supervised prescription collection** | 9,645 handwritten prescription images from 117 doctors, with an unordered list of medicines per image | Described in the [2023 paper](https://arxiv.org/abs/2306.06823). No dataset, image archive, GitHub repository or public request procedure was found. | **Highly relevant but private.** Labels are weak, not cropped-word class labels. |
| **Razdan et al., CNN–BiLSTM with lexicon search** | Indian prescriptions obtained from a prescription-auditing organisation; prescriptions were annotated and segmented into word images | Described in the [ICCCNT 2023 paper record/PDF mirror](https://www.researchgate.net/publication/375414751_Recognition_of_Handwritten_Medical_Prescription_using_CNN_Bi-LSTM_With_Lexicon_Search), DOI [10.1109/ICCCNT56998.2023.10307451](https://doi.org/10.1109/ICCCNT56998.2023.10307451). No released data or code located. | **Conceptually an excellent match, but unavailable.** |
| **Handwritten Medical Prescriptions Collection** | 129 full prescription images. A Hugging Face derivative exposes all 129 and shows that some are Indian—examples include Sir Ganga Ram Hospital, Fortis Delhi, Rajiv Gandhi Cancer Institute and a Kolkata hospital—but others come from the Philippines and the US | Original [Kaggle collection](https://www.kaggle.com/datasets/mehaksingal/illegible-medical-prescription-images-dataset); inspectable [Hugging Face derivative](https://huggingface.co/datasets/akansha2k2/prescription_dataset). The Kaggle archive is about 28.4 MB. The derivative has machine-generated OCR/captions, often empty or plainly erroneous. Dataset licence was not clearly declared. | **Real and accessible, but not a usable supervised classifier dataset.** Mixed geography, full pages, no verified drug-word crops or class labels. It might supply a handful of manually relabelled validation examples after privacy and licence review. |
| **ShubhamRaorane classifier prototype** | Two labels: **Hairbless** and **Lobate**. Training examples were manually written by the project team to resemble two medicine words seen in household prescriptions; real prescription snippets were reserved for demonstration/testing | Public [GitHub repository](https://github.com/ShubhamRaorane/Handwritten-Prescription-Medicine-Recognition), MIT licence | **Very relevant precedent for PolyGuard’s scoped approach, but not a real-doctor training dataset.** It independently demonstrates the same realistic fallback: create a small, closed-vocabulary corpus. |
| **Medical Prescription Handwritten Words** | 46 cropped images, with examples such as Amoxicillin, Pain, Fever, Tablet and Syrup | [Hugging Face](https://huggingface.co/datasets/avi-kai/Medical_Prescription_Handwritten_Words), MIT licence, 422 KB | **Too small and provenance is undocumented.** No evidence that the writers are Indian doctors or that the five target Indian brands are included. |
| **RxHandBD** | 5,578 real cropped prescription words, 1,559 unique transcriptions, including medicines and medical terms; 128×128 images with a CSV transcription map | Directly downloadable from [Mendeley Data](https://data.mendeley.com/datasets/dsb5r6vskg/1), 31.7 MB ZIP, CC BY 4.0 | **Well structured but Bangladeshi**, from Bangladesh University of Business and Technology. Useful for transfer learning or OCR pretraining, not evidence for Indian brand spellings. |
| **MedOCR-Vision** | 2,462 images, but only 1,000 are “prescriptions”; the remainder includes lab reports, OMR documents, invoices and receipts | [Hugging Face](https://huggingface.co/datasets/naazimsnh02/medocr-vision-dataset), 512 MB, MIT | **False positive for this task.** Its prescription portion comes from [chinmays18/medical-prescription-dataset](https://huggingface.co/datasets/chinmays18/medical-prescription-dataset), whose own description explicitly calls the prescriptions **synthetic**. |
| **Generic Indian handwriting corpora** | For example, IIIT-INDIC-HW-WORDS contains 872,000 handwritten word instances from 135 writers in Indic scripts | [IIIT-Hyderabad project](https://cvit.iiit.ac.in/research/projects/cvit-projects?start=50); a Hindi conversion is on [Hugging Face](https://huggingface.co/datasets/c3rl/IIIT-INDIC-HW-WORDS-Hindi) | **Category (b), not medicine handwriting.** Mostly Indic-script general vocabulary; Indian prescriptions and brand names are commonly written in Latin script. Useful only for generic visual pretraining in matching scripts. |

## Kaggle findings

Beyond the already-known Bangladesh dataset and the unverified `kalashsh` listing, the only repeatedly verifiable prescription-image collection was the 129-image **Handwritten Medical Prescriptions Collection** above.

Important limitations:

- It contains full prescription pages, not labelled drug-name crops.
- Available examples demonstrate mixed countries rather than an Indian-only collection.
- No reliable drug list or human-authored transcription accompanies it.
- The apparently annotated Hugging Face copy uses generated OCR and captions. Several records have empty medicine lists even when handwriting is present, so these labels should not be treated as ground truth.
- I could not establish a reusable dataset licence.

Searches also surfaced numerous Kaggle notebooks and competition write-ups, but these reuse the same 129-image collection, the Bangladesh word dataset, or synthetic prescriptions. They do not introduce a new Indian handwritten corpus.

## Academic and institutional evidence

The academic search confirms that relevant private Indian data exists:

- **RxScribe Bench:** 200 real Indian outpatient prescriptions. No public download was linked from the paper, project site, Hugging Face, GitHub, Zenodo or Mendeley.
- **Google Research:** 9,645 images from 117 doctors. The paper describes the data but provides no release.
- **Razdan et al.:** prescriptions sourced across India and segmented into words, but obtained through a prescription-auditing organisation and not released.
- Several recent Indian conference papers report “custom” or “self-created” prescription datasets without publishing images, annotations or a repository. Those are descriptions of private experimental data, not accessible datasets.

This distinction matters: **a paper reporting experiments on a dataset is not a dataset release.**

## Government and public-sector search

No prescription-image training corpus was found on:

- data.gov.in;
- ICMR or the Pharmacovigilance Programme of India;
- National Health Authority/ABDM resources;
- Smart India Hackathon dataset links; or
- Indian public institutional repositories found through these searches.

The [ABDM Hackathon page](https://abdm.gov.in/hackathon) did include a challenge for structured entry from handwriting, but its suggested resources were generic material such as MNIST and a Bengali medical dataset—not Indian handwritten prescriptions. Public prescription-audit studies on Zenodo contain papers and aggregate statistics, not the underlying patient prescription images.

That absence is unsurprising because prescription scans combine sensitive health information, clinician identifiers and difficult consent/de-identification requirements.

## Printed/text-only Indian resources

These are useful for constructing the **five-name vocabulary and spelling normalisation**, but they cannot train handwriting appearance:

- [1-800-LLMs/indian-medicines](https://huggingface.co/datasets/1-800-LLMs/indian-medicines) — Indian medicine-name CSV, no images.
- [MedScript Drug Dataset](https://huggingface.co/datasets/hashan-7/medscript-drug-dataset) — 69,032 normalised medicine-name strings for OCR correction; no handwriting and not specifically Indian.
- Kaggle Indian medicine catalogues contain large brand/generic/manufacturer tables, but are text or product metadata rather than prescription handwriting.

These belong to category **(c)**: useful lexicons and post-processing resources, not handwriting training data.

# Recommended fallback

For only five target names, **self-collection is the most defensible solution**.

1. Ask 25–50 consenting people—ideally including medical students, clinicians or pharmacists—to write each target name 5–10 times at normal prescription speed. That yields roughly 625–2,500 real word images.
2. Collect on paper with different pens, lighting, phone cameras, slants and abbreviation habits. Record a writer ID so train/validation/test splits can be **writer-disjoint**.
3. Crop and label the five words, but also add an **unknown/reject class**. A forced five-way prediction is unsafe when the image is blank, badly cropped or contains another medicine.
4. Apply conservative augmentation: small rotation, perspective changes, blur, brightness/contrast variation, compression, ink fading and mild elastic distortion. Do not let augmented copies of one original cross dataset splits.
5. Treat synthetic handwriting as augmentation, not as the test set. Suitable open tools include:
   - [Handwriting Transformers](https://arxiv.org/abs/2104.03964) for few-shot style-conditioned generation;
   - [WordStylist](https://github.com/koninik/WordStylist), which can generate arbitrary word images in learned writer styles;
   - [DiffusionPen](https://arxiv.org/abs/2409.06065);
   - [ScrabbleGAN](https://github.com/amzn/convolutional-handwriting-gan);
   - [GANwriting](https://github.com/omni-us/research-GANwriting).

For a course-project proof of concept, the Bangladesh cropped-word datasets can still validate the architecture and training pipeline. The report should explicitly state that this demonstrates **closed-vocabulary handwritten medicine classification**, while the final five Indian names require locally collected real samples.

**Defensible project conclusion:** no suitable public Indian handwritten drug-name training corpus was found; PolyGuard should build a small consented dataset for its exact five labels, use synthetic generation only to enlarge style variation, and evaluate on held-out real writers.