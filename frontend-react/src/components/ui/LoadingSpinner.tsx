import React from 'react';

export type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SpinnerColor = 'blue' | 'white' | 'gray' | 'red' | 'green' | 'yellow';

export interface LoadingSpinnerProps {
  size?: SpinnerSize;
  color?: SpinnerColor;
  text?: string;
  className?: string;
  inline?: boolean;
  fullHeight?: boolean;
}

const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
  xl: 'h-16 w-16',
};

const colorClasses: Record<SpinnerColor, string> = {
  blue: 'border-blue-600',
  white: 'border-white',
  gray: 'border-gray-600',
  red: 'border-red-600',
  green: 'border-green-600',
  yellow: 'border-yellow-600',
};

const textSizeClasses: Record<SpinnerSize, string> = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
  xl: 'text-xl',
};

/**
 * Reusable loading spinner component with customizable size, color, and text
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'blue',
  text,
  className = '',
  inline = false,
  fullHeight = false,
}) => {
  const spinnerClasses = [
    'animate-spin rounded-full border-t-2 border-b-2',
    sizeClasses[size],
    colorClasses[color],
  ].join(' ');

  const textClasses = [
    textSizeClasses[size],
    colorClasses[color].replace('border-', 'text-'),
  ].join(' ');

  const containerClasses = [
    inline ? 'inline-flex' : 'flex',
    'items-center',
    fullHeight ? 'justify-center h-full' : '',
    !inline && !fullHeight ? 'justify-center' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={containerClasses}>
      <div className={spinnerClasses} />
      {text && (
        <span className={`ml-3 ${textClasses}`}>
          {text}
        </span>
      )}
    </div>
  );
};

/**
 * Full-page loading spinner for page-level loading states
 */
export const FullPageSpinner: React.FC<{
  text?: string;
  size?: SpinnerSize;
}> = ({ text = 'Loading...', size = 'lg' }) => {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-white bg-opacity-75 z-50">
      <LoadingSpinner size={size} text={text} />
    </div>
  );
};

/**
 * Centered loading spinner for content areas
 */
export const CenteredSpinner: React.FC<{
  text?: string;
  size?: SpinnerSize;
  height?: string;
}> = ({ text, size = 'md', height = 'h-32' }) => {
  return (
    <div className={`flex items-center justify-center ${height}`}>
      <LoadingSpinner size={size} text={text} />
    </div>
  );
};

export default LoadingSpinner;
