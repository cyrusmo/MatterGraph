export type Material = {
  material_id?: string;
  formula?: string;
  [key: string]: unknown;
};

export type RankedRow = {
  material_id?: string;
  score?: number;
  [key: string]: unknown;
};
