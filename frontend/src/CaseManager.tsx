import { useState, useCallback } from 'react';
import { Plus, AlertCircle, RefreshCw } from 'lucide-react';
import { AppShell } from './components/layout/AppShell';
import { TopBar } from './components/layout/TopBar';
import { CaseGrid } from './components/case/CaseGrid';
import { CaseSearch } from './components/case/CaseSearch';
import { CaseEmptyState } from './components/case/CaseEmptyState';
import { NewCaseDialog } from './components/case/NewCaseDialog';
import { CaseCardSkeleton } from './components/ui/Skeleton';
import { Button } from './components/ui/Button';
import { useCases } from './hooks/useCases';
import type { CaseCreateInput } from './types/case';

export function CaseManager() {
  const {
    cases,
    allCases,
    isLoading,
    error,
    searchQuery,
    setSearchQuery,
    selectedCaseId,
    setSelectedCaseId,
    createCase,
    retry,
  } = useCases();

  const [isNewCaseOpen, setIsNewCaseOpen] = useState(false);

  const handleOpenCase = useCallback((id: string) => {
    // Future: navigate to case workspace with authentication
    console.log(`Opening case ${id} — authentication screen pending`);
    setSelectedCaseId(id);
  }, [setSelectedCaseId]);

  const handleCreateCase = useCallback(
    async (input: CaseCreateInput) => {
      await createCase(input);
    },
    [createCase]
  );

  return (
    <AppShell>
      <TopBar section="Case Manager">
        <CaseSearch value={searchQuery} onChange={setSearchQuery} />
      </TopBar>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          {/* Section Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Cases</h1>
              {!isLoading && !error && allCases.length > 0 && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {allCases.length} {allCases.length === 1 ? 'case' : 'cases'}
                  {searchQuery && ` · ${cases.length} matching`}
                </p>
              )}
            </div>
            <Button
              size="sm"
              icon={<Plus size={15} />}
              onClick={() => setIsNewCaseOpen(true)}
            >
              New Case
            </Button>
          </div>

          {/* Error State */}
          {error && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-red-50 text-red-400 mb-4">
                <AlertCircle size={24} />
              </div>
              <h3 className="text-base font-semibold text-gray-900 mb-1">Something went wrong</h3>
              <p className="text-sm text-gray-500 max-w-sm mb-5">{error}</p>
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw size={14} />}
                onClick={retry}
              >
                Retry
              </Button>
            </div>
          )}

          {/* Loading State */}
          {isLoading && !error && (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <CaseCardSkeleton key={i} />
              ))}
            </div>
          )}

          {/* Empty / No Results */}
          {!isLoading && !error && cases.length === 0 && (
            <CaseEmptyState
              isSearchResult={searchQuery.length > 0}
              searchQuery={searchQuery}
              onNewCase={() => setIsNewCaseOpen(true)}
              onClearSearch={() => setSearchQuery('')}
            />
          )}

          {/* Case Grid */}
          {!isLoading && !error && cases.length > 0 && (
            <CaseGrid
              cases={cases}
              selectedCaseId={selectedCaseId}
              onSelectCase={setSelectedCaseId}
              onOpenCase={handleOpenCase}
            />
          )}
        </div>
      </main>

      {/* New Case Dialog */}
      <NewCaseDialog
        open={isNewCaseOpen}
        onClose={() => setIsNewCaseOpen(false)}
        onCreate={handleCreateCase}
      />
    </AppShell>
  );
}
