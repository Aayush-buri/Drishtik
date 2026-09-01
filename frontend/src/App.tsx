import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { CaseManager } from './CaseManager';
import { CaseAuthScreen } from './components/case/CaseAuthScreen';
import { CaseWorkspacePlaceholder } from './components/case/CaseWorkspacePlaceholder';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CaseManager />} />
        <Route path="/auth/:caseId" element={<CaseAuthScreen />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/case/:caseId" element={<CaseWorkspacePlaceholder />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
