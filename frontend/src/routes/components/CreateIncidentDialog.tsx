import {useCallback, useEffect, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Input} from 'components/Input';
import {Label} from 'components/Label';
import {useBodyScrollLock} from 'utils/useBodyScrollLock';

import {
  background,
  border,
  content,
  fontSize,
  radius,
  space,
} from '../../styles/tokens.stylex';
import {createIncidentMutationOptions} from '../queries/createIncidentMutationOptions';
import {currentUserQueryOptions} from '../queries/currentUserQueryOptions';
import {SeveritySchema} from '../types';

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
  const {isPending, reset} = createIncident;

  const handleClose = useCallback(() => {
    if (isPending) return;
    setTitle('');
    setSeverity('P3');
    setDescription('');
    reset();
    onClose();
  }, [isPending, reset, onClose]);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        handleClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, handleClose]);

  useBodyScrollLock(isOpen);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser || !title.trim() || createIncident.isPending) return;

    try {
      const result = await createIncident.mutateAsync({
        title: title.trim(),
        severity,
        description: description.trim() || undefined,
        captain: currentUser.email,
        reporter: currentUser.email,
      });

      handleClose();
      navigate({to: '/$incidentId', params: {incidentId: result.id}});
    } catch {
      return;
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div {...stylex.props(styles.overlay)} onClick={handleClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-incident-title"
        {...stylex.props(styles.dialog)}
      >
        <h2 id="create-incident-title" {...stylex.props(styles.title)}>
          Create Incident
        </h2>
        <form onSubmit={handleSubmit} {...stylex.props(styles.form)}>
          <div {...stylex.props(styles.field)}>
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
          <div {...stylex.props(styles.field)}>
            <Label htmlFor="incident-severity">Severity</Label>
            <select
              id="incident-severity"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
              {...stylex.props(styles.select)}
            >
              {SeveritySchema.options.map(option => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div {...stylex.props(styles.field)}>
            <Label htmlFor="incident-description">
              Description <span {...stylex.props(styles.optional)}>(optional)</span>
            </Label>
            <textarea
              id="incident-description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What is happening? What is the impact?"
              rows={3}
              {...stylex.props(styles.description)}
            />
          </div>
          {createIncident.isError && (
            <p {...stylex.props(styles.error)}>
              Failed to create incident. Please try again.
            </p>
          )}
          <div {...stylex.props(styles.actions)}>
            <Button variant="secondary" onClick={handleClose} type="button">
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={!title.trim() || !currentUser}
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

const styles = stylex.create({
  title: {
    marginBottom: space.xl,
    color: content.headings,
    fontSize: 18,
    lineHeight: '28px',
    fontWeight: 600,
  },
  form: {gap: space.lg, display: 'flex', flexDirection: 'column'},
  field: {gap: space.xs, display: 'flex', flexDirection: 'column'},
  optional: {color: content.disabled, fontWeight: 400},
  error: {fontSize: fontSize.sm, color: '#dc2626'},
  actions: {gap: space.md, display: 'flex', justifyContent: 'flex-end'},
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 50,
    backgroundColor: 'rgb(0 0 0 / 0.5)',
  },
  dialog: {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    zIndex: 50,
    width: '100%',
    maxWidth: 448,
    borderRadius: radius.lg,
    backgroundColor: background.primary,
    padding: space['2xl'],
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  },
  select: {
    borderColor: border.secondary,
    height: 32,
    width: '100%',
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'solid',
    backgroundColor: 'transparent',
    paddingInline: 12,
    paddingBlock: 4,
    fontSize: fontSize.sm,
  },
  description: {
    borderColor: border.secondary,
    width: '100%',
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'solid',
    backgroundColor: 'transparent',
    paddingInline: 12,
    paddingBlock: 8,
    fontSize: fontSize.sm,
    color: {default: null, '::placeholder': content.disabled},
    resize: 'vertical',
  },
});
