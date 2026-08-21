import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";

function Placeholder() {
  return (
    <div className="min-h-screen bg-base-100 text-base-content font-sans">
      <div className="navbar bg-base-100 border-b border-base-300">
        <div className="navbar-start">
          <span className="font-mono text-sm font-semibold">ReplayGate</span>
        </div>
      </div>
      <main className="mx-auto max-w-6xl p-4">
        <p className="text-sm">Scaffold OK.</p>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Placeholder />} />
        <Route path="/runs/:runId" element={<Placeholder />} />
      </Routes>
    </BrowserRouter>,
  </StrictMode>,
);
