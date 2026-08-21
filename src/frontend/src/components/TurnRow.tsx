import { ArrowLeftRight } from "lucide-react";
import ToolCalls from "./ToolCalls";
import type { TurnDiff, TurnSide } from "../types";

const CHANGED_SECTION = "rounded-box border p-4 border-warning bg-warning/5";
const UNCHANGED_SECTION = "rounded-box border p-4 border-base-300";
const CHANGED_BADGE = "badge badge-sm badge-warning gap-1";
const UNCHANGED_BADGE = "badge badge-sm badge-ghost";

function Side({ label, side }: { label: string; side: TurnSide | null }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <h4 className="text-xs font-semibold tracking-wide uppercase opacity-60">{label}</h4>
      {side === null ? (
        <p className="text-xs opacity-60 italic">not replayed — run diverged earlier</p>
      ) : (
        <>
          <p className="text-sm">{side.assistant_text}</p>
          <ToolCalls calls={side.tool_calls} />
        </>
      )}
    </div>
  );
}

export default function TurnRow({ turn }: { turn: TurnDiff }) {
  return (
    <section
      id={`turn-${turn.index}`}
      aria-labelledby={`turn-${turn.index}-heading`}
      className={turn.changed ? CHANGED_SECTION : UNCHANGED_SECTION}
    >
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h3 id={`turn-${turn.index}-heading`} className="font-mono text-sm font-semibold">
          turn <span className="tabular-nums">{turn.index}</span>
        </h3>
        {turn.changed ? (
          <span className={CHANGED_BADGE}>
            <ArrowLeftRight aria-hidden="true" className="size-3" />
            divergent
            {turn.text_changed ? " · text" : ""}
            {turn.tools_changed ? " · tool calls" : ""}
          </span>
        ) : (
          <span className={UNCHANGED_BADGE}>identical</span>
        )}
      </header>
      <p className="mb-3 text-sm">
        <span className="text-xs font-semibold tracking-wide uppercase opacity-60">user </span>
        {turn.user_text}
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Side label="baseline" side={turn.baseline} />
        <Side label="current" side={turn.current} />
      </div>
    </section>
  );
}
