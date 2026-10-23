import { useEffect, useId, useRef, useState } from 'react';
import { FileXls, UploadSimple, X } from '@phosphor-icons/react';
import { numero } from '../../lib/format';

interface Props {
    label: string;
    /** Extensiones aceptadas, separadas por comas: ".xlsx,.xls". */
    accept: string;
    file: File | null;
    onFile: (file: File | null) => void;
    hint?: string;
    required?: boolean;
}

const tamano = (bytes: number) =>
    bytes < 1024 * 1024 ? `${numero(bytes / 1024, 0)} KB` : `${numero(bytes / (1024 * 1024), 1)} MB`;

/**
 * Selector de archivo con arrastrar y soltar. El <input type="file"> real sigue
 * ahí, oculto visualmente pero accesible por teclado y lector de pantalla: la
 * etiqueta que lo envuelve es la zona pulsable, y el foco se ve en ella.
 */
export function FileDrop({ label, accept, file, onFile, hint, required }: Props) {
    const id = useId();
    const entrada = useRef<HTMLInputElement>(null);
    const [encima, setEncima] = useState(false);

    // Si desde fuera se vacía el archivo (tras subirlo), se vacía también el input.
    useEffect(() => {
        if (!file && entrada.current) entrada.current.value = '';
    }, [file]);

    const permitido = (f: File) =>
        accept.split(',').some(ext => f.name.toLowerCase().endsWith(ext.trim().toLowerCase()));

    return (
        <div className="flex flex-col gap-1.5">
            <span id={`${id}-etiqueta`} className="text-small font-medium text-ink">
                {label}
                {required && <span className="ml-0.5 text-danger-text" aria-hidden="true">*</span>}
            </span>

            <label
                htmlFor={id}
                onDragOver={e => { e.preventDefault(); setEncima(true); }}
                onDragLeave={() => setEncima(false)}
                onDrop={e => {
                    e.preventDefault();
                    setEncima(false);
                    const f = e.dataTransfer.files?.[0];
                    if (f && permitido(f)) onFile(f);
                }}
                className={
                    'flex min-h-36 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center ' +
                    'transition-[background-color,border-color] duration-200 ease-snap ' +
                    'has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-brand-600 ' +
                    (encima
                        ? 'border-brand-600 bg-brand-soft'
                        : 'border-control bg-canvas-soft hover:border-ink-3')
                }
            >
                <input
                    id={id}
                    ref={entrada}
                    type="file"
                    accept={accept}
                    required={required}
                    aria-describedby={hint ? `${id}-ayuda` : undefined}
                    onChange={e => onFile(e.target.files?.[0] ?? null)}
                    className="sr-only"
                />
                {file ? (
                    <span className="flex items-center gap-3 text-left">
                        <FileXls size={28} aria-hidden="true" className="shrink-0 text-brand-700" />
                        <span className="min-w-0">
                            <span className="block truncate text-body font-medium text-ink">{file.name}</span>
                            <span className="block text-small text-ink-3">{tamano(file.size)} · pulsa para cambiarlo</span>
                        </span>
                    </span>
                ) : (
                    <>
                        <UploadSimple size={24} aria-hidden="true" className="text-ink-3" />
                        <span className="text-body text-ink">
                            <span className="font-medium text-brand-700 underline underline-offset-2">Elige un archivo</span>{' '}
                            o arrástralo aquí
                        </span>
                        <span className="text-small text-ink-3">{accept.split(',').join(' · ')}</span>
                    </>
                )}
            </label>

            {/* Siempre ocupa su sitio: al adjuntar un archivo no debe crecer la tarjeta */}
            <div className="h-6">
                {file && (
                    <button
                        type="button"
                        onClick={() => onFile(null)}
                        className="inline-flex w-fit cursor-pointer items-center gap-1 rounded-sm text-small text-ink-3 transition-colors duration-200 ease-snap hover:text-ink"
                    >
                        <X size={14} aria-hidden="true" /> Quitar archivo
                    </button>
                )}
            </div>
            {hint && <p id={`${id}-ayuda`} className="text-small text-ink-3">{hint}</p>}
        </div>
    );
}
