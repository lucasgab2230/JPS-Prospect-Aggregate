interface EnhancementStatusBadgeProps {
  hasAnyActivity: boolean;
}

export function EnhancementStatusBadge({ hasAnyActivity }: EnhancementStatusBadgeProps) {
  return (
    <div className="flex items-center space-x-2">
      <div className={`w-2 h-2 rounded-full ${hasAnyActivity ? 'bg-green-500' : 'bg-gray-500'} ${hasAnyActivity ? 'animate-pulse' : ''}`}></div>
      <span className="text-xs text-gray-600">
        {hasAnyActivity ? 'Live updates' : 'Idle'}
      </span>
    </div>
  );
}
