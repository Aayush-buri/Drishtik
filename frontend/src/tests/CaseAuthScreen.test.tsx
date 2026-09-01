import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
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
      <BrowserRouter>
        <CaseAuthScreen />
      </BrowserRouter>
    );
  };

  it('renders correctly', () => {
    renderComponent();
    expect(screen.getByLabelText(/Username/i)).toBeDefined();
    expect(screen.getByLabelText(/Password/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeDefined();
  });

  it('shows error if username is empty', async () => {
    renderComponent();
    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(screen.getByText('Username is required')).toBeDefined();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows error if password is empty', async () => {
    renderComponent();
    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'user1' } });
    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(screen.getByText('Password is required')).toBeDefined();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('calls login on valid submission', async () => {
    renderComponent();
    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'user1' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'pass123' } });
    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));
    
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });
});
