# OCR evaluation

Facts recovered from the 10 scanned or photographed pages of `eval/ocr/helios_test_report.pdf` (a fictional test document). Measured in the development container; Render's free CPU is slower.

Before the OCR upgrade: 24/38 facts (63%), 21.5 s. The fax, the sideways page and the photo on a text page returned nothing, and the table lost its data rows.

After:

OCR fact recall: 36/38 (95%) · extraction time 31.7 s

| Page | Kind | Facts found |
|---|---|---|
| 8 | Scanned inspection note | 4/4 |
| 9 | Photo on a text page | 3/3 |
| 10 | Stained, skewed invoice | 4/4 |
| 11 | Grainy fax | 5/5 |
| 12 | Phone photo with shadow | 4/4 |
| 13 | Faded photocopy | 3/3 |
| 14 | Handwriting-style notes | 3/4 |
| 15 | Sideways scan | 2/3 |
| 16 | Scanned table | 5/5 |
| 17 | Form with injected text | 3/3 |
