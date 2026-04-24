from enum import Enum


class PropertyMethod(str, Enum):
  DFT = "dft"
  EXPERIMENTAL = "experimental"
  MODEL_PREDICTED = "model_predicted"
  UNKNOWN = "unknown"
