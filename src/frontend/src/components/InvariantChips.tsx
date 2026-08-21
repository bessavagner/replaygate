import { CircleAlert, CircleCheck } from "lucide-react";
import type { InvariantChip } from "../types";

// Complete static class strings — never assembled at render time, so Tailwind
// can see every class it must generate.
const PASS_BADGE = "badge badge-sm badge-success gap-1";
const FAIL_BADGE = "badge badge-sm badge-error gap-1";

export default function InvariantChips({ invariants }: { invariants: InvariantChip[] }) {
  if (invariants.length === 0) {
    return (
      <p className="text-xs opacity-70">
        Invariants were not evaluated — the candidate left the recorded trajectory.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {invariants.map((invariant) => {
        const Icon = invariant.passed ? CircleCheck : CircleAlert;
        return (
          <li key={invariant.name} className="flex flex-wrap items-baseline gap-2">
            <span className={invariant.passed ? PASS_BADGE : FAIL_BADGE}>
              <Icon aria-hidden="true" className="size-3" />
              {invariant.passed ? "pass" : "fail"}
            </span>
            <span className="font-mono text-xs font-semibold">{invariant.name}</span>
            <span className="text-xs opacity-80">{invariant.detail}</span>
          </li>
        );
      })}
    </ul>
  );
}
