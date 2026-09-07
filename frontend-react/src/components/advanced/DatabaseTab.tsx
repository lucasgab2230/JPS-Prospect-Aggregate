import { DatabaseManagement } from '@/components/DatabaseManagement';
import { DuplicateReview } from '@/components/DuplicateReview';

interface DatabaseTabProps {
  activeSubTab: string;
  onSetActiveTab: (tab: string, subtab?: string) => void;
  subTabs: Array<{
    id: string;
    label: string;
  }>;
}

export function DatabaseTab({ activeSubTab, onSetActiveTab, subTabs }: DatabaseTabProps) {
  return (
    <div className="space-y-6">
      {/* SubTab Navigation */}
      {subTabs.length > 0 && (
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {subTabs.map((subTab) => (
              <button
                key={subTab.id}
                onClick={() => onSetActiveTab('database', subTab.id)}
                className={`
                  py-2 px-1 border-b-2 font-medium text-sm
                  ${activeSubTab === subTab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                {subTab.label}
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* SubTab Content */}
      {activeSubTab === 'duplicates' ? <DuplicateReview /> : <DatabaseManagement />}
    </div>
  );
}
