import React from 'react';

interface PageLayoutProps {
  title?: string;
  description?: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function PageLayout({
  title,
  description,
  subtitle,
  children,
}: PageLayoutProps) {
  return (
    // Replaced div with CSS module class to a simple div,
    // or ideally one with Tailwind classes for basic layout if needed.
    // For now, a simple div to isolate styling issues.
    <div className="py-6 px-4 md:px-6 lg:px-8"> {/* Added some basic padding with Tailwind */}
      <div className="mb-4"> {/* Basic spacing for header content */}
        {title && (
          // Consider replacing with Tailwind classes: e.g., "text-3xl font-bold tracking-tight mb-1"
          <h1 className="text-gray-900 text-2xl font-semibold">{title}</h1>
        )}
        {subtitle && (
          // Consider replacing with Tailwind classes: e.g., "text-sm text-gray-600 dark:text-gray-400"
          <p className="text-sm text-gray-600">{subtitle}</p>
        )}
        {description && (
          // Consider replacing with Tailwind classes
          <p className="text-gray-700">{description}</p>
        )}
      </div>
      <main>{children}</main> {/* Wrapped children in <main> for semantics */}
    </div>
  );
}

export function PageSkeleton() {
  return (
    // Consider replacing with Tailwind for skeleton styling
    <div className="p-6">
      <div>Loading content...</div>
    </div>
  );
}
