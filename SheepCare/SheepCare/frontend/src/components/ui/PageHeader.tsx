import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

// La primera pantalla no roba el foco; las siguientes (navegación) sí lo llevan al título.
let primeraCarga = true;

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
 * como único <h1> de la página. También pone el título de la pestaña y, al navegar,
 * lleva el foco al <h1>: en una aplicación de una sola página es lo que avisa a un
 * lector de pantalla del cambio de pantalla (WCAG 2.4.2).
 */
export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
    const encabezado = useRef<HTMLHeadingElement>(null);

    useEffect(() => {
        document.title = `${title} · SheepCare`;
        if (primeraCarga) {
            primeraCarga = false;
            return;
        }
        encabezado.current?.focus({ preventScroll: true });
    }, [title]);

    return (
        <header className="reveal mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
            <div className="min-w-0 max-w-2xl">
                {eyebrow && (
                    <p className="mb-2 text-micro font-medium uppercase tracking-[0.1em] text-ink-3">{eyebrow}</p>
                )}
                <h1 ref={encabezado} tabIndex={-1} className="text-h1 outline-none">{title}</h1>
                {description && <p className="mt-2 text-body text-ink-2">{description}</p>}
            </div>
            {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
    );
}
