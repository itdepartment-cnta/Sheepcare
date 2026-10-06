import type { ReactNode } from 'react';

interface PageHeaderProps {
    /** Etiqueta pequeña sobre el título: indica a qué parte de la aplicación pertenece. */
    eyebrow?: string;
    title: string;
    description?: string;
    actions?: ReactNode;
}

/**
 * Cabecera común de todas las pantallas. Sustituye a los títulos con emoji: un
 * solo lenguaje visual (icono de línea o nada), jerarquía clara y el título
 * como único <h1> de la página.
 */
export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
    return (
        <header className="reveal mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
            <div className="min-w-0 max-w-2xl">
                {eyebrow && (
                    <p className="mb-2 text-micro font-medium uppercase tracking-[0.1em] text-ink-3">{eyebrow}</p>
                )}
                <h1 className="text-h1">{title}</h1>
                {description && <p className="mt-2 text-body text-ink-2">{description}</p>}
            </div>
            {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
    );
}
