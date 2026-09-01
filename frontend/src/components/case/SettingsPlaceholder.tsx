export function SettingsPlaceholder() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900 mb-2">Settings</h1>
        <p className="text-sm text-gray-500 mb-8">Manage case configurations, security policies, and team access.</p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {['General', 'Security', 'Collaborators', 'Evidence', 'Video Analysis', 'AI Configuration', 'Blockchain Audit', 'Advanced'].map(setting => (
            <div key={setting} className="p-4 border border-gray-100 rounded-lg hover:border-indigo-100 hover:bg-indigo-50/30 transition-colors cursor-not-allowed opacity-70">
              <h3 className="font-medium text-gray-900 text-sm">{setting}</h3>
              <p className="text-xs text-gray-500 mt-1">Configuration pending implementation</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
