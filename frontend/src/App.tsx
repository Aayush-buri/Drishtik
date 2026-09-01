import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { CaseManager } from './CaseManager';
import { CaseAuthScreen } from './components/case/CaseAuthScreen';
import { CaseWorkspaceShell } from './components/case/CaseWorkspaceShell';
import { Dashboard } from './components/case/Dashboard';
import { SettingsPlaceholder } from './components/case/SettingsPlaceholder';
import { ModulePlaceholder } from './components/case/ModulePlaceholder';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CaseManager />} />
        <Route path="/auth/:caseId" element={<CaseAuthScreen />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/case/:caseId" element={<CaseWorkspaceShell />}>
            <Route index element={<Dashboard />} />
            <Route path="evidence" element={<ModulePlaceholder />} />
            <Route path="devices" element={<ModulePlaceholder />} />
            <Route path="acquisition" element={<ModulePlaceholder />} />
            <Route path="video" element={<ModulePlaceholder />} />
            <Route path="recovery" element={<ModulePlaceholder />} />
            <Route path="ai" element={<ModulePlaceholder />} />
            <Route path="records" element={<ModulePlaceholder />} />
            <Route path="settings" element={<SettingsPlaceholder />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
