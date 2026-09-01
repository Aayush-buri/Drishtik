import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Files, 
  HardDrive, 
  Cpu, 
  Video, 
  DatabaseBackup, 
  Brain, 
  FileText,
  LogOut,
  Home,
  Settings,
  Bell
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../ui/Badge';
import { DrishtikLogo } from '../../assets/DrishtikLogo';

const navItems = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '' },
  { label: 'Evidence', icon: Files, path: 'evidence' },
  { label: 'Devices', icon: HardDrive, path: 'devices' },
  { label: 'Acquisition', icon: Cpu, path: 'acquisition' },
  { label: 'Video Analysis', icon: Video, path: 'video' },
  { label: 'Recovery', icon: DatabaseBackup, path: 'recovery' },
  { label: 'AI Analysis', icon: Brain, path: 'ai' },
  { label: 'Records', icon: FileText, path: 'records' },
];

export function CaseWorkspaceShell() {
  const { user, activeCase, role, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!activeCase || !user) {
    return null; // Will redirect via ProtectedRoute normally
  }

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const handleHome = () => {
    navigate('/');
  };

  // Determine current module name from path
  const currentPath = location.pathname.split('/').pop();
  const currentModule = navItems.find(item => 
    item.path === currentPath || (item.path === '' && location.pathname.endsWith(`/case/${activeCase.id}`))
  )?.label || 'Settings';

  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden font-sans">
      
      {/* Left Sidebar */}
      <aside className="w-16 md:w-56 bg-gray-900 text-gray-400 flex flex-col justify-between shrink-0 transition-all duration-300">
        <div>
          {/* Logo Area */}
          <div className="h-14 flex items-center justify-center md:justify-start md:px-6 border-b border-gray-800">
            <DrishtikLogo size={24} className="text-indigo-400" />
            <span className="ml-3 font-semibold text-white tracking-wide hidden md:block">Drishtik</span>
          </div>

          {/* Main Nav */}
          <nav className="p-2 md:p-4 space-y-1 mt-2">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === ''}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors group relative ${
                    isActive 
                      ? 'bg-indigo-600/10 text-indigo-400 font-medium' 
                      : 'hover:bg-gray-800 hover:text-gray-100'
                  }`
                }
                title={item.label} // Tooltip for collapsed state
              >
                <item.icon size={18} className="shrink-0" />
                <span className="text-sm hidden md:block">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Bottom Utility Controls */}
        <div className="p-2 md:p-4 border-t border-gray-800 space-y-1">
          <button 
            onClick={handleHome}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-gray-800 hover:text-gray-100 transition-colors"
            title="Home (Case Manager)"
          >
            <Home size={18} className="shrink-0" />
            <span className="text-sm hidden md:block">Home</span>
          </button>
          
          <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-gray-800 hover:text-gray-100 transition-colors" title="Notifications">
            <Bell size={18} className="shrink-0" />
            <span className="text-sm hidden md:block">Notifications</span>
          </button>

          <NavLink 
            to="settings"
            className={({ isActive }) =>
              `w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors ${
                isActive 
                  ? 'bg-indigo-600/10 text-indigo-400 font-medium' 
                  : 'hover:bg-gray-800 hover:text-gray-100'
              }`
            }
            title="Settings"
          >
            <Settings size={18} className="shrink-0" />
            <span className="text-sm hidden md:block">Settings</span>
          </NavLink>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Top Bar */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 shadow-sm z-10">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="font-semibold text-gray-900">{activeCase.case_identifier}</span>
            <span className="text-gray-300">/</span>
            <span className="font-medium text-gray-700">{currentModule}</span>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3">
              <span className="text-sm font-medium text-gray-700">{user.display_name}</span>
              {role && <Badge variant={role === 'ADMIN' ? 'admin' : 'active'}>{role}</Badge>}
            </div>
            <div className="w-px h-4 bg-gray-200 hidden sm:block"></div>
            <button 
              onClick={handleLogout}
              className="text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-2 text-sm font-medium"
              title="Sign Out"
            >
              <LogOut size={16} />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
