import { CheckIcon, ReloadIcon, Cross2Icon } from '@radix-ui/react-icons';

interface ProgressStep {
  key: string;
  label: string;
  completed: boolean;
  skipped: boolean;
  active: boolean;
  skipReason?: string;
}

interface EnhancementProgressProps {
  status: {
    currentStep?: string;
    progress?: {
      titles?: { completed: boolean; skipped?: boolean; skipReason?: string };
      values?: { completed: boolean; skipped?: boolean; skipReason?: string };
      naics?: { completed: boolean; skipped?: boolean; skipReason?: string };
      set_asides?: { completed: boolean; skipped?: boolean; skipReason?: string };
    };
    enhancementTypes?: string[];
  } | null;
  isVisible: boolean;
}

export function EnhancementProgress({ status, isVisible }: EnhancementProgressProps) {
  if (!isVisible || !status) {
    return null;
  }

  const allSteps: ProgressStep[] = [
    {
      key: 'titles',
      label: 'Enhance Title',
      completed: status.progress?.titles?.completed || false,
      skipped: status.progress?.titles?.skipped || false,
      active: status.currentStep?.toLowerCase() === 'enhancing title...' || false,
      skipReason: status.progress?.titles?.skipReason
    },
    {
      key: 'values',
      label: 'Parse Contract Values',
      completed: status.progress?.values?.completed || false,
      skipped: status.progress?.values?.skipped || false,
      active: status.currentStep?.toLowerCase() === 'parsing contract values...' || false,
      skipReason: status.progress?.values?.skipReason
    },
    {
      key: 'naics',
      label: 'Classify NAICS Code',
      completed: status.progress?.naics?.completed || false,
      skipped: status.progress?.naics?.skipped || false,
      active: status.currentStep?.toLowerCase() === 'classifying naics code...' || false,
      skipReason: status.progress?.naics?.skipReason
    },
    {
      key: 'set_asides',
      label: 'Process Set Asides',
      completed: status.progress?.set_asides?.completed || false,
      skipped: status.progress?.set_asides?.skipped || false,
      active: status.currentStep?.toLowerCase() === 'processing set asides...' || false,
      skipReason: status.progress?.set_asides?.skipReason
    }
  ];

  // Filter steps based on enhancement types if provided
  const steps = status.enhancementTypes && status.enhancementTypes.length > 0
    ? allSteps.filter(step => status.enhancementTypes?.includes(step.key))
    : allSteps;

  return (
    <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
      <h4 className="text-sm font-medium text-yellow-800 mb-3">AI Enhancement Progress</h4>

      <div className="space-y-2">
        {steps.map((step) => (
          <div key={step.key} className="flex items-center space-x-3">
            <div className="flex-shrink-0">
              {step.active ? (
                <ReloadIcon className="h-4 w-4 text-blue-600 animate-spin" />
              ) : step.completed && !step.skipped ? (
                <CheckIcon className="h-4 w-4 text-green-600" />
              ) : step.skipped ? (
                // Show different icon based on whether it was planned to be skipped or actually skipped
                <div className="h-4 w-4 bg-yellow-100 rounded-full flex items-center justify-center" title={step.skipReason}>
                  <Cross2Icon className="h-3 w-3 text-yellow-700" />
                </div>
              ) : (
                <div className="h-4 w-4 border border-gray-300 rounded-full"></div>
              )}
            </div>
            <span className={`text-sm ${
              step.active ? 'text-blue-700 font-medium' :
              step.completed && !step.skipped ? 'text-green-700' :
              step.skipped ? 'text-yellow-700' :
              'text-gray-600'
            }`}>
              {step.label}
              {step.skipped && (
                <span className="ml-1 text-xs text-yellow-600">
                  (will skip - {
                    step.skipReason === 'already_enhanced' ? 'already enhanced' :
                    step.skipReason === 'already_parsed' ? 'already parsed' :
                    step.skipReason === 'already_classified' ? 'already classified' :
                    step.skipReason === 'already_standardized' ? 'already standardized' :
                    'has existing data'
                  })
                </span>
              )}
              {step.active && status.currentStep && (
                <span className="ml-1 text-xs">- {status.currentStep}</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
