import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { CaseManager } from './CaseManager';
import { CaseAuthScreen } from './components/case/CaseAuthScreen';
import { CaseWorkspaceShell } from './components/case/CaseWorkspaceShell';
import { Dashboard } from './components/case/Dashboard';
import { SettingsPlaceholder } from './components/case/SettingsPlaceholder';
import { ModulePlaceholder } from './components/case/ModulePlaceholder';
import { EvidenceModule } from './components/case/evidence/EvidenceModule';
import { EvidenceInspectionView } from './components/case/evidence/EvidenceInspectionView';
import { DevicesModule } from './components/case/devices/DevicesModule';
import { DeviceDetailsView } from './components/case/devices/DeviceDetailsView';
import { RecordsModule } from './components/case/RecordsModule';
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
            <Route path="evidence" element={<EvidenceModule />} />
            <Route path="evidence/:evidenceId" element={<EvidenceInspectionView />} />
            <Route path="devices" element={<DevicesModule />} />
            <Route path="devices/:deviceId" element={<DeviceDetailsView />} />
            <Route path="acquisition" element={<DevicesModule />} />
            <Route path="video" element={<ModulePlaceholder />} />
            <Route path="recovery" element={<ModulePlaceholder />} />
            <Route path="ai" element={<ModulePlaceholder />} />
            <Route path="records" element={<RecordsModule />} />
            <Route path="settings" element={<SettingsPlaceholder />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
