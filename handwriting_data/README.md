# Doctor handwriting data collection

Real handwritten samples of 5 disease-specific drug names, collected from
practicing doctors for training a constrained-vocabulary handwriting
classifier (see INDIAN_HANDWRITING_DATASET_RESEARCH.md for why this data
does not exist publicly and had to be collected).

## How to add a new doctor's submission

1. Assign the doctor the next number (Doctor_01, Doctor_02, ...) - keep a
   private mapping of number -> who it is somewhere OUTSIDE this repo if
   you want to remember, never put a real name in this folder or in git.
2. Save their raw photo(s) into `raw_submissions/Doctor_NN.jpg` (create
   that folder if needed - it's gitignored, these images never get
   committed).
3. Once cropped into individual word images, place each crop into the
   matching drug's folder as `Doctor_NN_repeat_M.png`, e.g.
   `Metformin/Doctor_03_repeat_1.png`.

Keeping the doctor number in every filename is what makes a writer-disjoint
train/test split possible later - never mix two doctors' images with the
same filename pattern, and never split one doctor's samples across both
train and test.

## Status

- Doctors contacted: (fill in as you go)
- Doctors responded: 0
- Total samples so far: 0
