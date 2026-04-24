"""Example: show reduced formula normalization via pymatgen compositions."""

from mattergraph.normalization.formulas import reduced_formula, standardize_formula

raw = "Fe2+2 O3-2"
print("reduced", reduced_formula(raw))
print("std", standardize_formula(raw))
