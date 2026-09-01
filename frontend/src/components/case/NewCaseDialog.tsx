import { useState } from 'react';
import { Dialog } from '../ui/Dialog';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import type { CaseCreateInput } from '../../types/case';

interface NewCaseDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (input: CaseCreateInput) => Promise<void>;
}

interface FormErrors {
  name?: string;
  case_type?: string;
  username?: string;
  password?: string;
  confirm_password?: string;
  display_name?: string;
  submit?: string;
}

export function NewCaseDialog({ open, onClose, onCreate }: NewCaseDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [form, setForm] = useState<CaseCreateInput>({
    name: '',
    description: '',
    case_type: '',
    username: '',
    password: '',
    confirm_password: '',
    display_name: '',
  });

  const update = (field: keyof CaseCreateInput, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors] || errors.submit) {
      setErrors((prev) => ({ ...prev, [field]: undefined, submit: undefined }));
    }
  };

  const validate = (): boolean => {
    const e: FormErrors = {};
    if (!form.name.trim()) e.name = 'Case name is required';
    if (!form.case_type.trim()) e.case_type = 'Case type is required';
    if (!form.username.trim()) e.username = 'Username is required';
    if (!form.display_name.trim()) e.display_name = 'Display name is required';
    if (!form.password) e.password = 'Password is required';
    else if (form.password.length < 6) e.password = 'Password must be at least 6 characters';
    if (form.password !== form.confirm_password) e.confirm_password = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setIsSubmitting(true);
    try {
      await onCreate(form);
      setForm({ name: '', description: '', case_type: '', username: '', password: '', confirm_password: '', display_name: '' });
      setErrors({});
      onClose();
    } catch (err: any) {
      setErrors((prev) => ({ ...prev, submit: err.message || 'Failed to create case' }));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setForm({ name: '', description: '', case_type: '', username: '', password: '', confirm_password: '', display_name: '' });
      setErrors({});
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} title="New Case" maxWidth="max-w-md">
      <form onSubmit={handleSubmit} className="space-y-5">
        
        {errors.submit && (
          <div className="p-3 bg-red-50 text-red-600 text-sm rounded-md border border-red-100">
            {errors.submit}
          </div>
        )}

        {/* Case Information */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Case Information</p>
          <Input
            label="Case Name"
            placeholder="e.g. Bank Surveillance Review"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            error={errors.name}
            disabled={isSubmitting}
          />
          <Input
            label="Case Type"
            placeholder="e.g. Security Incident"
            value={form.case_type}
            onChange={(e) => update('case_type', e.target.value)}
            error={errors.case_type}
            disabled={isSubmitting}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="case-description" className="text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="case-description"
              className="
                w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900
                placeholder:text-gray-400 resize-none
                transition-colors duration-150
                focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 focus:border-indigo-500
                disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-50
              "
              rows={3}
              placeholder="Brief description of the case..."
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              disabled={isSubmitting}
            />
          </div>
        </div>

        {/* Admin Account */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Case Administrator</p>
          <p className="text-xs text-gray-500">
            The case creator becomes the initial Case Administrator.
          </p>
          <Input
            label="Display Name"
            placeholder="e.g. Aayush Sharma"
            value={form.display_name}
            onChange={(e) => update('display_name', e.target.value)}
            error={errors.display_name}
            disabled={isSubmitting}
          />
          <Input
            label="Username"
            placeholder="e.g. aayush"
            value={form.username}
            onChange={(e) => update('username', e.target.value)}
            error={errors.username}
            autoComplete="off"
            disabled={isSubmitting}
          />
          <Input
            label="Password"
            type="password"
            placeholder="Minimum 6 characters"
            value={form.password}
            onChange={(e) => update('password', e.target.value)}
            error={errors.password}
            autoComplete="new-password"
            disabled={isSubmitting}
          />
          <Input
            label="Confirm Password"
            type="password"
            placeholder="Re-enter password"
            value={form.confirm_password}
            onChange={(e) => update('confirm_password', e.target.value)}
            error={errors.confirm_password}
            autoComplete="new-password"
            disabled={isSubmitting}
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Case'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
