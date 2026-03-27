import {useQuery} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Tag} from 'components/Tag';
import {Pencil, XIcon} from 'lucide-react';
import {cn} from 'utils/cn';

import {tagsQueryOptions, type TagType} from '../../$incidentId/queries/tagsQueryOptions';
import {type ArrayFilterKey} from '../useActiveFilters';

import {useFilterEditor} from './useFilterEditor';

interface TagFilterProps {
  label: string;
  filterKey: ArrayFilterKey;
  tagType: TagType;
}

export function TagFilter({label, filterKey, tagType}: TagFilterProps) {
  const {
    isEditing,
    selected,
    inputValue,
    focusedIndex,
    inputRef,
    setInputValue,
    setFocusedIndex,
    toggle,
    open,
    close,
    handleKeyDown,
  } = useFilterEditor({filterKey});
  const {data: suggestions = []} = useQuery(tagsQueryOptions(tagType));

  const available = suggestions.filter(
    (s: string) =>
      !selected.includes(s) && s.toLowerCase().includes(inputValue.toLowerCase())
  );

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          className={cn(isEditing && 'invisible')}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center">
            {selected.map(v => (
              <Tag
                key={v}
                action={
                  <Button
                    variant="close"
                    size={null}
                    onClick={() => toggle(v)}
                    aria-label={`Remove ${v}`}
                  >
                    <XIcon className="h-3.5 w-3.5" />
                  </Button>
                }
              >
                {v}
              </Tag>
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown(available)}
              placeholder="Add..."
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : selected.length > 0 ? (
          <div className="gap-space-sm flex flex-wrap">
            {selected.map(v => (
              <Tag key={v}>{v}</Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">Any</p>
        )}

        {isEditing && available.length > 0 && (
          <div className="mt-space-xs rounded-radius-md bg-background-primary absolute right-0 left-0 z-50 border border-gray-200 shadow-lg">
            <div className="p-space-sm max-h-[200px] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {available.map((option: string, index: number) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    toggle(option);
                    setInputValue('');
                    setFocusedIndex(0);
                    inputRef.current?.focus();
                  }}
                  className={cn(
                    'w-full text-left px-space-md py-space-sm cursor-pointer rounded-radius-sm text-size-sm',
                    index === focusedIndex
                      ? 'bg-background-secondary'
                      : 'hover:bg-background-transparent-neutral-muted'
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {isEditing && (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={close}
        />
      )}
    </div>
  );
}
