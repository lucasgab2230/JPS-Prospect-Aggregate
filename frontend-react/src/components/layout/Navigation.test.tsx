import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navigation } from './Navigation';

// Mock the hooks
vi.mock('../AuthProvider', () => ({
  useAuth: vi.fn()
}));

vi.mock('../../hooks/api', () => ({
  useSignOut: vi.fn(),
  useIsAdmin: vi.fn()
}));

vi.mock('@/hooks/useError', () => ({
  useError: () => ({
    handleError: vi.fn()
  })
}));

vi.mock('@/lib/utils', () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(' ')
}));

// Helper function to generate dynamic user data
const generateUser = (role: 'user' | 'admin' = 'user') => ({
  id: Math.floor(Math.random() * 10000),
  username: `user_${Math.random().toString(36).substr(2, 9)}`,
  first_name: role === 'admin' ? 'Admin' : `User${Math.floor(Math.random() * 100)}`,
  last_name: `Last${Math.floor(Math.random() * 100)}`,
  email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
  role
});

const mockSignOut = {
  mutateAsync: vi.fn(),
  isPending: false
};

function renderWithProviders(component: React.ReactElement, options: { route?: string } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  const RouterComponent = options.route ? MemoryRouter : BrowserRouter;
  const routerProps = options.route ? { initialEntries: [options.route] } : {};

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterComponent {...routerProps}>
        {component}
      </RouterComponent>
    </QueryClientProvider>
  );
}

describe('Navigation', () => {
  let currentUser: any;

  beforeEach(() => {
    vi.clearAllMocks();

    // Generate fresh user for each test
    currentUser = generateUser('user');

    const { useAuth } = require('../AuthProvider');
    const { useSignOut, useIsAdmin } = require('../../hooks/api');

    useAuth.mockImplementation(() => ({ user: currentUser }));
    useSignOut.mockReturnValue(mockSignOut);
    useIsAdmin.mockImplementation(() => currentUser?.role === 'admin');
  });

  it('renders the application title', () => {
    renderWithProviders(<Navigation />);

    expect(screen.getByText('JPS Prospect Aggregate')).toBeInTheDocument();
  });

  it('renders basic navigation items for regular users', () => {
    renderWithProviders(<Navigation />);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Advanced' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });

  it('renders admin navigation items for admin users', () => {
    const { useAuth, useIsAdmin } = require('../AuthProvider');

    const adminUser = generateUser('admin');
    useAuth.mockImplementation(() => ({ user: adminUser }));
    useIsAdmin.mockImplementation(() => true);

    renderWithProviders(<Navigation />);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Advanced' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Admin' })).toBeInTheDocument();
  });

  it('highlights active navigation item', () => {
    renderWithProviders(<Navigation />, { route: '/' });

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    expect(dashboardLink).toHaveClass('border-blue-500', 'text-gray-900');
  });

  it('shows inactive styling for non-active navigation items', () => {
    const { useIsAdmin } = require('../../hooks/api');
    useIsAdmin.mockReturnValue(true);

    renderWithProviders(<Navigation />, { route: '/' });

    const advancedLink = screen.getByRole('link', { name: 'Advanced' });
    expect(advancedLink).toHaveClass('border-transparent', 'text-gray-500');
  });

  it('displays user welcome message', () => {
    renderWithProviders(<Navigation />);

    expect(screen.getByText('Welcome,')).toBeInTheDocument();
    // Should display the first name of the current user
    expect(screen.getByText(currentUser.first_name)).toBeInTheDocument();
  });

  it('shows admin badge for admin users', () => {
    const { useAuth, useIsAdmin } = require('../AuthProvider');

    const adminUser = generateUser('admin');
    useAuth.mockImplementation(() => ({ user: adminUser }));
    useIsAdmin.mockImplementation(() => true);

    renderWithProviders(<Navigation />);

    // Admin badge should be displayed for admin users
    const adminBadge = screen.getAllByText('Admin').find(el =>
      el.classList.contains('bg-blue-100') && el.classList.contains('text-blue-800')
    );
    expect(adminBadge).toBeInTheDocument();
  });

  it('does not show admin badge for regular users', () => {
    renderWithProviders(<Navigation />);

    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  it('renders sign out button', () => {
    renderWithProviders(<Navigation />);

    expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument();
  });

  it('calls sign out mutation when sign out button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Navigation />);

    const signOutButton = screen.getByRole('button', { name: 'Sign Out' });
    await user.click(signOutButton);

    expect(mockSignOut.mutateAsync).toHaveBeenCalled();
  });

  it('shows loading state during sign out', () => {
    const { useSignOut } = require('../../hooks/api');
    useSignOut.mockReturnValue({
      ...mockSignOut,
      isPending: true
    });

    renderWithProviders(<Navigation />);

    expect(screen.getByText('Signing out...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Signing out...' })).toBeDisabled();
  });

  it('handles sign out error gracefully', async () => {
    const user = userEvent.setup();
    const mockError = new Error('Sign out failed');
    const { useSignOut } = require('../../hooks/api');

    useSignOut.mockReturnValue({
      ...mockSignOut,
      mutateAsync: vi.fn().mockRejectedValue(mockError)
    });

    renderWithProviders(<Navigation />);

    const signOutButton = screen.getByRole('button', { name: 'Sign Out' });
    await user.click(signOutButton);

    // Error should be handled by the error handler
    expect(useSignOut().mutateAsync).toHaveBeenCalled();
  });

  it('does not render user menu when no user is logged in', () => {
    const { useAuth } = require('../AuthProvider');
    useAuth.mockReturnValue({ user: null });

    renderWithProviders(<Navigation />);

    expect(screen.queryByText('Welcome,')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign Out' })).not.toBeInTheDocument();
  });

  it('applies correct navigation link attributes', () => {
    renderWithProviders(<Navigation />);

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    expect(dashboardLink).toHaveAttribute('href', '/');
  });

  it('applies correct admin navigation link attributes', () => {
    const { useIsAdmin } = require('../../hooks/api');
    useIsAdmin.mockReturnValue(true);

    renderWithProviders(<Navigation />);

    const advancedLink = screen.getByRole('link', { name: 'Advanced' });
    const adminLink = screen.getByRole('link', { name: 'Admin' });

    expect(advancedLink).toHaveAttribute('href', '/advanced');
    expect(adminLink).toHaveAttribute('href', '/admin');
  });

  it('shows responsive design classes', () => {
    renderWithProviders(<Navigation />);

    const nav = screen.getByRole('navigation');
    expect(nav).toHaveClass('bg-white', 'shadow-sm', 'border-b', 'border-gray-200');

    const navContainer = nav.querySelector('.px-4');
    expect(navContainer).toHaveClass('sm:px-6', 'lg:px-8');
  });

  it('hides navigation items on small screens', () => {
    renderWithProviders(<Navigation />);

    const navLinks = screen.getByRole('link', { name: 'Dashboard' }).parentElement;
    expect(navLinks).toHaveClass('hidden', 'sm:ml-6', 'sm:flex');
  });

  it('handles missing user first name gracefully', () => {
    const { useAuth } = require('../AuthProvider');
    const userWithoutFirstName = {
      ...generateUser(),
      first_name: undefined
    };
    useAuth.mockImplementation(() => ({ user: userWithoutFirstName }));

    renderWithProviders(<Navigation />);

    expect(screen.getByText('Welcome,')).toBeInTheDocument();
    // Should not crash when first_name is undefined
  });

  it('applies proper styling to navigation items', () => {
    const { useIsAdmin } = require('../../hooks/api');
    useIsAdmin.mockReturnValue(true);

    renderWithProviders(<Navigation />, { route: '/advanced' });

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    const advancedLink = screen.getByRole('link', { name: 'Advanced' });

    // Active link
    expect(advancedLink).toHaveClass('border-blue-500', 'text-gray-900');

    // Inactive link
    expect(dashboardLink).toHaveClass('border-transparent', 'text-gray-500');
  });

  it('applies hover styles to inactive navigation items', () => {
    renderWithProviders(<Navigation />, { route: '/' });

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    expect(dashboardLink).toHaveClass('hover:border-gray-300', 'hover:text-gray-700');
  });

  it('maintains proper spacing and layout', () => {
    const { useAuth, useIsAdmin } = require('../AuthProvider');

    const adminUser = generateUser('admin');
    useAuth.mockImplementation(() => ({ user: adminUser }));
    useIsAdmin.mockImplementation(() => true);

    renderWithProviders(<Navigation />);

    const userMenu = screen.getByText('Welcome,').closest('.flex');
    expect(userMenu).toHaveClass('items-center', 'space-x-4');

    const navContainer = screen.getByText('Welcome,').closest('.flex.justify-between');
    expect(navContainer).toHaveClass('h-16');
  });

  it('shows correct button variant and size for sign out', () => {
    renderWithProviders(<Navigation />);

    const signOutButton = screen.getByRole('button', { name: 'Sign Out' });
    expect(signOutButton).toHaveClass('border'); // outline variant adds border
  });

  it('handles keyboard navigation', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Navigation />);

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    const signOutButton = screen.getByRole('button', { name: 'Sign Out' });

    await user.tab();
    expect(dashboardLink).toHaveFocus();

    await user.tab();
    expect(signOutButton).toHaveFocus();
  });

  it('supports ARIA accessibility features', () => {
    renderWithProviders(<Navigation />);

    const nav = screen.getByRole('navigation');
    expect(nav).toBeInTheDocument();

    const links = screen.getAllByRole('link');
    links.forEach(link => {
      expect(link).toHaveAttribute('href');
    });

    const button = screen.getByRole('button', { name: 'Sign Out' });
    expect(button).toHaveAttribute('type', 'button');
  });

  it('displays proper text content and structure', () => {
    const { useAuth, useIsAdmin } = require('../AuthProvider');

    const adminUser = generateUser('admin');
    useAuth.mockImplementation(() => ({ user: adminUser }));
    useIsAdmin.mockImplementation(() => true);

    renderWithProviders(<Navigation />);

    // Check title structure
    const title = screen.getByText('JPS Prospect Aggregate');
    expect(title).toHaveClass('text-xl', 'font-semibold', 'text-gray-900');

    // Check user welcome structure
    const welcome = screen.getByText('Welcome,');
    expect(welcome).toHaveClass('text-sm', 'text-gray-700');

    // Check that user name is displayed with proper styling
    const userName = screen.getByText(adminUser.first_name);
    expect(userName).toBeInTheDocument();
  });

  it('renders correctly with different route paths', () => {
    const routes = ['/', '/advanced', '/admin'];

    routes.forEach(route => {
      const { useIsAdmin } = require('../../hooks/api');
      useIsAdmin.mockReturnValue(true);

      renderWithProviders(<Navigation />, { route });

      expect(screen.getByText('JPS Prospect Aggregate')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    });
  });
});
