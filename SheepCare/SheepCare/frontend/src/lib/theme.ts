/**
 * Tema claro/oscuro. La guía de CNTA define los dos juegos de tokens; el
 * atributo `data-theme="dark"` en <html> activa el oscuro. index.html lo aplica
 * antes del primer pintado para que no parpadee.
 *
 * El almacenamiento puede no estar disponible (modo privado, datos bloqueados):
 * todo está envuelto y la aplicación funciona igual sin él.
 */
import { useCallback, useEffect, useState } from 'react';

export type Tema = 'light' | 'dark';
const CLAVE = 'sheepcare-theme';

const leer = (): Tema | null => {
    try {
        const v = localStorage.getItem(CLAVE);
        return v === 'dark' || v === 'light' ? v : null;
    } catch {
        return null;
    }
};

const preferidoPorElSistema = (): Tema =>
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';

const aplicar = (t: Tema) => {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
};

export function useTema() {
    const [tema, setTema] = useState<Tema>(() => leer() ?? preferidoPorElSistema());

    useEffect(() => {
        aplicar(tema);
    }, [tema]);

    const alternar = useCallback(() => {
        setTema(actual => {
            const siguiente: Tema = actual === 'dark' ? 'light' : 'dark';
            try {
                localStorage.setItem(CLAVE, siguiente);
            } catch { /* sin almacenamiento */ }
            return siguiente;
        });
    }, []);

    return { tema, alternar };
}
