export type RunStatus = "ok" | "failed" | "diverged";

export interface RunSummary {
  run_id: string;
  scenario: string;
  channel: string;
  model: string;
  agent_version: string;
  recorded_at: string;
  turn_count: number;
}

export interface ToolCallView {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface TurnSide {
  assistant_text: string;
  tool_calls: ToolCallView[];
}

export interface TurnDiff {
  index: number;
  user_text: string;
  baseline: TurnSide;
  current: TurnSide | null;
  text_changed: boolean;
  tools_changed: boolean;
  changed: boolean;
}

export interface InvariantChip {
  name: string;
  passed: boolean;
  detail: string;
}

export interface JudgeChip {
  dimension: string;
  score: number;
  rationale: string;
}

export interface DivergenceView {
  turn_index: number;
  kind: "llm" | "tool";
  summary: string;
}

export interface DiffView {
  run_id: string;
  scenario: string;
  candidate: string | null;
  status: RunStatus;
  channel: string;
  model: string;
  agent_version: string;
  recorded_at: string;
  turns: TurnDiff[];
  divergences: DivergenceView[];
  invariants: InvariantChip[];
  judge: JudgeChip[];
  judge_note: string | null;
  changed_turn_indexes: number[];
}
