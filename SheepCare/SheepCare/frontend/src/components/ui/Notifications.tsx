import { Toaster as Sonner, toast } from 'sonner';
import type { CSSProperties } from 'react';
import type { Tema } from '../../lib/theme';

/**
 * Avisos (guía §6.3). Sustituyen a alert(). Sonner ya expone una región aria-live,
 * y sus colores se enlazan a los tokens semánticos de la guía (el texto sobre su
 * fondo del mismo tono), de modo que el modo oscuro funciona sin más.
 */
export function Toaster({ tema }: { tema: Tema }) {
    return (
        <Sonner
            theme={tema}
            position="bottom-right"
            closeButton
            toastOptions={{ duration: 5000 }}
            style={
                {
                    '--normal-bg': 'var(--panel)',
                    '--normal-text': 'var(--ink)',
                    '--normal-border': 'var(--line)',
                    '--success-bg': 'var(--ok-bg)',
                    '--success-text': 'var(--ok-text)',
                    '--success-border': 'transparent',
                    '--error-bg': 'var(--danger-bg)',
                    '--error-text': 'var(--danger-text)',
                    '--error-border': 'transparent',
                    '--border-radius': 'var(--radius-md)',
                    fontFamily: 'var(--font-sans)',
                } as CSSProperties
            }
        />
    );
}

// eslint-disable-next-line react-refresh/only-export-components -- API imperativa de avisos, a propósito junto al <Toaster>
export const avisar = {
    ok: (titulo: string, descripcion?: string) => toast.success(titulo, { description: descripcion }),
    // Los errores se quedan más tiempo: hay que leerlos y decidir qué hacer (WCAG 2.2.1).
    error: (titulo: string, descripcion?: string) => toast.error(titulo, { description: descripcion, duration: 10000 }),
};
