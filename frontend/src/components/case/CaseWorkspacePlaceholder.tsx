import { useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { AppShell } from '../layout/AppShell';
import { TopBar } from '../layout/TopBar';

export function CaseWorkspacePlaceholder() {
  const { user, activeCase, role, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  if (!activeCase || !user) {
    return null; // or redirect, though routing logic should handle this
  }

  return (
    <AppShell>
      <TopBar section={`Case: ${activeCase.case_identifier}`}>
        <div className="flex flex-1 justify-end">
          <Button variant="ghost" size="sm" icon={<LogOut size={16} />} onClick={handleLogout}>
            Sign Out
          </Button>
        </div>
      </TopBar>
      <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-gray-200 text-center">
          <h2 className="text-xl font-bold text-gray-900 mb-2">Authentication Successful</h2>
          <p className="text-gray-500 mb-8">This is a temporary placeholder for the authenticated case workspace.</p>
          
          <div className="grid grid-cols-2 gap-4 text-left border-t border-gray-100 pt-6">
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Current Case</p>
                <p className="text-sm font-medium text-gray-900">{activeCase.name}</p>
                <p className="text-xs font-mono text-gray-500 mt-0.5">{activeCase.case_identifier}</p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Authenticated User</p>
                <p className="text-sm font-medium text-gray-900">{user.display_name}</p>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge variant="active">@{user.username}</Badge>
                  {role && <Badge variant="admin">{role}</Badge>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
