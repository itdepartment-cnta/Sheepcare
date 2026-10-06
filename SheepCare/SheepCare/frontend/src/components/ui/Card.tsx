import type { ReactNode } from 'react';

interface CardProps {
    children: ReactNode;
    className?: string;
    /** `flat`: panel simple de la guía, para contenido secundario. Por defecto, doble bisel. */
    flat?: boolean;
    /** Relleno interior. Desactívalo si dentro va una tabla a sangre. */
    padded?: boolean;
    /** Posición en la entrada escalonada (retraso = índice × 70 ms). */
    index?: number;
    as?: 'div' | 'section' | 'article';
}

/**
 * Contenedor principal. Por defecto usa el «doble bisel»: un marco exterior y un
 * núcleo interior con radios concéntricos (18 y 14 px, la escala de la guía),
 * que da profundidad sin recurrir a sombras fuertes. Úsalo para los bloques que
 * organizan la pantalla; para contenido auxiliar, `flat`.
 */
export function Card({ children, className = '', flat = false, padded = true, index, as: Tag = 'div' }: CardProps) {
    const estilo = index == null ? undefined : ({ '--i': index } as React.CSSProperties);
    const animacion = index == null ? '' : ' reveal';

    if (flat) {
        return (
            <Tag className={`panel ${padded ? 'p-5' : ''}${animacion} ${className}`} style={estilo}>
                {children}
            </Tag>
        );
    }
    return (
        <Tag className={`bezel${animacion} ${className}`} style={estilo}>
            <div className="bezel-core h-full">
                <div className={padded ? 'p-5' : ''}>{children}</div>
            </div>
        </Tag>
    );
}

interface CardHeaderProps {
    title: string;
    description?: string;
    icon?: ReactNode;
    actions?: ReactNode;
    /** Nivel semántico del título; por defecto h2. */
    as?: 'h2' | 'h3';
}

export function CardHeader({ title, description, icon, actions, as: Titulo = 'h2' }: CardHeaderProps) {
    return (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
                {icon && (
                    <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand-700">
                        {icon}
                    </span>
                )}
                <div>
                    <Titulo className="text-h3">{title}</Titulo>
                    {description && <p className="mt-1 max-w-prose text-small text-ink-3">{description}</p>}
                </div>
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
    );
}
