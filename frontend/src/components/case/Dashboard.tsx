import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Files, 
  HardDrive, 
  Video, 
  DatabaseBackup, 
  Brain,
  Download,
  Search,
  Zap,
  PlayCircle,
  ArrowRight,
  Inbox
} from 'lucide-react';
import { dashboardService, type DashboardMetrics, type RecentEvidence, type TimelineEvent } from '../../services/dashboardService';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../ui/Badge';

export function Dashboard() {
  const { activeCase } = useAuth();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentEvidence, setRecentEvidence] = useState<RecentEvidence[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      setIsLoading(true);
      try {
        const [m, e, t] = await Promise.all([
          dashboardService.getMetrics(),
          dashboardService.getRecentEvidence(),
          dashboardService.getTimelinePreview()
        ]);
        setMetrics(m);
        setRecentEvidence(e);
        setTimelineEvents(t);
      } catch (err) {
        console.error('Failed to load dashboard data', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadDashboard();
  }, []);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const cards = [
    { label: 'Evidence', value: metrics?.evidenceCount || 0, icon: Files, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Devices', value: metrics?.devicesCount || 0, icon: HardDrive, color: 'text-purple-600', bg: 'bg-purple-50' },
    { label: 'Videos', value: metrics?.videosCount || 0, icon: Video, color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { label: 'Recovered', value: metrics?.recoveredCount || 0, icon: DatabaseBackup, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'AI Events', value: metrics?.aiEventsCount || 0, icon: Brain, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Case Status Header */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{activeCase?.name || 'Case Overview'}</h1>
          <p className="text-sm text-gray-500 mt-1">{activeCase?.description || 'No description provided.'}</p>
        </div>
        <div className="flex gap-4 text-sm">
          <div>
            <span className="text-gray-500">Status:</span>
            <Badge variant="active" className="ml-2">{activeCase?.status || 'ACTIVE'}</Badge>
          </div>
          <div className="hidden sm:block">
            <span className="text-gray-500">Type:</span>
            <span className="ml-2 font-medium text-gray-900">{activeCase?.case_type}</span>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {cards.map((card, i) => (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            key={card.label} 
            className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4"
          >
            <div className={`p-3 rounded-lg ${card.bg} ${card.color}`}>
              <card.icon size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 leading-none">{card.value}</p>
              <p className="text-xs font-medium text-gray-500 mt-1 uppercase tracking-wide">{card.label}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Main Column */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Recent Evidence */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
              <h2 className="text-sm font-semibold text-gray-900">Recent Evidence</h2>
              <button className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                View All <ArrowRight size={14} />
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-medium">
                  <tr>
                    <th className="px-6 py-3">ID</th>
                    <th className="px-6 py-3">File Name</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Hash</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {recentEvidence.length > 0 ? (
                    recentEvidence.map((ev) => (
                      <tr key={ev.id} className="hover:bg-gray-50/50">
                        <td className="px-6 py-3 font-mono text-xs">{ev.id}</td>
                        <td className="px-6 py-3 font-medium text-gray-900">{ev.fileName}</td>
                        <td className="px-6 py-3">{ev.type}</td>
                        <td className="px-6 py-3">
                          <span className={`inline-flex items-center gap-1.5 ${ev.hash === 'Verified' ? 'text-emerald-600' : ev.hash === 'Mismatch' ? 'text-red-600' : 'text-gray-500'}`}>
                            {ev.hash}
                          </span>
                        </td>
                        <td className="px-6 py-3">
                          <Badge variant={ev.status === 'Completed' ? 'active' : ev.status === 'Failed' ? 'admin' : 'default'}>
                            {ev.status}
                          </Badge>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                        <div className="flex flex-col items-center justify-center">
                          <Inbox size={24} className="text-gray-300 mb-2" />
                          <p className="text-sm font-medium text-gray-900">No evidence available</p>
                          <p className="text-xs mt-1 text-gray-500">Import evidence to see it listed here.</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Side Column */}
        <div className="space-y-6">
          
          {/* Quick Actions */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <button className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-indigo-100 hover:bg-indigo-50/50 hover:text-indigo-700 transition-colors group">
                <div className="flex items-center gap-3 text-sm font-medium text-gray-700 group-hover:text-indigo-700">
                  <Download size={16} className="text-gray-400 group-hover:text-indigo-500" />
                  Import Evidence
                </div>
              </button>
              <button className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-indigo-100 hover:bg-indigo-50/50 hover:text-indigo-700 transition-colors group">
                <div className="flex items-center gap-3 text-sm font-medium text-gray-700 group-hover:text-indigo-700">
                  <Search size={16} className="text-gray-400 group-hover:text-indigo-500" />
                  Identify Device
                </div>
              </button>
              <button className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-indigo-100 hover:bg-indigo-50/50 hover:text-indigo-700 transition-colors group">
                <div className="flex items-center gap-3 text-sm font-medium text-gray-700 group-hover:text-indigo-700">
                  <Zap size={16} className="text-gray-400 group-hover:text-indigo-500" />
                  Start Acquisition
                </div>
              </button>
              <button className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-indigo-100 hover:bg-indigo-50/50 hover:text-indigo-700 transition-colors group">
                <div className="flex items-center gap-3 text-sm font-medium text-gray-700 group-hover:text-indigo-700">
                  <PlayCircle size={16} className="text-gray-400 group-hover:text-indigo-500" />
                  Open Video Analysis
                </div>
              </button>
            </div>
          </div>

          {/* Timeline Preview */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold text-gray-900">Timeline Events</h2>
            </div>
            
            {timelineEvents.length > 0 ? (
              <div className="space-y-4">
                {timelineEvents.map((ev, i) => (
                  <div key={ev.id} className="flex gap-3 relative">
                    {i !== timelineEvents.length - 1 && (
                      <div className="absolute left-[9px] top-5 bottom-[-16px] w-px bg-gray-200"></div>
                    )}
                    <div className="w-5 h-5 rounded-full bg-gray-100 border-2 border-white flex-shrink-0 z-10"></div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-gray-900">{ev.time}</span>
                        <span className="text-xs text-gray-500">{ev.source}</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-0.5">{ev.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-gray-500 border border-dashed border-gray-200 rounded-lg bg-gray-50/50">
                <p className="text-sm font-medium text-gray-900">No events recorded</p>
                <p className="text-xs mt-1">Timeline data will appear here.</p>
              </div>
            )}
            
            <button className="mt-6 w-full text-center text-xs font-medium text-indigo-600 hover:text-indigo-700 bg-indigo-50/50 hover:bg-indigo-50 py-2 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              Open Full Timeline
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
