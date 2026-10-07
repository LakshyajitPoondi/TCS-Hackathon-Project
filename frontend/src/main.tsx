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
import {AuthProvider,Guard} from './auth';
import {LoginPage} from './pages/LoginPage';
import {MachinesPage,MachinePage} from './pages/MachinesPage';
import {DocumentsPage,DocumentPage} from './pages/DocumentsPage';
import {UsersPage} from './pages/ManagementPages';
import {CasesPage,CaseDetailPage} from './pages/CasesPages';
import {DashboardPage} from './pages/DashboardPage';

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage/>}/>
        <Route element={<Guard/>}>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/incidents/:id" element={<IncidentPage />} />
          <Route element={<Guard action="upload"/>}><Route path="/upload" element={<UploadPage />} /></Route>
          <Route path="/machines" element={<MachinesPage/>}/>
          <Route path="/machines/:line/:short" element={<MachinePage/>}/>
          <Route path="/documents" element={<DocumentsPage/>}/>
          <Route path="/documents/:id" element={<DocumentPage/>}/>
          <Route path="/cases" element={<CasesPage/>}/>
          <Route path="/cases/:id" element={<CaseDetailPage/>}/>
          <Route element={<Guard action="users"/>}><Route path="/users" element={<UsersPage/>}/></Route>
          <Route path="/evaluations" element={<EvaluationsPage />} />
          <Route
            path="*"
            element={
              <EmptyState title="Page not found">
                <Button to="/" variant="ghost" arrow>
                  Back to dashboard
                </Button>
              </EmptyState>
            }
          />
        </Route>
        </Route>
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
