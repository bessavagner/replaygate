import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { GitBranch, TriangleAlert } from "lucide-react";
import InvariantChips from "../components/InvariantChips";
import JudgeChips from "../components/JudgeChips";
import StatusBadge from "../components/StatusBadge";
import TurnRow from "../components/TurnRow";
import { fetchRun } from "../api";
import type { DiffView } from "../types";

export default function RunDetail() {
  const { runId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const candidate = searchParams.get("candidate") ?? undefined;
  const [view, setView] = useState<DiffView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setView(null);
    setError(null);
    fetchRun(runId, candidate).then(setView, (e: Error) => setError(e.message));
  }, [runId, candidate]);

  if (error !== null) {
    return (
      <div role="alert" className="alert alert-error alert-vertical sm:alert-horizontal">
        <TriangleAlert aria-hidden="true" className="size-5" />
        <div>
          <h3 className="font-semibold">Could not load this run</h3>
          <div className="text-xs">{error}</div>
        </div>
      </div>
    );
  }

  if (view === null) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading run">
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="breadcrumbs text-sm">
        <ul>
          <li>
            <Link to="/">Runs</Link>
          </li>
          <li>
            <span className="font-mono">{view.run_id}</span>
          </li>
        </ul>
      </div>

      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-lg font-semibold">{view.scenario}</h1>
          <StatusBadge status={view.status} />
          {view.candidate !== null ? (
            <span className="badge badge-sm badge-ghost gap-1">
              <GitBranch aria-hidden="true" className="size-3" />
              candidate: <span className="font-mono">{view.candidate}</span>
            </span>
          ) : null}
        </div>
        <div className="stats stats-vertical border border-base-300 lg:stats-horizontal">
          <div className="stat">
            <div className="stat-title">Turns</div>
            <div className="stat-value tabular-nums text-2xl">{view.turns.length}</div>
            <div className="stat-desc tabular-nums">
              {view.changed_turn_indexes.length} divergent
            </div>
          </div>
          <div className="stat">
            <div className="stat-title">Model</div>
            <div className="stat-value font-mono text-base">{view.model}</div>
            <div className="stat-desc font-mono">agent {view.agent_version}</div>
          </div>
          <div className="stat">
            <div className="stat-title">Channel</div>
            <div className="stat-value text-base">{view.channel}</div>
            <div className="stat-desc tabular-nums">
              {new Date(view.recorded_at).toISOString().slice(0, 16).replace("T", " ")}
            </div>
          </div>
        </div>
      </header>

      {view.divergences.length > 0 ? (
        <div role="alert" className="alert alert-warning alert-vertical sm:alert-horizontal">
          <GitBranch aria-hidden="true" className="size-5" />
          <div>
            <h3 className="font-semibold">Candidate left the recorded trajectory</h3>
            <ul className="mt-1 flex flex-col gap-1 text-xs">
              {view.divergences.map((divergence) => (
                <li key={`${divergence.turn_index}-${divergence.kind}`} className="font-mono">
                  turn {divergence.turn_index} [{divergence.kind}]: {divergence.summary}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      <section aria-labelledby="invariants-heading" className="flex flex-col gap-2">
        <h2 id="invariants-heading" className="text-xs font-semibold tracking-wide uppercase">
          Cross-turn invariants
        </h2>
        <InvariantChips invariants={view.invariants} />
      </section>

      <JudgeChips judge={view.judge} note={view.judge_note} />

      {view.changed_turn_indexes.length > 0 ? (
        <nav aria-label="Jump to divergent turn" className="flex flex-wrap items-center gap-2">
          <span className="text-xs opacity-70">Jump to divergence:</span>
          {view.changed_turn_indexes.map((index) => (
            <a key={index} href={`#turn-${index}`} className="link link-primary font-mono text-xs">
              turn {index}
            </a>
          ))}
        </nav>
      ) : null}

      <div className="flex flex-col gap-4">
        {view.turns.map((turn) => (
          <TurnRow key={turn.index} turn={turn} />
        ))}
      </div>
    </div>
  );
}
