import { Search, X } from 'lucide-react';
import { Input } from '../ui/Input';
import { IconButton } from '../ui/IconButton';

interface CaseSearchProps {
  value: string;
  onChange: (value: string) => void;
}

export function CaseSearch({ value, onChange }: CaseSearchProps) {
  return (
    <div className="relative w-64">
      <Input
        placeholder="Search cases..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        icon={<Search size={15} />}
        aria-label="Search cases by name, ID, or type"
      />
      {value && (
        <div className="absolute right-1.5 top-1/2 -translate-y-1/2">
          <IconButton
            icon={<X size={14} />}
            size="sm"
            onClick={() => onChange('')}
            aria-label="Clear search"
          />
        </div>
      )}
    </div>
  );
}
