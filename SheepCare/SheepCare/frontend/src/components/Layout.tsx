import { Suspense, useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import { Toaster, Skeleton } from './ui';
import { useTema } from '../lib/theme';

/** Marcador mientras se descarga la pantalla de la ruta (el armazón ya está visible). */
function CargandoPantalla() {
    return (
        <div role="status" aria-label="Cargando pantalla" className="space-y-6">
            <div className="space-y-3">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-8 w-64" />
            </div>
            <Skeleton className="h-64 w-full rounded-xl" />
        </div>
    );
}

/**
 * Armazón común de las pantallas autenticadas. Es una ruta de diseño: se monta
 * una vez y solo cambia el <Outlet />, de modo que la barra lateral y los avisos
 * no se recrean al navegar.
 */
export default function Layout() {
    const { tema, alternar } = useTema();
    const principal = useRef<HTMLElement>(null);
    const { pathname } = useLocation();

    // Al cambiar de pantalla, vuelve arriba (el desplazamiento es del <main>, no de la ventana)
    useEffect(() => {
        principal.current?.scrollTo({ top: 0 });
    }, [pathname]);

    return (
        <div className="flex h-dvh bg-canvas">
            <a href="#contenido" className="skip-link">Saltar al contenido</a>
            <Sidebar tema={tema} onAlternarTema={alternar} />
            <main id="contenido" ref={principal} tabIndex={-1} className="min-w-0 flex-1 overflow-auto outline-none">
                <div className="mx-auto w-full max-w-[1280px] px-5 py-6 pb-16 lg:px-8">
                    <Suspense fallback={<CargandoPantalla />}>
                        <Outlet />
                    </Suspense>
                </div>
            </main>
            <Toaster tema={tema} />
        </div>
    );
}
