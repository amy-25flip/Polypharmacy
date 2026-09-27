# Top-line answer

**No publicly accessible system is proven to read genuinely messy handwritten prescriptions reliably enough to justify replacing Gemini outright.** Purpose-trained research models can outperform general multimodal models on their own datasets, but the strongest results rely on large private/simulated datasets, narrow drug vocabularies, cropped words, or costly fine-tuning—and do not establish safe accuracy on unseen real Indian prescriptions.

For PolyGuard, the best course is to:

1. Keep Gemini for convenient first-pass extraction.
2. Add conservative confidence/abstention and drug-catalog matching.
3. Require the existing doctor-confirmation gate.
4. Optionally run a small benchmark of one prescription-specific open model and one commercial API—but switch only if they materially improve accuracy on PolyGuard’s own messy-prescription set.

## 1. Purpose-built research, models, and datasets

### The strongest directly relevant result: MIRAGE

The 2024 Indian study **MIRAGE** fine-tuned Qwen-VL, LLaVA 1.6, and Idefics2 on **743,118 simulated medical-record images written by 1,133 Indian doctors**, covering 21,075 medicine brands. Its best fine-tuned Idefics2 model reported about **82% F1/accuracy for medicine names and dosages**.

Crucially, the same paper tested unfine-tuned general models on its data:

| Model, without domain fine-tuning | Reported F1 |
|---|---:|
| Gemini 1.5 Pro | 5.53% |
| GPT-4o | 7.57% |
| LLaVA 1.6 | 2.00% |
| Fine-tuned Idefics2 | about 82% |

This is good evidence that sufficient prescription-specific training can greatly outperform zero-shot general MLLMs. It is **not an immediately deployable solution**, however:

- The records were simulated rather than ordinary patient-uploaded photos.
- Only 100 records were publicly released.
- Training required seven A6000 GPUs for nine days.
- Performance fell on rare medications.
- Extracting all fields was substantially worse than extracting medicine names alone.

[MIRAGE paper](https://arxiv.org/abs/2410.09729)

### Other prescription-specific research

A 2024 Pakistan study combined Mask R-CNN region detection, TrOCR, and drug-database matching, trained on approximately **1,000 prescriptions from 50 doctors**. It reports **1.4% character error rate**, but that figure is not equivalent to “98.6% correct prescriptions”: it is reported on component/standard benchmarks and does not establish end-to-end accuracy on new photographed prescriptions. The dataset and production model do not appear to be offered as a supported public API. [Paper](https://arxiv.org/abs/2412.18199)

Earlier systems commonly report roughly 65–90%, but frequently use:

- Tablet/stylus handwriting rather than photographed paper;
- Cropped individual medicine words;
- A small fixed vocabulary;
- Few writers or locally collected private data.

For example, a 2022 online-handwriting system recognized only 24 medicine names from two writers. That is not comparable to arbitrary prescription photographs. [Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9509260/)

### Public datasets are small and not a robust universal benchmark

The most usable public dataset is the **Doctor’s Handwritten Prescription BD dataset**:

- 4,680 cropped medicine-name images;
- 78 drug classes;
- Bangladesh-specific vocabulary;
- Already segmented into individual words.

It is useful for teaching classification, but cannot train or validate a full-page Indian prescription reader with thousands of possible brands. [Dataset description](https://www.kaggle.com/dsv/8378585)

MIRAGE released only a 100-prescription subset of its much larger collection. Consequently, there still is no large, broadly accepted public benchmark representing messy, phone-photographed Indian prescriptions.

### Open-source model worth testing—but not trusting yet

A recent Apache-licensed Hugging Face model, **medical-prescription-ocr-india**, fine-tunes Qwen2.5-VL-3B on 1,969 Indian prescription samples and emits structured JSON. Its own model card warns that illegible handwriting can yield incomplete or incorrect drugs and requires professional verification. More importantly, it publishes no convincing independent evaluation showing that it beats current Gemini on difficult unseen prescriptions. [Model card](https://huggingface.co/KushagraWadhwa/medical-prescription-ocr-india)

It is the most practical specialized model for a small experiment, but not yet a validated upgrade.

## 2. Commercial document-AI products

| Product | Handwritten-prescription specialization? | Indicative cost/free access | Assessment |
|---|---|---|---|
| **Google Document AI Enterprise OCR** | **No.** General document and handwriting OCR; no prescription processor appears in Google’s processor catalog. A Custom Extractor can be trained, but requires PolyGuard’s own labeled data. | First 1,000 OCR pages/month free; then about **$1.50/1,000 pages**. Custom extraction about **$30/1,000 pages**. | Cheap to test, but unlikely to solve illegible drug names better than Gemini without custom data. [Processors](https://docs.cloud.google.com/document-ai/docs/processors-list), [pricing](https://cloud.google.com/products/document-ai/pricing) |
| **Azure AI Document Intelligence** | **No.** Its Read model recognizes generic handwriting. The healthcare-specific prebuilt model is for **US health-insurance cards**, not prescriptions. | F0: **500 pages/month**, with two-page/file and 4 MB limits. Read OCR is approximately **$1.50/1,000 pages**, region-dependent. | Good generic OCR baseline, not a medical-handwriting model. [Model list](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/model-overview?view=doc-intel-4.0.0), [pricing](https://azure.microsoft.com/en-us/pricing/details/ai-document-intelligence/) |
| **AWS Textract** | **No.** General printed-text and handwriting OCR. | Three-month trial: 1,000 Detect Text pages/month; thereafter about **$1.50/1,000 pages**. | Affordable, but not prescription-specialized. [Pricing](https://aws.amazon.com/textract/pricing/) |
| **AWS Comprehend Medical** | Medical NLP, but **not OCR**. It extracts medications, strengths and frequencies only after usable text exists. | First month: 85,000 text units; thereafter NERe begins around **$0.01 per 100 characters**, which is expensive compared with OCR. | Cannot recover characters Textract misreads. Indian brand vocabulary may also be a mismatch. [Documentation](https://docs.aws.amazon.com/comprehend-medical/latest/dev/comprehendmedical-welcome.html), [pricing](https://aws.amazon.com/comprehend/medical/pricing/) |
| **Google healthcare/medical language models** | Specialized for medical reasoning and text, not a public handwritten-prescription OCR processor. | Model/API dependent. | Medical knowledge does not create visual information absent from illegible strokes. |

None of the three major clouds sells a prebuilt “Indian handwritten prescription” model comparable to its invoice, receipt, or ID processors.

### Prescription-specific commercial APIs

Vendors such as **Veryfi, PrescriptoAI, Medisha, RxScan, Fleming, and eKiosk Health** now advertise prescription OCR. Some offer free trials; PrescriptoAI advertises 100 free calls/month. However:

- Published claims such as “99%+ accuracy” generally lack a disclosed dataset, legibility distribution, error metric, or independent evaluation.
- Some services may simply wrap a general VLM plus drug-database normalization.
- Public pricing, data-retention details, and Indian prescription coverage are often incomplete.
- A high field-average can hide catastrophic drug-name or dose errors.

These are reasonable **benchmark candidates**, not evidence-backed replacements. Examples: [PrescriptoAI](https://www.prescriptoai.com/), [Medisha preview](https://ocrapi.medisha.com/api/Index), [Veryfi](https://www.veryfi.com/medical-prescription-list-ocr-api/).

Google also demonstrated a pharmacist-assisted handwriting-decoding prototype for Google Lens in 2022, but it was not released as a public product or API. [Contemporary report](https://techcrunch.com/2022/12/18/google-can-now-decode-doctors-bad-handwriting/)

## 3. What pharmacies appear to do internally

The evidence supports a **machine-assisted, human-verified workflow**, not autonomous transcription.

- Netmeds explicitly says an uploaded prescription is handled by a pharmacist, who may call the customer to confirm the medicines. [Netmeds assisted ordering](https://www.netmeds.com/faq/assisted-ordering)
- Tata 1mg’s terms require the third-party pharmacy to validate the prescription and cancel orders when discrepancies are found. [Tata 1mg terms](https://www.1mg.com/tnc/)
- PharmEasy says prescriptions are verified by licensed pharmacists/retail pharmacies before dispensing. [Order process](https://pharmeasy.in/order-process-guide)
- Practo sends the image and order to the pharmacy, which verifies them. [Practo terms](https://www.practo.com/order/terms)

A particularly informative 2023 industry paper on an Indian medicine-ordering application describes:

- AWS Textract for OCR;
- LayoutLMv2, dictionaries and layout signals for field extraction;
- A proprietary pharmacy catalog for fuzzy candidate matching;
- Human-created ground truth and a pharmacist-processing flow.

But it explicitly covers **mostly or fully printed prescriptions**, not difficult handwriting. Its system returns the top three candidate products for safety rather than treating a single OCR result as authoritative. [ACL industry paper](https://aclanthology.org/2023.acl-industry.76.pdf)

Thus, the industry advantage is largely proprietary catalogs, customer/order context, trained pharmacists and large private feedback datasets—not a magic handwriting API.

## 4. Recent comparisons of general MLLMs and specialized models

There are two directly relevant findings:

1. **MIRAGE (2024)** compared Gemini 1.5 Pro and GPT-4o with domain-fine-tuned VLMs on prescription handwriting. Fine-tuning produced a very large improvement, but required a huge private dataset and substantial compute. This is the clearest specialized-versus-general comparison.

2. **RxScribe Bench (September 2026)** evaluates frontier VLMs on real Indian outpatient prescriptions using separate correctness, hallucination, engagement and robustness measures. Its top-line conclusion is that **no single model wins across all four dimensions**. That reinforces the need to measure dangerous fabrications separately from ordinary transcription mistakes. It does not establish a universally reliable model. [RxScribe Bench](https://arxiv.org/abs/2609.13280)

I found no strong peer-reviewed comparison showing that an off-the-shelf conventional OCR service or publicly downloadable specialized model consistently beats current Gemini/Claude/GPT-class vision models on genuinely messy, unseen Indian prescriptions.

# Recommendation for PolyGuard

**Do not replace Gemini with Google Document AI, Azure Document Intelligence, or AWS Textract/Comprehend Medical.** They are affordable, but none is specialized for handwritten prescriptions, and adding them would increase complexity without evidence of a meaningful accuracy improvement.

A proportionate plan is:

- Retain Gemini for first-pass JSON extraction.
- Make “unable to read confidently” an explicitly preferred result; instruct it never to infer a medicine merely because it is pharmacologically plausible.
- Validate extracted names against a curated Indian drug/brand catalog, but present close matches as candidates—not automatic corrections.
- Require confirmation of every medicine, strength, frequency and duration.
- Visually pair each proposed medicine with the relevant image crop where possible.
- Block interaction checking until confirmation is complete.
- Describe the feature as **assisted transcription**, not prescription recognition.

If the team has one spare day, benchmark the Qwen2.5-VL prescription model and one free commercial trial against a small, manually transcribed set of PolyGuard’s real images. Score exact medicine name, strength, frequency, omissions and hallucinated drugs separately. Do not switch unless the improvement is substantial and repeatable.

The honest conclusion is that **bad handwritten-prescription recognition remains an unsolved, data-dependent safety problem across research and industry**. PolyGuard’s approximately 1-in-5 result on a genuinely messy prescription is not evidence that the team chose the wrong API. The mandatory doctor-confirmation gate is the most important and defensible part of the design.