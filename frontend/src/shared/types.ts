export type Variant = "vulnerable" | "secure";

export type User = {
  id: number;
  username: string;
  role: string;
  balance_cents: number;
};

export type Movement = {
  id: number;
  sender: string;
  recipient: string;
  amount_cents: number;
  concept: string;
  created_at: string;
};

export type WalletMeta = {
  variant: Variant;
};

export type ApiErrorPayload = {
  error?: string;
};

export type ApiResult<T> = {
  data: T;
  status: number;
};

export type Credential = {
  username: string;
  password: string;
  role: string;
};

export type LabStatus = {
  active: boolean;
  needs_reset: boolean;
  active_run_id?: string | null;
  variants: Record<Variant, { url: string }>;
  credentials: Credential[];
  reset_results?: Partial<Record<Variant, { ok: boolean; generation?: number; error?: string }>>;
};

export type LabOutcome =
  | "attack_reproduced"
  | "blocked"
  | "unexpected"
  | "inconclusive";

export type LabEvidence = {
  summary: string;
  request?: unknown;
  before?: unknown;
  after?: unknown;
  screenshots?: string[];
};

export type LabResult = {
  case_id: string;
  variant: Variant;
  outcome: LabOutcome;
  evidence: LabEvidence;
};

export type LabRun = {
  id: string;
  case_id: string;
  variant?: Variant;
  status: string;
  error?: string | null;
  results: LabResult[];
  current?: { case_id: string; variant: Variant } | null;
};
