"""Example: load a few JARVIS-DFT entries (data may be downloaded on first use)."""

from mattergraph_connectors import JarvisConnector

c = JarvisConnector()
for m in c.fetch(max_records=3):
  print(m.material_id, m.formula)
