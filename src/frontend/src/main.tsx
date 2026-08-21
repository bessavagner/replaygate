import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import RunDetail from "./routes/RunDetail";
import RunList from "./routes/RunList";
import "./index.css";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-base-100 text-base-content font-sans">
      <div className="navbar bg-base-100 border-b border-base-300">
        <div className="navbar-start">
          <Link to="/" className="font-mono text-sm font-semibold">
            ReplayGate
          </Link>
        </div>
        <div className="navbar-end text-xs opacity-70">read-only</div>
      </div>
      <main className="mx-auto max-w-6xl p-4">{children}</main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <Shell>
              <RunList />
            </Shell>
          }
        />
        <Route
          path="/runs/:runId"
          element={
            <Shell>
              <RunDetail />
            </Shell>
          }
        />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
