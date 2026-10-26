import React, { createContext, useContext, ReactNode } from 'react';

// Define the shape of your context data
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface AppContextType {
  // Add your context values here
  // Example:
  // isAuthenticated: boolean;
  // setIsAuthenticated: (isAuthenticated: boolean) => void;
}

// Create the context with a default undefined value
const AppContext = createContext<AppContextType | undefined>(undefined);

// Create a provider component
interface AppProviderProps {
  children: ReactNode;
}

export const AppProviders: React.FC<AppProviderProps> = ({ children }) => {
  // Add your state and functions here
  // Example:
  // const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  const contextValue: AppContextType = {
    // Pass your state and functions here
    // Example:
    // isAuthenticated,
    // setIsAuthenticated,
  };

  return (
    <AppContext.Provider value={contextValue}>
      {children}
    </AppContext.Provider>
  );
};

// Create a custom hook to use the AppContext
export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProviders');
  }
  return context;
};
