import { useId, useState } from 'react';
import { Info } from '@phosphor-icons/react';

type Tono = 'default' | 'info' | 'warn' | 'danger';

const COLOR: Record<Tono, string> = {
    default: 'text-ink',
    info: 'text-info-text',
    warn: 'text-warn-text',
    danger: 'text-danger-text',
};

/**
 * Cifra grande con su etiqueta. Montserrat con cifras tabulares para que alineen.
 * El texto de ayuda (`info`) es un tooltip que sale al pasar el ratón o al enfocar
 * el botón, se puede cerrar con Esc y se puede recorrer con el puntero sin que
 * desaparezca (WCAG 1.4.13). Va invertido respecto al tema (`bg-ink text-canvas`).
 */
export function Stat({
    value, label, tone = 'default', size = 'lg', info,
}: { value: string; label: string; tone?: Tono; size?: 'lg' | 'md'; info?: string }) {
    const idAyuda = useId();
    const [visible, setVisible] = useState(false);
    return (
        <div>
            <p className={`font-display tabular ${size === 'lg' ? 'text-display' : 'text-h1'} ${COLOR[tone]}`}>{value}</p>
            <p className="mt-1 flex items-center gap-1 text-small text-ink-3">
                {label}
                {info && (
                    <span
                        className="relative inline-flex"
                        onMouseEnter={() => setVisible(true)}
                        onMouseLeave={() => setVisible(false)}
                    >
                        <button
                            type="button"
                            aria-label={`Más información: ${label}`}
                            aria-describedby={idAyuda}
                            onFocus={() => setVisible(true)}
                            onBlur={() => setVisible(false)}
                            onKeyDown={e => { if (e.key === 'Escape') setVisible(false); }}
                            className="inline-flex rounded-full text-ink-3 hover:text-ink focus-visible:text-ink"
                        >
                            <Info size={14} aria-hidden="true" />
                        </button>
                        {/* El relleno inferior cubre el hueco entre el botón y el globo */}
                        <span className={'absolute bottom-full left-1/2 z-10 -translate-x-1/2 pb-1 ' + (visible ? 'block' : 'hidden')}>
                            <span
                                id={idAyuda}
                                role="tooltip"
                                className="block w-max max-w-[16rem] rounded-md bg-ink px-2 py-1 text-micro text-canvas"
                            >
                                {info}
                            </span>
                        </span>
                    </span>
                )}
            </p>
        </div>
    );
}
