"""Example: pull a handful of Materials Project summaries (requires ``MP_API_KEY``)."""

import os
import sys

if not os.environ.get("MP_API_KEY") and not os.environ.get("MATERIALS_PROJECT_API_KEY"):
  print("Set MP_API_KEY first.", file=sys.stderr)
  sys.exit(0)

from mattergraph_connectors import MaterialsProjectConnector  # noqa: E402

c = MaterialsProjectConnector()
mats = c.fetch(elements=["Fe"], material_ids=None, chunk_size=5, num_chunks=1)
for m in mats[:3]:
  print(m.material_id, m.formula, m.get_numeric("formation_energy_per_atom"))
