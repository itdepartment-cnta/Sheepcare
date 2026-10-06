import { isAxiosError } from 'axios';

/**
 * Mensaje legible de un error de la API. La guía de CNTA (§9) pide explicar qué
 * hacer y no qué falló técnicamente: si el servidor no dice nada útil, se da una
 * instrucción general en lugar de volcar el error crudo.
 */
export function mensajeDeError(e: unknown, porDefecto = 'No se pudo completar la operación. Inténtalo de nuevo.'): string {
    if (isAxiosError(e)) {
        const detalle = e.response?.data?.detail;
        if (typeof detalle === 'string' && detalle.trim()) return detalle;
        if (Array.isArray(detalle)) {
            const msgs = detalle.map((d: { msg?: string }) => d?.msg).filter(Boolean);
            if (msgs.length) return msgs.join('; ');
        }
        if (!e.response) return 'No hay conexión con el servidor. Revisa la red e inténtalo de nuevo.';
    }
    return porDefecto;
}

/** Código HTTP de un error de la API, si lo hay. */
export const estadoHttp = (e: unknown): number | undefined =>
    isAxiosError(e) ? e.response?.status : undefined;
