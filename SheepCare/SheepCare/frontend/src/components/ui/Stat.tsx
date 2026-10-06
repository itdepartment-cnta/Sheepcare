/** Cifra grande con su etiqueta. Montserrat con cifras tabulares para que alineen. */
export function Stat({
    value, label, tone = 'default', size = 'lg',
}: { value: string; label: string; tone?: 'default' | 'info' | 'danger'; size?: 'lg' | 'md' }) {
    const color = tone === 'info' ? 'text-info-text' : tone === 'danger' ? 'text-danger-text' : 'text-ink';
    return (
        <div>
            <p className={`font-display tabular ${size === 'lg' ? 'text-display' : 'text-h1'} ${color}`}>{value}</p>
            <p className="mt-1 text-small text-ink-3">{label}</p>
        </div>
    );
}
