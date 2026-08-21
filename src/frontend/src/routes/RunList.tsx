import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, TriangleAlert } from "lucide-react";
import { fetchRuns } from "../api";
import type { RunSummary } from "../types";

export default function RunList() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns().then(setRuns, (e: Error) => setError(e.message));
  }, []);

  if (error !== null) {
    return (
      <div role="alert" className="alert alert-error alert-vertical sm:alert-horizontal">
        <TriangleAlert aria-hidden="true" className="size-5" />
        <div>
          <h3 className="font-semibold">Could not load runs</h3>
          <div className="text-xs">{error}</div>
        </div>
      </div>
    );
  }

  if (runs === null) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading runs">
        <div className="skeleton h-8 w-full" />
        <div className="skeleton h-8 w-full" />
        <div className="skeleton h-8 w-full" />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div role="alert" className="alert alert-vertical sm:alert-horizontal">
        <FolderOpen aria-hidden="true" className="size-5" />
        <div>
          <h3 className="font-semibold">No recorded runs</h3>
          <div className="text-xs">
            The fixtures directory has no fixture in it yet. Record one with{" "}
            <code className="font-mono">replaygate record booking_happy ./fx</code>, then
            point the server at its parent directory.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-full overflow-x-auto rounded-box border border-base-300">
      <table className="table table-sm">
        <caption className="sr-only">Recorded conversation fixtures</caption>
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Scenario</th>
            <th scope="col">Channel</th>
            <th scope="col">Model</th>
            <th scope="col">Agent</th>
            <th scope="col">Turns</th>
            <th scope="col">Recorded</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id} className="hover:bg-base-200">
              <td>
                <Link className="link link-primary font-mono" to={`/runs/${run.run_id}`}>
                  {run.run_id}
                </Link>
              </td>
              <td className="font-mono text-xs">{run.scenario}</td>
              <td>{run.channel}</td>
              <td className="font-mono text-xs">{run.model}</td>
              <td className="font-mono text-xs">{run.agent_version}</td>
              <td className="tabular-nums">{run.turn_count}</td>
              <td className="tabular-nums text-xs">
                {new Date(run.recorded_at).toISOString().slice(0, 16).replace("T", " ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
