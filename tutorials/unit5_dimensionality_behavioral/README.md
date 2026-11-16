# Unit 5: Dimensionality reduction and behavioural factors in adult weight (T13 - T15)

- `t13_dimensionality_reduction.py`: PCA, LDA, t-SNE, Isomap on the real Wisconsin breast-cancer data (scikit-learn), compared on kNN accuracy, silhouette and trustworthiness; accuracy vs number of components with the reduction fitted inside each CV fold.
- `weight_data.py`: synthetic adults (n = 2,111) with the column schema of the public obesity-and-eating-habits study; BMI generated from a stated model (documented in the file) so recovered effects can be checked.
- `t14_behavioral_factors_part1.py`: exploration and inference (Kruskal-Wallis, eta-squared, Benjamini-Hochberg, Cramer's V, VIF, interaction heat-map).
- `t15_behavioral_factors_part2.py`: leakage check, linear vs non-linear models, permutation importance, partial dependence, behaviour phenotypes.
