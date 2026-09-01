import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { useAuth } from '../../hooks/useAuth';
import { DrishtikLogo } from '../../assets/DrishtikLogo';

export function CaseAuthScreen() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { login, isLoading, error, clearError } = useAuth();
  
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [validationError, setValidationError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setValidationError('');

    if (!username.trim()) {
      setValidationError('Username is required');
      return;
    }
    if (!password) {
      setValidationError('Password is required');
      return;
    }

    try {
      if (caseId) {
        await login({ username, password }, caseId);
        navigate(`/case/${caseId}`);
      }
    } catch {
      // Error is handled by useAuth state
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="sm:mx-auto sm:w-full sm:max-w-md"
      >
        <div className="flex justify-center mb-6">
          <DrishtikLogo size={48} className="text-indigo-600" />
        </div>
        
        <div className="text-center mb-8">
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-gray-900">
            Case Authentication
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Enter credentials to access case ID <span className="font-mono text-gray-700 font-medium">{caseId}</span>
          </p>
        </div>

        <div className="bg-white py-8 px-4 shadow-sm sm:rounded-lg sm:px-10 border border-gray-200">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <Input
              label="Username"
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                clearError();
                setValidationError('');
              }}
              disabled={isLoading}
            />

            <div className="relative">
              <Input
                label="Password"
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  clearError();
                  setValidationError('');
                }}
                disabled={isLoading}
              />
              <button
                type="button"
                className="absolute right-3 top-[28px] text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:text-indigo-600"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {(error || validationError) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="text-sm text-red-600 bg-red-50 p-3 rounded-md border border-red-100"
                role="alert"
              >
                {validationError || error}
              </motion.div>
            )}

            <div className="pt-2">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
                    Signing in...
                  </>
                ) : (
                  'Sign In'
                )}
              </Button>
            </div>

            <div className="mt-6">
              <Button
                variant="ghost"
                type="button"
                className="w-full"
                onClick={() => navigate('/')}
                disabled={isLoading}
                icon={<ArrowLeft size={16} />}
              >
                Back to Case Manager
              </Button>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  );
}
