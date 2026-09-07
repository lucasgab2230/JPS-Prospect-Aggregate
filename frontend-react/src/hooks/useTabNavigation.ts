import { useSearchParams } from 'react-router-dom';

interface TabConfig {
  id: string;
  label: string;
  description: string;
  subTabs?: Array<{
    id: string;
    label: string;
  }>;
}

const allTabs: TabConfig[] = [
  { id: 'data-sources', label: 'Data Sources', description: 'Manage data sources and scrapers' },
  {
    id: 'database',
    label: 'Database',
    description: 'Database management and operations',
    subTabs: [
      { id: 'overview', label: 'Overview' },
      { id: 'duplicates', label: 'Duplicate Review' }
    ]
  },
  { id: 'ai-enrichment', label: 'AI Enhancement', description: 'AI enrichment controls and status monitoring' },
  { id: 'tools', label: 'Tools', description: 'System utilities and maintenance scripts' }
];

export function useTabNavigation(isSuperAdmin: boolean = false) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Filter tabs based on user role
  const tabs = isSuperAdmin ? allTabs : allTabs.filter(tab => tab.id !== 'data-sources');

  const activeTab = searchParams.get('tab') || tabs[0].id;
  const activeSubTab = searchParams.get('subtab') || 'overview';

  const currentTab = tabs.find(tab => tab.id === activeTab) || tabs[0];

  const setActiveTab = (tab: string, subtab?: string) => {
    const params: { tab: string; subtab?: string } = { tab };
    if (subtab) {
      params.subtab = subtab;
    }
    setSearchParams(params);
  };

  return {
    // Configuration
    tabs,

    // Current state
    activeTab,
    activeSubTab,
    currentTab,

    // Actions
    setActiveTab,
  };
}
