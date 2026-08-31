from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any

import pandas as pd
from mattergraph.datasets import DeduplicationBasis, MatterGraphDataset
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Lattice, Structure

_ALIASES: dict[str, tuple[str, ...]] = {
  "material_id": ("material_id", "entry_id", "id", "record_id", "immutable_id"),
  "formula": ("formula", "chemical_formula_reduced", "reduced_formula"),
  "reduced_formula": ("reduced_formula", "chemical_formula_reduced", "formula"),
  "elements": ("elements", "element_list", "chemsys_elements"),
  "nelements": ("nelements", "n_elements"),
  "nsites": ("nsites", "n_sites"),
  "structure": ("structure", "structure_json"),
  "immutable_id": ("immutable_id",),
  "functional": ("functional", "xc_functional", "dft_functional"),
  "structure_fingerprint": (
    "structure_fingerprint",
    "entalpic_fingerprint",
    "bawl_id",
    "fingerprint",
  ),
}

_PROPERTY_UNITS = {
  "density": "g/cm^3",
  "bulk_modulus": "GPa",
  "shear_modulus": "GPa",
  "band_gap": "eV",
  "formation_energy_per_atom": "eV/atom",
  "energy_above_hull": "eV/atom",
  "max_force": "eV/Å",
  "energy": "eV",
}

EXAMPLE_NAMES = ("spc-tialn-24",)
_EXAMPLE_RESOURCES = {
  "spc-tialn-24": "spc_real_snapshot.json",
}


class LeMatBulk:
  """Adapter for turning LeMaterial bulk-style records into MatterGraph workflows."""

  @classmethod
  def example(cls, name: str = "spc-tialn-24") -> MatterGraphDataset:
    """Load a checksummed, credential-free LeMaterial example bundled with the package."""
    artifact = deepcopy(_load_example_artifact(name))
    manifest = artifact["manifest"]
    dataset = cls.from_records(
      artifact["records"],
      source_dataset=str(manifest["dataset"]),
      subset=str(manifest["subset"]),
    )
    dataset.metadata["snapshot_manifest"] = manifest
    dataset.metadata["example_name"] = name
    return dataset

  @classmethod
  def from_hf(
    cls,
    *,
    repo_id: str = "LeMaterial/LeMat-Bulk",
    subset: str | None = None,
    split: str = "train",
  ) -> MatterGraphDataset:
    try:
      datasets = import_module("datasets")
    except ImportError as exc:
      msg = (
        "Install the optional `datasets` dependency to load LeMaterial from Hugging Face, "
        "or use LeMatBulk.from_records(...) / LeMatBulk.from_parquet(...)."
      )
      raise ImportError(msg) from exc

    if subset is None:
      dataset = datasets.load_dataset(repo_id, split=split)
    else:
      dataset = datasets.load_dataset(repo_id, name=subset, split=split)
    frame = dataset.to_pandas()
    return cls._dataset_from_frame(
      frame,
      source_dataset=repo_id,
      source_subset=subset or split,
    )

  @classmethod
  def from_parquet(
    cls,
    path: str | Path,
    *,
    source_dataset: str = "LeMaterial/LeMat-Bulk",
    subset: str | None = None,
  ) -> MatterGraphDataset:
    parquet_path = Path(path)
    try:
      frame = pd.read_parquet(parquet_path)
    except ImportError as exc:
      msg = (
        "Reading parquet requires `pyarrow` or `fastparquet`. "
        "Install one of those dependencies or use LeMatBulk.from_records(...)."
      )
      raise ImportError(msg) from exc
    return cls._dataset_from_frame(
      frame,
      source_dataset=source_dataset,
      source_subset=subset or parquet_path.stem,
    )

  @classmethod
  def from_records(
    cls,
    records: list[dict[str, Any]],
    *,
    source_dataset: str = "LeMaterial/LeMat-Bulk",
    subset: str | None = None,
  ) -> MatterGraphDataset:
    return cls._dataset_from_frame(
      pd.DataFrame(records),
      source_dataset=source_dataset,
      source_subset=subset or "local_records",
    )

  @classmethod
  def _dataset_from_frame(
    cls,
    frame: pd.DataFrame,
    *,
    source_dataset: str,
    source_subset: str | None,
  ) -> MatterGraphDataset:
    normalized = frame.copy(deep=True)
    for target, aliases in _ALIASES.items():
      cls._populate_standard_column(normalized, target, aliases)
    if "structure" not in normalized.columns:
      normalized["structure"] = normalized.apply(_reconstruct_structure, axis=1)
    else:
      missing = normalized["structure"].isna()
      if missing.any():
        normalized.loc[missing, "structure"] = normalized.loc[missing].apply(
          _reconstruct_structure, axis=1
        )

    if "material_id" not in normalized.columns or "formula" not in normalized.columns:
      msg = "LeMatBulk records must provide a material identifier and formula-compatible field"
      raise ValueError(msg)

    basis = cls._resolve_deduplication_basis(normalized, source_subset)
    metadata = {
      "strict_guardrails": True,
      "default_deduplication_basis": basis,
      "provenance_fields": [
        "source_dataset",
        "source_subset",
        "functional",
        "immutable_id",
        "structure_fingerprint",
      ],
      "property_columns": cls._property_columns(normalized),
      "property_units": {
        column: unit
        for column, unit in _PROPERTY_UNITS.items()
        if column in normalized.columns
      },
    }
    return MatterGraphDataset(
      normalized,
      source_dataset=source_dataset,
      source_subset=source_subset,
      metadata=metadata,
    )

  @staticmethod
  def _populate_standard_column(
    frame: pd.DataFrame,
    target: str,
    aliases: tuple[str, ...],
  ) -> None:
    if target in frame.columns:
      return
    for alias in aliases:
      if alias in frame.columns:
        frame[target] = frame[alias]
        return

  @staticmethod
  def _resolve_deduplication_basis(
    frame: pd.DataFrame,
    source_subset: str | None,
  ) -> DeduplicationBasis:
    subset = (source_subset or "").lower()
    if "immutable_id" in frame.columns and frame["immutable_id"].notna().all():
      if "unique" in subset or "dedup" in subset:
        return "immutable_id"
    if "structure_fingerprint" in frame.columns and frame["structure_fingerprint"].notna().all():
      return "structure_fingerprint"
    return "unknown"

  @staticmethod
  def _property_columns(frame: pd.DataFrame) -> list[str]:
    reserved = {
      "material_id",
      "formula",
      "reduced_formula",
      "elements",
      "nelements",
      "nsites",
      "structure",
      "immutable_id",
      "functional",
      "structure_fingerprint",
      "provenance",
      "field_provenance",
      "forces",
      "lattice_vectors",
      "cartesian_site_positions",
      "species_at_sites",
      "entalpic_fingerprint",
      "source_reduced_formula",
      "last_modified",
    }
    columns: list[str] = []
    for column in frame.columns:
      if column in reserved:
        continue
      non_null = frame[column].dropna()
      if non_null.empty:
        continue
      if non_null.map(lambda value: isinstance(value, (int, float, str, bool))).all():
        columns.append(column)
    return columns


@lru_cache(maxsize=len(EXAMPLE_NAMES))
def _load_example_artifact(name: str) -> dict[str, Any]:
  resource_name = _EXAMPLE_RESOURCES.get(name)
  if resource_name is None:
    available = ", ".join(EXAMPLE_NAMES)
    msg = f"unknown LeMatBulk example {name!r}; available examples: {available}"
    raise ValueError(msg)
  resource = files("mattergraph_connectors").joinpath("resources", resource_name)
  artifact = json.loads(resource.read_text(encoding="utf-8"))
  if not isinstance(artifact, dict) or not isinstance(artifact.get("records"), list):
    msg = f"bundled LeMatBulk example {name!r} is malformed"
    raise ValueError(msg)
  return artifact


def _reconstruct_structure(row: pd.Series) -> CrystalStructure | None:
  lattice = row.get("lattice_vectors")
  cartesian = row.get("cartesian_site_positions")
  species = row.get("species_at_sites")
  if not isinstance(lattice, (list, tuple)):
    return None
  if not isinstance(cartesian, (list, tuple)) or not isinstance(species, (list, tuple)):
    return None
  if len(cartesian) != len(species):
    return None
  try:
    structure = Structure(
      Lattice(lattice),
      list(species),
      list(cartesian),
      coords_are_cartesian=True,
      to_unit_cell=True,
    )
  except (TypeError, ValueError):
    return None
  return CrystalStructure.from_pymatgen(structure)
