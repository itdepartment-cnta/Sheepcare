/**
 * Formato de fechas y números según la guía de CNTA (§9): es-ES, dd/MM/yyyy,
 * miles con punto y decimales con coma. Una sola fuente para toda la interfaz.
 */

const FECHA = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
const FECHA_LARGA = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
const FECHA_HORA = new Intl.DateTimeFormat('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});
const DIA_CORTO = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric' });
const HORA = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' });

const valida = (d: Date) => !Number.isNaN(d.getTime());

/**
 * SQLite guarda las marcas de tiempo en UTC y sin zona («2026-10-23 11:30:00»), y
 * `new Date` las tomaría por hora local: se verían con la diferencia horaria de retraso.
 * Sin zona explícita (Z o ±hh:mm) se interpretan como UTC.
 */
const aFecha = (iso: string): Date => {
    const sinZona = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(iso.trim());
    return new Date(sinZona ? `${iso.trim().replace(' ', 'T')}Z` : iso);
};

export const fecha = (iso?: string | null): string => {
    if (!iso) return '—';
    const d = aFecha(iso);
    return valida(d) ? FECHA.format(d) : '—';
};

export const fechaLarga = (d: Date = new Date()): string => FECHA_LARGA.format(d);

export const fechaHora = (iso?: string | null): string => {
    if (!iso) return '—';
    const d = aFecha(iso);
    return valida(d) ? FECHA_HORA.format(d) : '—';
};

export const diaCorto = (d: Date): string => DIA_CORTO.format(d).replace('.', '');
export const hora = (d: Date): string => HORA.format(d);

export const numero = (n: number | null | undefined, decimales = 0): string =>
    n == null || Number.isNaN(n)
        ? '—'
        : new Intl.NumberFormat('es-ES', {
              minimumFractionDigits: decimales,
              maximumFractionDigits: decimales,
          }).format(n);

/** 0-1 → «87 %» (con espacio fino antes del símbolo, como indica la guía). */
export const porcentaje = (fraccion: number | null | undefined, decimales = 0): string =>
    fraccion == null ? '—' : `${numero(fraccion * 100, decimales)}\u00A0%`;
