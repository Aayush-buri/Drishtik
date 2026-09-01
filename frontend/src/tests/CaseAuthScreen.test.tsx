import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CaseAuthScreen } from '../components/case/CaseAuthScreen';
import { useAuth } from '../hooks/useAuth';

// Mock useAuth
vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

const mockLogin = vi.fn();
const mockClearError = vi.fn();

describe('CaseAuthScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      login: mockLogin,
      isLoading: false,
      error: null,
      clearError: mockClearError,
    });
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={['/auth/CASE-123']}>
        <Routes>
          <Route path="/auth/:caseId" element={<CaseAuthScreen />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders correctly', () => {
    renderComponent();
    expect(screen.getByLabelText('Username')).toBeDefined();
    expect(screen.getByLabelText('Password')).toBeDefined();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeDefined();
  });

  it('shows error if username is empty', async () => {
    renderComponent();
    fireEvent.submit(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(screen.getByText('Username is required')).toBeDefined();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows error if password is empty', async () => {
    renderComponent();
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'user1' } });
    fireEvent.submit(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(screen.getByText('Password is required')).toBeDefined();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('calls login on valid submission', async () => {
    renderComponent();
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'user1' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pass123' } });
    fireEvent.submit(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });
});
