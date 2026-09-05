import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { CaseManager } from './CaseManager';
import { CaseAuthScreen } from './components/case/CaseAuthScreen';
import { CaseWorkspaceShell } from './components/case/CaseWorkspaceShell';
import { Dashboard } from './components/case/Dashboard';
import { SettingsPlaceholder } from './components/case/SettingsPlaceholder';
import { EvidenceModule } from './components/case/evidence/EvidenceModule';
import { EvidenceInspectionView } from './components/case/evidence/EvidenceInspectionView';
import { DevicesModule } from './components/case/devices/DevicesModule';
import { DeviceDetailsView } from './components/case/devices/DeviceDetailsView';
import { RecordsModule } from './components/case/RecordsModule';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { VideoAnalysisWorkspace } from './components/case/video/VideoAnalysisWorkspace';
import { RecoveryModule } from './components/case/recovery/RecoveryModule';
import { AIAnalysisModule } from './components/case/ai/AIAnalysisModule';

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
            <Route path="video-analysis/:evidenceId" element={<VideoAnalysisWorkspace />} />
            <Route path="video" element={<VideoAnalysisWorkspace />} />
            <Route path="video/:evidenceId" element={<VideoAnalysisWorkspace />} />
            <Route path="devices" element={<DevicesModule />} />
            <Route path="devices/:deviceId" element={<DeviceDetailsView />} />
            <Route path="acquisition" element={<DevicesModule />} />
            <Route path="recovery" element={<RecoveryModule />} />
            <Route path="ai" element={<AIAnalysisModule />} />
            <Route path="records" element={<RecordsModule />} />
            <Route path="settings" element={<SettingsPlaceholder />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
