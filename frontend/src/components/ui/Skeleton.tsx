interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-md bg-gray-200/70 ${className}`}
      aria-hidden="true"
    />
  );
}

export function CaseCardSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-5 w-3/4" />
      <div className="space-y-2 pt-1">
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <div className="flex items-center justify-between pt-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>
    </div>
  );
}
