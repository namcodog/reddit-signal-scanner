import { useContext } from 'react';
import { AppStateContext } from './appStateContext';

export const useAppState = () => {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error('useAppState must be used within an AppStateProvider');
  }
  return [context.state, context.actions] as const;
};

export default useAppState;
