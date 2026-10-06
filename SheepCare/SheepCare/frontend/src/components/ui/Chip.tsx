import type { ReactNode } from 'react';

type Tono = 'neutral' | 'ok' | 'warn' | 'danger' | 'info' | 'brand';

/**
 * Etiqueta de estado (guía §6.4). El texto va siempre sobre su fondo del mismo
 * semántico (--*-text sobre --*-bg), que ya está validado a contraste AA. El
 * punto es de color sólido: el significado no depende solo del color porque el
 * texto lo dice.
 */
const TONOS: Record<Tono, { caja: string; punto: string }> = {
    neutral: { caja: 'bg-canvas-soft text-ink-2 border-line', punto: 'bg-ink-3' },
    ok: { caja: 'bg-ok-bg text-ok-text border-transparent', punto: 'bg-ok' },
    warn: { caja: 'bg-warn-bg text-warn-text border-transparent', punto: 'bg-warn' },
    danger: { caja: 'bg-danger-bg text-danger-text border-transparent', punto: 'bg-danger' },
    info: { caja: 'bg-info-bg text-info-text border-transparent', punto: 'bg-info' },
    brand: { caja: 'bg-brand-soft text-brand-700 border-transparent', punto: 'bg-brand-500' },
};

export function Chip({ tone = 'neutral', children, className = '' }: { tone?: Tono; children: ReactNode; className?: string }) {
    const t = TONOS[tone];
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-micro font-medium ${t.caja} ${className}`}
        >
            <span className={`size-1.5 rounded-full ${t.punto}`} aria-hidden="true" />
            {children}
        </span>
    );
}
