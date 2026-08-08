import React from 'react';
import { Input } from './input';
import { Label } from './label';
import { Textarea } from './textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select';
import { cn } from '@/lib/utils';

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement> {
  label: string;
  error?: string;
  span?: boolean;
  type?: string;
  options?: { value: string; label: string }[];
  icon?: React.ReactNode;
}

const fieldClasses = "bg-muted border-transparent focus-visible:border-primary/40 focus-visible:bg-card focus-visible:ring-primary/15 shadow-sm";

export default function FormInput({
  label,
  error,
  span = false,
  type = 'text',
  options,
  className = '',
  name,
  value,
  onChange,
  placeholder,
  disabled,
  required,
  icon,
  ...props
}: FormInputProps) {
  const isSelect = type === 'select';
  const isTextArea = type === 'textarea';

  const emitChange = (newValue: string | null) => {
    onChange?.({
      target: { name, value: newValue ?? '' },
    } as unknown as React.ChangeEvent<HTMLSelectElement>);
  };

  return (
    <div className={cn("flex flex-col gap-1.5", span ? "md:col-span-2" : "col-span-1")}>
      <Label className="text-xs font-bold text-foreground">
        {label}
        {required && <span className="text-primary">*</span>}
      </Label>

      {isSelect ? (
        <Select
          value={value as string}
          onValueChange={emitChange}
          disabled={disabled}
        >
          <SelectTrigger
            className={cn(fieldClasses, "w-full", error && "border-destructive focus-visible:border-destructive")}
          >
            <SelectValue placeholder={placeholder || 'Select...'} />
          </SelectTrigger>
          <SelectContent>
            {options?.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : isTextArea ? (
        <Textarea
          name={name}
          value={value}
          onChange={onChange as React.ChangeEventHandler<HTMLTextAreaElement>}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className={cn(fieldClasses, "resize-none", error && 'border-destructive focus-visible:border-destructive')}
        />
      ) : (
        <div className="relative">
          {icon && (
            <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
              {icon}
            </span>
          )}
          <Input
            type={type}
            name={name}
            value={value}
            onChange={onChange as React.ChangeEventHandler<HTMLInputElement>}
            placeholder={placeholder}
            disabled={disabled}
            required={required}
            className={cn(
              fieldClasses,
              icon && "pl-8",
              error && 'border-destructive focus-visible:border-destructive',
              className
            )}
            {...(props as React.InputHTMLAttributes<HTMLInputElement>)}
          />
        </div>
      )}

      {error && <span className="text-[10px] font-bold text-destructive animate-slide-in">{error}</span>}
    </div>
  );
}
