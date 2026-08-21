import { Scale } from "lucide-react";
import type { JudgeChip } from "../types";

const PASS_THRESHOLD = 0.5;

const BELOW_BADGE = "badge badge-sm badge-warning gap-1";
const AT_OR_ABOVE_BADGE = "badge badge-sm badge-ghost gap-1";

export default function JudgeChips({
  judge,
  note,
}: {
  judge: JudgeChip[];
  note: string | null;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Scale aria-hidden="true" className="size-4" />
        <h2 className="text-xs font-semibold tracking-wide uppercase">Semantic judge</h2>
        <span className="badge badge-sm badge-ghost">advisory — never gates</span>
      </div>
      {note !== null ? (
        <p className="text-xs opacity-70">{note}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {judge.map((chip) => {
            const below = chip.score < PASS_THRESHOLD;
            return (
              <li key={chip.dimension} className="flex flex-wrap items-baseline gap-2">
                <span className={below ? BELOW_BADGE : AT_OR_ABOVE_BADGE}>
                  <span className="tabular-nums">{chip.score.toFixed(2)}</span>
                  {below ? " below threshold" : ""}
                </span>
                <span className="font-mono text-xs font-semibold">{chip.dimension}</span>
                <span className="text-xs opacity-80">{chip.rationale}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
