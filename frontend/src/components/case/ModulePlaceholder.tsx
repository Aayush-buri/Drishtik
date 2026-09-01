import { useLocation } from 'react-router-dom';
import { Settings2 } from 'lucide-react';

export function ModulePlaceholder() {
  const location = useLocation();
  const moduleName = location.pathname.split('/').pop() || 'Module';
  const formattedName = moduleName.charAt(0).toUpperCase() + moduleName.slice(1);

  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-8">
      <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center text-gray-400 mb-4">
        <Settings2 size={32} />
      </div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">{formattedName} Module</h2>
      <p className="text-sm text-gray-500 max-w-md">
        This functional module will be implemented in a future phase of the Drishtik platform.
      </p>
    </div>
  );
}
