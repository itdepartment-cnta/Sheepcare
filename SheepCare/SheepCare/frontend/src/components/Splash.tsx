/** Pantalla de espera mientras se comprueba la sesión o se carga una ruta. */
export default function Splash() {
    return (
        <div role="status" aria-live="polite" className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-canvas">
            <img src="/sheepcare.svg" alt="" width={48} height={48} className="size-12 animate-pulse" />
            <p className="text-small text-ink-3">Cargando…</p>
        </div>
    );
}
