import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles/globals.css";
import { AppShell } from "./components/layout/AppShell";
import { EmptyState } from "./components/ui/EmptyState";
import { Button } from "./components/ui/Button";
import { Spinner } from "./components/ui/Spinner";
import {AuthProvider,Guard} from './auth';

// B20: every route is its own chunk; the shell, auth and UI primitives stay in the main bundle.
const named = <K extends string>(load: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const LoginPage = named(() => import('./pages/LoginPage'), 'LoginPage');
const DashboardPage = named(() => import('./pages/DashboardPage'), 'DashboardPage');
const IncidentsPage = named(() => import('./pages/IncidentsPage'), 'IncidentsPage');
const IncidentPage = named(() => import('./pages/IncidentPage'), 'IncidentPage');
const UploadPage = named(() => import('./pages/UploadPage'), 'UploadPage');
const EvaluationsPage = named(() => import('./pages/EvaluationsPage'), 'EvaluationsPage');
const MachinesPage = named(() => import('./pages/MachinesPage'), 'MachinesPage');
const MachinePage = named(() => import('./pages/MachinesPage'), 'MachinePage');
const DocumentsPage = named(() => import('./pages/DocumentsPage'), 'DocumentsPage');
const DocumentPage = named(() => import('./pages/DocumentsPage'), 'DocumentPage');
const UsersPage = named(() => import('./pages/ManagementPages'), 'UsersPage');
const CasesPage = named(() => import('./pages/CasesPages'), 'CasesPage');
const CaseDetailPage = named(() => import('./pages/CasesPages'), 'CaseDetailPage');
const AuditPage = named(() => import('./pages/AuditPage'), 'AuditPage');
const pageFallback = <div className="flex min-h-[40vh] items-center justify-center"><Spinner label="Loading…" /></div>;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
      <Routes>
        <Route path="/login" element={<Suspense fallback={pageFallback}><LoginPage/></Suspense>}/>
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
          <Route element={<Guard action="users"/>}><Route path="/users" element={<UsersPage/>}/><Route path="/audit" element={<AuditPage/>}/></Route>
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
