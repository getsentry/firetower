import {useState} from 'react';
import {Button} from 'components/Button';
import {Input} from 'components/Input';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {Tag} from 'components/Tag';
import {ChevronDownIcon, XIcon} from 'lucide-react';

interface TextInputFilterProps {
  label: string;
  values: string[];
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
  placeholder?: string;
}

export function TextInputFilter({
  label,
  values,
  onAdd,
  onRemove,
  placeholder = 'Type and press Enter',
}: TextInputFilterProps) {
  const [input, setInput] = useState('');

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      const trimmed = input.trim();
      if (trimmed && !values.includes(trimmed)) {
        onAdd(trimmed);
      }
      setInput('');
    }
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm">
          {label}
          {values.length > 0 && (
            <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
              {values.length}
            </span>
          )}
          <ChevronDownIcon className="ml-space-2xs h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64">
        <Input
          placeholder={placeholder}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        {values.length > 0 && (
          <div className="mt-space-sm flex flex-wrap gap-space-xs">
            {values.map(v => (
              <Tag
                key={v}
                action={
                  <button
                    type="button"
                    onClick={() => onRemove(v)}
                    className="text-content-secondary hover:text-content-primary cursor-pointer"
                  >
                    <XIcon className="h-3 w-3" />
                  </button>
                }
              >
                {v}
              </Tag>
            ))}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
