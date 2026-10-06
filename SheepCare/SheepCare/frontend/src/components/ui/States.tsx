import type { ReactNode } from 'react';
import { WarningCircle } from '@phosphor-icons/react';

/** Estado vacío compuesto: explica qué falta y ofrece el siguiente paso. */
export function EmptyState({
    icon, title, children, action,
}: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
    return (
        <div className="flex flex-col items-center px-6 py-14 text-center">
            <div className="mb-4 flex size-12 items-center justify-center rounded-xl bg-canvas-soft text-ink-3 ring-1 ring-line [&_svg]:size-6">
                {icon}
            </div>
            <h3 className="text-h3">{title}</h3>
            {children && <p className="mt-1.5 max-w-sm text-small text-ink-3">{children}</p>}
            {action && <div className="mt-5">{action}</div>}
        </div>
    );
}

/** Error recuperable: dice qué hacer, no qué falló técnicamente (guía §9). */
export function ErrorState({ title = 'No se pudieron cargar los datos', children, action }: { title?: string; children?: ReactNode; action?: ReactNode }) {
    return (
        <div role="alert" className="flex flex-col items-center px-6 py-12 text-center">
            <div className="mb-4 flex size-12 items-center justify-center rounded-xl bg-danger-bg text-danger-text [&_svg]:size-6">
                <WarningCircle aria-hidden="true" />
            </div>
            <h3 className="text-h3">{title}</h3>
            {children && <p className="mt-1.5 max-w-sm text-small text-ink-3">{children}</p>}
            {action && <div className="mt-5">{action}</div>}
        </div>
    );
}

export function Skeleton({ className = '' }: { className?: string }) {
    return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

/** Esqueleto con la forma de una tabla, para no saltar de un spinner al contenido. */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
    return (
        <div role="status" aria-label="Cargando datos" className="p-5">
            <div className="mb-4 flex gap-4">
                {Array.from({ length: cols }, (_, i) => <Skeleton key={i} className="h-3 flex-1" />)}
            </div>
            <div className="space-y-3">
                {Array.from({ length: rows }, (_, r) => (
                    <div key={r} className="flex gap-4">
                        {Array.from({ length: cols }, (_, c) => <Skeleton key={c} className="h-5 flex-1" />)}
                    </div>
                ))}
            </div>
            <span className="sr-only">Cargando…</span>
        </div>
    );
}
