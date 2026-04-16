import {useCallback, useEffect, useRef, useState} from 'react';
import {useNavigate} from '@tanstack/react-router';

import {useActiveFilters, type ArrayFilterKey} from '../useActiveFilters';

interface UseFilterEditorOptions {
  filterKey: ArrayFilterKey;
  onClose?: () => void;
  onOpen?: () => void;
}

// Just a helper hook to prevent duplicate code in the different editor types.
export function useFilterEditor({filterKey, onClose, onOpen}: UseFilterEditorOptions) {
  const navigate = useNavigate({from: '/'});
  const {search} = useActiveFilters();
  const committed = ((search[filterKey] as string[] | undefined) ?? []) as string[];
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [displayValues, setDisplayValues] = useState<string[]>(committed);
  const [prevCommitted, setPrevCommitted] = useState<string[]>(committed);
  const draftRef = useRef<string[]>(draft);
  const onCloseRef = useRef(onClose);
  const onOpenRef = useRef(onOpen);
  useEffect(() => {
    onCloseRef.current = onClose;
    onOpenRef.current = onOpen;
  });
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const committedChanged =
    committed.length !== prevCommitted.length ||
    !committed.every((v, i) => prevCommitted[i] === v);
  if (committedChanged) {
    setPrevCommitted(committed);
    if (!isEditing) {
      setDisplayValues(committed);
    }
  }

  const selected = isEditing ? draft : displayValues;

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  const toggle = useCallback((value: string) => {
    setDraft(prev =>
      prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]
    );
  }, []);

  const remove = useCallback(
    (value: string) => {
      setDisplayValues(prev => prev.filter(v => v !== value));
      navigate({
        to: '/',
        search: s => {
          const current = ((s[filterKey] as string[] | undefined) ?? []).filter(
            v => v !== value
          );
          return {
            ...s,
            [filterKey]: current.length > 0 ? current : undefined,
          };
        },
        replace: true,
      });
    },
    [navigate, filterKey]
  );

  const close = useCallback(() => {
    const current = draftRef.current;
    setDisplayValues(current);
    setIsEditing(false);
    setInputValue('');
    setFocusedIndex(0);
    onCloseRef.current?.();
    navigate({
      to: '/',
      search: s => ({
        ...s,
        [filterKey]: current.length > 0 ? current : undefined,
      }),
      replace: true,
    });
  }, [navigate, filterKey]);

  const open = () => {
    setDisplayValues(committed);
    setDraft(committed);
    setIsEditing(true);
    setInputValue('');
    setFocusedIndex(0);
    onOpenRef.current?.();
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isEditing, close]);

  const handleKeyDown = (identities: string[]) => (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (identities.length > 0) {
          setFocusedIndex(prev => (prev + 1) % identities.length);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (identities.length > 0) {
          setFocusedIndex(prev => (prev - 1 + identities.length) % identities.length);
        }
        break;
      case 'Enter':
        if (focusedIndex >= 0 && focusedIndex < identities.length) {
          e.preventDefault();
          toggle(identities[focusedIndex]);
          setInputValue('');
          setFocusedIndex(0);
          inputRef.current?.focus();
        } else if (!inputValue.trim()) {
          close();
        }
        break;
      case 'Backspace':
        if (inputValue === '' && selected.length > 0) {
          toggle(selected[selected.length - 1]);
        }
        break;
    }
  };

  return {
    isEditing,
    selected,
    inputValue,
    focusedIndex,
    inputRef,
    setInputValue,
    setFocusedIndex,
    toggle,
    remove,
    open,
    close,
    handleKeyDown,
  };
}
