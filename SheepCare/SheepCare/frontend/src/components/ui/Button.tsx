import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { LinkProps } from 'react-router-dom';
import { CircleNotch } from '@phosphor-icons/react';

type Variante = 'primary' | 'secondary' | 'dark' | 'ghost' | 'danger';
type Tamano = 'md' | 'sm';

/**
 * Botones de la guía de CNTA (§6.1). El primario es lima con texto negro y se
 * reserva para la acción principal de la pantalla: dos primarios en una
 * pantalla es un fallo de diseño.
 */
const BASE =
    'inline-flex items-center justify-center gap-2 rounded-control border font-medium whitespace-nowrap ' +
    'cursor-pointer select-none ' +
    'transition-[background-color,border-color,color,transform] duration-200 ease-snap ' +
    'active:scale-[0.98] disabled:opacity-55 disabled:cursor-not-allowed disabled:active:scale-100';

const VARIANTES: Record<Variante, string> = {
    primary:
        'bg-brand-500 text-brand-on border-brand-500 font-bold hover:bg-brand-600 hover:border-brand-600 ' +
        'disabled:hover:bg-brand-500 disabled:hover:border-brand-500',
    secondary:
        'bg-panel text-ink border-ink-4 hover:border-ink-3 disabled:hover:border-ink-4',
    dark: 'bg-ink text-canvas border-ink hover:bg-ink-2 hover:border-ink-2',
    ghost: 'bg-transparent text-ink-2 border-transparent hover:bg-canvas-soft hover:text-ink',
    danger:
        'bg-panel text-danger-text border-ink-4 hover:bg-danger-bg hover:border-danger disabled:hover:bg-panel',
};

const TAMANOS: Record<Tamano, string> = {
    md: 'px-4 py-2 text-small min-h-9',
    sm: 'px-3 py-1 text-small min-h-7',
};

const clases = (variante: Variante, tamano: Tamano, extra?: string) =>
    [BASE, VARIANTES[variante], TAMANOS[tamano], extra].filter(Boolean).join(' ');

interface Comunes {
    variant?: Variante;
    size?: Tamano;
    icon?: ReactNode;
    className?: string;
}

interface BotonProps extends Comunes, Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
    /** Muestra un indicador y deshabilita el botón mientras dura la acción. */
    loading?: boolean;
}

export function Button({
    variant = 'secondary',
    size = 'md',
    icon,
    loading = false,
    className,
    children,
    disabled,
    type = 'button', // siempre explícito: evita enviar un <form> por accidente
    ...resto
}: BotonProps) {
    return (
        <button
            type={type}
            className={clases(variant, size, className)}
            disabled={disabled || loading}
            aria-busy={loading || undefined}
            {...resto}
        >
            {loading ? <CircleNotch size={16} className="animate-spin" aria-hidden="true" /> : icon}
            {children}
        </button>
    );
}

interface EnlaceProps extends Comunes, Omit<LinkProps, 'className'> {}

/** Enlace de React Router con el aspecto de un botón. */
export function LinkButton({ variant = 'secondary', size = 'md', icon, className, children, ...resto }: EnlaceProps) {
    return (
        <Link className={clases(variant, size, className)} {...resto}>
            {icon}
            {children}
        </Link>
    );
}

interface ExternoProps extends Comunes, Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'className'> {}

/** Enlace a otra aplicación (se abre en pestaña nueva) con el aspecto de un botón. */
export function ExternalButton({ variant = 'secondary', size = 'md', icon, className, children, ...resto }: ExternoProps) {
    return (
        <a target="_blank" rel="noopener noreferrer" className={clases(variant, size, className)} {...resto}>
            {icon}
            {children}
            <span className="sr-only">(se abre en una pestaña nueva)</span>
        </a>
    );
}

interface BotonIconoProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className' | 'aria-label'> {
    /** Obligatorio: un botón solo de icono no tiene otro nombre accesible. */
    label: string;
    children: ReactNode;
    tone?: 'neutral' | 'danger';
}

/** Botón solo de icono, con área de pulsación de 32 px (la guía pide al menos 24). */
export function IconButton({ label, children, tone = 'neutral', type = 'button', ...resto }: BotonIconoProps) {
    const color =
        tone === 'danger'
            ? 'text-ink-3 hover:text-danger-text hover:bg-danger-bg'
            : 'text-ink-3 hover:text-ink hover:bg-canvas-soft';
    return (
        <button
            type={type}
            aria-label={label}
            title={label}
            className={
                'inline-flex size-8 items-center justify-center rounded-control transition-[background-color,color,transform] ' +
                'duration-200 ease-snap active:scale-95 cursor-pointer ' +
                color
            }
            {...resto}
        >
            {children}
        </button>
    );
}
