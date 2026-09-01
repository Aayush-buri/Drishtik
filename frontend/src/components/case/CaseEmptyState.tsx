import { FolderOpen, Search } from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';
import { Button } from '../ui/Button';

interface CaseEmptyStateProps {
  isSearchResult: boolean;
  searchQuery: string;
  onNewCase: () => void;
  onClearSearch?: () => void;
}

export function CaseEmptyState({ isSearchResult, searchQuery, onNewCase, onClearSearch }: CaseEmptyStateProps) {
  if (isSearchResult) {
    return (
      <EmptyState
        icon={<Search size={24} />}
        title="No cases found"
        description={`No cases match "${searchQuery}". Try a different search term.`}
        action={
          onClearSearch && (
            <Button variant="secondary" size="sm" onClick={onClearSearch}>
              Clear search
            </Button>
          )
        }
      />
    );
  }

  return (
    <EmptyState
      icon={<FolderOpen size={24} />}
      title="No cases yet"
      description="Create your first forensic case to get started."
      action={
        <Button size="sm" onClick={onNewCase}>
          New Case
        </Button>
      }
    />
  );
}
