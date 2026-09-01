import {useState} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Input} from 'components/Input';
import {Label} from 'components/Label';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {currentUserQueryOptions} from '../queries/currentUserQueryOptions';
import {createIncidentMutationOptions} from '../queries/createIncidentMutationOptions';
import {SeveritySchema} from '../types';

const overlay = cva(['fixed', 'inset-0', 'z-50', 'bg-black/50']);

const dialog = cva([
  'fixed',
  'top-1/2',
  'left-1/2',
  '-translate-x-1/2',
  '-translate-y-1/2',
  'z-50',
  'w-full',
  'max-w-md',
  'rounded-radius-lg',
  'bg-background-primary',
  'p-space-2xl',
  'shadow-xl',
]);

interface CreateIncidentDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreateIncidentDialog({isOpen, onClose}: CreateIncidentDialogProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const {data: currentUser} = useQuery(currentUserQueryOptions());
  const createIncident = useMutation(createIncidentMutationOptions(queryClient));

  const [title, setTitle] = useState('');
  const [severity, setSeverity] = useState('P3');
  const [description, setDescription] = useState('');

  const handleClose = () => {
    setTitle('');
    setSeverity('P3');
    setDescription('');
    createIncident.reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser || !title.trim()) return;

    const result = await createIncident.mutateAsync({
      title: title.trim(),
      severity,
      description: description.trim() || undefined,
      captain: currentUser.email,
      reporter: currentUser.email,
    });

    handleClose();
    navigate({to: '/$incidentId', params: {incidentId: result.id}});
  };

  if (!isOpen) return null;

  return (
    <>
      <div className={cn(overlay())} onClick={handleClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-incident-title"
        className={cn(dialog())}
      >
        <h2
          id="create-incident-title"
          className="mb-space-xl text-content-headings text-lg font-semibold"
        >
          Create Incident
        </h2>
        <form onSubmit={handleSubmit} className="gap-space-lg flex flex-col">
          <div className="gap-space-xs flex flex-col">
            <Label htmlFor="incident-title">Title</Label>
            <Input
              id="incident-title"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Brief description of the incident"
              required
              autoFocus
            />
          </div>
          <div className="gap-space-xs flex flex-col">
            <Label htmlFor="incident-severity">Severity</Label>
            <select
              id="incident-severity"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
              className={cn(
                'border-gray-200 h-8 w-full rounded-radius-md border bg-transparent px-3 py-1 text-size-sm',
                'focus:outline-auto'
              )}
            >
              {SeveritySchema.options.map(option => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div className="gap-space-xs flex flex-col">
            <Label htmlFor="incident-description">
              Description <span className="text-content-disabled font-normal">(optional)</span>
            </Label>
            <textarea
              id="incident-description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What is happening? What is the impact?"
              rows={3}
              className={cn(
                'border-gray-200 w-full rounded-radius-md border bg-transparent px-3 py-2 text-size-sm',
                'placeholder:text-content-disabled',
                'focus:outline-auto',
                'resize-y'
              )}
            />
          </div>
          {createIncident.isError && (
            <p className="text-size-sm text-red-600">
              Failed to create incident. Please try again.
            </p>
          )}
          <div className="gap-space-md flex justify-end">
            <Button variant="secondary" onClick={handleClose} type="button">
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={!title.trim()}
              loading={createIncident.isPending}
            >
              Create
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}
