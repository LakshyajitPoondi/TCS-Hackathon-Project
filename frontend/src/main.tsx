import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles/globals.css";
import { AppShell } from "./components/layout/AppShell";
import { IncidentsPage } from "./pages/IncidentsPage";
import { IncidentPage } from "./pages/IncidentPage";
import { UploadPage } from "./pages/UploadPage";
import { EvaluationsPage } from "./pages/EvaluationsPage";
import { EmptyState } from "./components/ui/EmptyState";
import { Button } from "./components/ui/Button";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<IncidentsPage />} />
          <Route path="/incidents/:id" element={<IncidentPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/evaluations" element={<EvaluationsPage />} />
          <Route
            path="*"
            element={
              <EmptyState title="Page not found">
                <Button to="/" variant="ghost" arrow>
                  Back to incidents
                </Button>
              </EmptyState>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
