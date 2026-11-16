# Unit 4: Clinical text (T10 - T12)

`notes_data.py` generates synthetic notes across 6 specialties with gold annotations (entity spans, negation, dose, frequency,
BP, HR, primary diagnosis) recorded by construction, so every method can be scored exactly. Drugs follow real naming stems.

- `t10_text_classification_clustering.py`: TF-IDF + Naive Bayes / logistic regression / linear SVM; k-means with and without boilerplate removal.
- `t11_information_extraction_ner.py`: regex rules (v1 then v2), dictionary NER, learned BIO tagger, NegEx-style negation; tested on drugs never seen in training.
- `t12_ranking_disambiguation.py`: TF-IDF vs BM25 ranking (P@10, MAP, nDCG), TextRank key terms, word-sense disambiguation of RA / MS / PT / cold / discharge.

Scores near 1.0 reflect templated text, not real clinical notes.
