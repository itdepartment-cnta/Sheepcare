import { useEffect, useId, useRef } from 'react';
import { Button } from './Button';

interface Props {
    open: boolean;
    title: string;
    children?: React.ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
    /** Acción destructiva: el botón de confirmar se muestra en rojo. */
    danger?: boolean;
    loading?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

/**
 * Diálogo de confirmación. Sustituye a window.confirm(), que la guía de CNTA
 * prohíbe (§6.6). Usa el elemento <dialog> en modo modal, que ya da lo que la
 * guía exige: foco atrapado, Esc para cerrar y el resto de la página inerte.
 * El foco inicial va en «Cancelar», la opción segura.
 */
export function ConfirmDialog({
    open, title, children, confirmLabel = 'Eliminar', cancelLabel = 'Cancelar',
    danger = true, loading = false, onConfirm, onCancel,
}: Props) {
    const ref = useRef<HTMLDialogElement>(null);
    const idTitulo = useId();
    const idTexto = useId();

    useEffect(() => {
        const d = ref.current;
        if (!d) return;
        if (open && !d.open) d.showModal();
        if (!open && d.open) d.close();
    }, [open]);

    return (
        <dialog
            ref={ref}
            aria-labelledby={idTitulo}
            aria-describedby={children ? idTexto : undefined}
            // Esc y el cierre del propio elemento llegan por aquí
            onClose={onCancel}
            // Clic en el fondo oscuro (el propio <dialog>) = cancelar
            onClick={e => { if (e.target === ref.current && !loading) onCancel(); }}
            className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-xl border border-line bg-panel p-0 text-ink shadow-lg"
        >
            <div className="p-6">
                <h2 id={idTitulo} className="text-h3">{title}</h2>
                {children && <div id={idTexto} className="mt-2 text-body text-ink-2">{children}</div>}
            </div>
            <div className="flex justify-end gap-2 border-t border-line-soft bg-canvas-soft px-6 py-4">
                <Button autoFocus onClick={onCancel} disabled={loading}>{cancelLabel}</Button>
                <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
                    {confirmLabel}
                </Button>
            </div>
        </dialog>
    );
}
