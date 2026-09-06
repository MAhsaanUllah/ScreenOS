# Day 1 extraction measurements

Environment: Python 3.11.15, Windows.
Median of five reads per fictional CV, after imports; includes file opening.
Short samples do not establish speed on full-length real CVs.

| Sample | Characters | Median seconds |
| --- | ---: | ---: |
| 01_strong.txt | 440 | 0.000564 |
| 02_python.docx | 290 | 0.018407 |
| 03_documents.pdf | 356 | 0.019569 |
| 04_career_change.txt | 277 | 0.000475 |
| 05_claims_only.docx | 202 | 0.016703 |
| 06_instructions.pdf | 273 | 0.013279 |

Manual review time, screening accuracy and time savings are
not measured. This measures file reading only.
