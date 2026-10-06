import type { ReactNode } from 'react';

/**
 * Tabla de datos (guía §6.5). Cabeceras con scope="col", cifras alineadas a la
 * derecha y en tabulares, y una leyenda solo para lectores de pantalla. Va dentro
 * de una tarjeta sin relleno; el desplazamiento horizontal queda contenido.
 */
export function Table({
    caption, children, maxHeight, minWidth = '40rem',
}: { caption: string; children: ReactNode; maxHeight?: string; minWidth?: string }) {
    return (
        <div className="overflow-auto" style={{ maxHeight }}>
            <table className="w-full border-collapse text-body" style={{ minWidth }}>
                <caption className="sr-only">{caption}</caption>
                {children}
            </table>
        </div>
    );
}

export function Th({ children, align = 'left' }: { children?: ReactNode; align?: 'left' | 'right' }) {
    return (
        <th
            scope="col"
            className={
                'sticky top-0 z-[1] border-b border-line bg-canvas-soft px-4 py-3 text-micro font-medium uppercase tracking-[0.1em] text-ink-3 ' +
                (align === 'right' ? 'text-right' : 'text-left')
            }
        >
            {children}
        </th>
    );
}

export function Tr({ children }: { children: ReactNode }) {
    return (
        <tr className="border-b border-line-soft transition-colors duration-200 ease-snap last:border-0 hover:bg-canvas-soft">
            {children}
        </tr>
    );
}

interface TdProps {
    children?: ReactNode;
    /** Cifras: derecha y tabulares. */
    numeric?: boolean;
    muted?: boolean;
    mono?: boolean;
    strong?: boolean;
}

export function Td({ children, numeric, muted, mono, strong }: TdProps) {
    const clases = [
        'px-4 py-3 align-middle',
        numeric ? 'text-right tabular' : '',
        muted ? 'text-ink-3' : 'text-ink',
        mono ? 'font-mono text-small' : '',
        strong ? 'font-medium' : '',
    ];
    return <td className={clases.filter(Boolean).join(' ')}>{children}</td>;
}
