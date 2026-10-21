import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import { CaretDown } from '@phosphor-icons/react';

/**
 * Campos de formulario de la guía de CNTA (§6.2): etiqueta visible (el
 * placeholder NO sustituye a la etiqueta), ayuda y error enlazados con
 * aria-describedby, y el error con role="alert".
 */

const CONTROL =
    'w-full rounded-control border bg-panel px-3 py-2 text-body text-ink min-h-9 ' +
    'transition-[border-color,box-shadow] duration-200 ease-snap ' +
    'placeholder:text-ink-3 disabled:opacity-55 disabled:cursor-not-allowed ' +
    'hover:border-ink-3 focus:border-ink focus:shadow-[0_0_0_3px_rgba(127,187,0,0.18)]';

interface Base {
    label: string;
    hint?: string;
    error?: string;
    /** Marca el campo como inválido sin texto propio (el mensaje va en otro sitio). */
    invalid?: boolean;
    /** Oculta la etiqueta visualmente (sigue disponible para lectores). */
    hideLabel?: boolean;
    className?: string;
}

function Envoltorio({
    id, label, hint, error, required, hideLabel, className, children,
}: Base & { id: string; required?: boolean; children: ReactNode }) {
    return (
        <div className={'flex flex-col gap-1.5 ' + (className ?? '')}>
            <label htmlFor={id} className={hideLabel ? 'sr-only' : 'text-small font-medium text-ink'}>
                {label}
                {required && <span className="ml-0.5 text-danger-text" aria-hidden="true">*</span>}
            </label>
            {children}
            {hint && !error && <p id={`${id}-hint`} className="text-small text-ink-3">{hint}</p>}
            {error && <p id={`${id}-error`} role="alert" className="text-small font-medium text-danger-text">{error}</p>}
        </div>
    );
}

const describedBy = (id: string, hint?: string, error?: string) =>
    error ? `${id}-error` : hint ? `${id}-hint` : undefined;

type InputProps = Base & Omit<InputHTMLAttributes<HTMLInputElement>, 'className'>;

export function TextField({ label, hint, error, invalid, hideLabel, className, id: idProp, required, ...resto }: InputProps) {
    const auto = useId();
    const id = idProp ?? auto;
    return (
        <Envoltorio id={id} label={label} hint={hint} error={error} required={required} hideLabel={hideLabel} className={className}>
            <input
                id={id}
                required={required}
                aria-invalid={error || invalid ? true : undefined}
                aria-describedby={describedBy(id, hint, error)}
                className={CONTROL + (error || invalid ? ' border-danger' : ' border-control')}
                {...resto}
            />
        </Envoltorio>
    );
}

type SelectProps = Base & Omit<SelectHTMLAttributes<HTMLSelectElement>, 'className'>;

export function SelectField({ label, hint, error, hideLabel, className, id: idProp, required, children, ...resto }: SelectProps) {
    const auto = useId();
    const id = idProp ?? auto;
    return (
        <Envoltorio id={id} label={label} hint={hint} error={error} required={required} hideLabel={hideLabel} className={className}>
            <div className="relative">
                <select
                    id={id}
                    required={required}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={describedBy(id, hint, error)}
                    className={CONTROL + ' appearance-none pr-9 cursor-pointer' + (error ? ' border-danger' : ' border-control')}
                    {...resto}
                >
                    {children}
                </select>
                <CaretDown
                    size={16}
                    aria-hidden="true"
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-3"
                />
            </div>
        </Envoltorio>
    );
}
