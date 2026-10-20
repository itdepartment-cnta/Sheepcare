import { Info } from '@phosphor-icons/react';

/** Cifra grande con su etiqueta. Montserrat con cifras tabulares para que alineen. */
export function Stat({
    value, label, tone = 'default', size = 'lg', info,
}: { value: string; label: string; tone?: 'default' | 'info' | 'danger'; size?: 'lg' | 'md'; info?: string }) {
    const color = tone === 'info' ? 'text-info-text' : tone === 'danger' ? 'text-danger-text' : 'text-ink';
    return (
        <div>
            <p className={`font-display tabular ${size === 'lg' ? 'text-display' : 'text-h1'} ${color}`}>{value}</p>
            <p className="mt-1 flex items-center gap-1 text-small text-ink-3">
                {label}
                {info && (
                    <span className="group relative inline-flex">
                        <button
                            type="button"
                            title={info}
                            aria-label={info}
                            className="inline-flex rounded-full text-ink-3 hover:text-ink focus-visible:text-ink"
                        >
                            <Info size={14} aria-hidden="true" />
                        </button>
                        <span
                            role="tooltip"
                            className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden w-max max-w-[16rem] -translate-x-1/2 rounded-md bg-ink px-2 py-1 text-micro text-white group-hover:block group-focus-within:block"
                        >
                            {info}
                        </span>
                    </span>
                )}
            </p>
        </div>
    );
}
