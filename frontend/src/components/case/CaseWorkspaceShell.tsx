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
  let currentModule = navItems.find(item => 
    (item.path && item.path === currentPath) || 
    (item.path === '' && (
      location.pathname.endsWith(`/case/${activeCase.id}`) ||
      location.pathname.endsWith(`/case/${activeCase.case_identifier}`) ||
      currentPath === String(activeCase.id) ||
      currentPath === activeCase.case_identifier
    ))
  )?.label;

  if (!currentModule) {
    if (location.pathname.includes('/evidence/')) {
      currentModule = 'Evidence Inspection';
    } else if (location.pathname.includes('/devices/')) {
      currentModule = 'Device Details';
    } else if (location.pathname.includes('/video')) {
      currentModule = 'Video Analysis';
    } else if (location.pathname.endsWith('settings')) {
      currentModule = 'Settings';
    } else {
      currentModule = 'Dashboard';
    }
  }

  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden font-sans">
      
      {/* Left Sidebar - Unified Light Design System */}
      <aside className="w-16 md:w-56 bg-white border-r border-gray-200 text-gray-600 flex flex-col justify-between shrink-0 transition-all duration-300 shadow-sm z-20">
        <div>
          {/* Logo Area */}
          <div className="h-14 flex items-center justify-center md:justify-start md:px-6 border-b border-gray-100">
            <DrishtikLogo size={24} className="text-indigo-600 shrink-0" />
            <span className="ml-3 font-bold text-gray-900 tracking-tight hidden md:block text-base">Drishtik</span>
          </div>

          {/* Main Nav */}
          <nav className="p-2 md:p-3 space-y-1 mt-2">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === ''}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group relative font-medium text-sm ${
                    isActive 
                      ? 'bg-indigo-50 text-indigo-700 font-semibold shadow-xs' 
                      : 'text-gray-600 hover:bg-gray-100/80 hover:text-gray-900'
                  }`
                }
                title={item.label}
              >
                <item.icon size={18} className="shrink-0" />
                <span className="hidden md:block truncate">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Bottom Utility Controls */}
        <div className="p-2 md:p-3 border-t border-gray-100 space-y-1">
          <button 
            onClick={handleHome}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-600 hover:bg-gray-100/80 hover:text-gray-900 font-medium text-sm transition-colors"
            title="Home (Case Manager)"
          >
            <Home size={18} className="shrink-0" />
            <span className="hidden md:block">Home</span>
          </button>
          
          <button 
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-600 hover:bg-gray-100/80 hover:text-gray-900 font-medium text-sm transition-colors" 
            title="Notifications"
          >
            <Bell size={18} className="shrink-0" />
            <span className="hidden md:block">Notifications</span>
          </button>

          <NavLink 
            to="settings"
            className={({ isActive }) =>
              `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium text-sm transition-colors ${
                isActive 
                  ? 'bg-indigo-50 text-indigo-700 font-semibold shadow-xs' 
                  : 'text-gray-600 hover:bg-gray-100/80 hover:text-gray-900'
              }`
            }
            title="Settings"
          >
            <Settings size={18} className="shrink-0" />
            <span className="hidden md:block">Settings</span>
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
        <main className="flex-1 overflow-y-auto bg-gray-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
