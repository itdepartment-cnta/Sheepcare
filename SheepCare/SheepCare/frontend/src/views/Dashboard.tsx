import { useEffect, useMemo, useState } from 'react';
import { Barn, UploadSimple, ArrowRight, ClockCounterClockwise, Pulse, CloudArrowUp } from '@phosphor-icons/react';
import { farmsApi, resultsApi, uploadsApi, settingsApi } from '../api';
import type { DetectionResult, Farm, SyncStatus, UploadSummary } from '../api';
import { fecha, fechaLarga, numero, porcentaje } from '../lib/format';
import { Card, CardHeader, Chip, EmptyState, ErrorState, LinkButton, PageHeader, Button, Skeleton } from '../components/ui';

interface Datos {
    granjas: Farm[];
    subidas: UploadSummary[];
    ultima: DetectionResult | null;
    sync: SyncStatus | null;
}

/** Cifra grande con su etiqueta, para los bloques de resumen. */
function Cifra({ valor, etiqueta, destacada = false }: { valor: string; etiqueta: string; destacada?: boolean }) {
    return (
        <div>
            <p className={`font-display text-display tabular ${destacada ? 'text-info-text' : 'text-ink'}`}>{valor}</p>
            <p className="mt-1 text-small text-ink-3">{etiqueta}</p>
        </div>
    );
}

function Cargando() {
    return (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12" role="status" aria-label="Cargando el panel">
            <Skeleton className="h-72 rounded-xl lg:col-span-8 lg:row-span-2" />
            <Skeleton className="h-34 rounded-xl lg:col-span-4" />
            <Skeleton className="h-34 rounded-xl lg:col-span-4" />
            <Skeleton className="h-28 rounded-xl lg:col-span-12" />
        </div>
    );
}

export default function Dashboard() {
    const [datos, setDatos] = useState<Datos | null>(null);
    const [error, setError] = useState(false);
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        let vigente = true;
        Promise.all([
            farmsApi.list(),
            uploadsApi.list(),
            resultsApi.latest(),
            // La sincronización es secundaria: si falla, el panel sigue funcionando.
            settingsApi.syncStatus().catch(() => null),
        ])
            .then(([granjas, subidas, ultima, sync]) => {
                if (vigente) setDatos({ granjas, subidas, ultima, sync });
            })
            .catch(() => {
                if (vigente) setError(true);
            });
        return () => { vigente = false; };
    }, [intento]);

    const reintentar = () => {
        setError(false);
        setDatos(null);
        setIntento(n => n + 1);
    };

    const resumen = useMemo(() => {
        if (!datos) return null;
        const ordenadas = [...datos.subidas].sort((a, b) => b.upload_date.localeCompare(a.upload_date));
        const analizados = datos.subidas.reduce((s, u) => s + u.total_animals, 0);
        const celo = datos.subidas.reduce((s, u) => s + u.celo_count, 0);
        return { ultima: ordenadas[0] ?? null, analizados, celo, subidas: datos.subidas.length };
    }, [datos]);

    const fechaHoy = fechaLarga();
    const cabecera = (
        <PageHeader
            eyebrow={fechaHoy.charAt(0).toUpperCase() + fechaHoy.slice(1)}
            title="Panel"
            description="Resumen de la actividad reciente."
            actions={
                <LinkButton to="/upload" variant="primary" icon={<UploadSimple size={16} aria-hidden="true" />}>
                    Subir datos
                </LinkButton>
            }
        />
    );

    if (error) {
        return (
            <>
                {cabecera}
                <Card>
                    <ErrorState action={<Button onClick={reintentar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                </Card>
            </>
        );
    }

    if (!datos || !resumen) {
        return (
            <>
                {cabecera}
                <Cargando />
            </>
        );
    }

    const { granjas, ultima, sync } = datos;
    const sinDatos = granjas.length === 0 && !resumen.ultima;

    if (sinDatos) {
        return (
            <>
                {cabecera}
                <Card>
                    <EmptyState
                        icon={<Barn aria-hidden="true" />}
                        title="Todavía no hay datos"
                        action={<LinkButton to="/farms" variant="primary">Registrar una granja</LinkButton>}
                    >
                        Registra tu primera granja y sube un archivo para ver aquí la detección de celo.
                    </EmptyState>
                </Card>
            </>
        );
    }

    const u = resumen.ultima;
    const tasa = u && u.total_animals > 0 ? u.celo_count / u.total_animals : 0;

    return (
        <>
            {cabecera}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                {/* Bloque principal: la última subida */}
                <Card className="lg:col-span-8 lg:row-span-2" index={1}>
                    <CardHeader
                        title={u ? u.farm_name : 'Sin subidas todavía'}
                        description={u ? `${u.filename} · ${fecha(u.upload_date)}` : 'Sube un archivo de datos para empezar.'}
                        icon={<Pulse size={18} aria-hidden="true" />}
                        actions={u && <Chip tone="brand">Última subida</Chip>}
                    />
                    {u ? (
                        <>
                            <div className="mt-6 grid grid-cols-3 gap-6">
                                <Cifra valor={numero(u.total_animals)} etiqueta="Animales analizados" />
                                <Cifra valor={numero(u.celo_count)} etiqueta="En celo" destacada />
                                <Cifra valor={numero(u.no_celo_count)} etiqueta="No en celo" />
                            </div>
                            <div className="mt-8">
                                <div className="mb-2 flex items-baseline justify-between text-small">
                                    <span className="text-ink-3">Proporción en celo</span>
                                    <span className="font-medium tabular text-ink">{porcentaje(tasa, 1)}</span>
                                </div>
                                <div
                                    role="img"
                                    aria-label={`${porcentaje(tasa, 1)} de los animales en celo`}
                                    className="h-2.5 overflow-hidden rounded-full bg-line"
                                >
                                    <div className="h-full origin-left rounded-full bg-info" style={{ width: `${Math.max(tasa * 100, tasa > 0 ? 2 : 0)}%` }} />
                                </div>
                            </div>
                            <div className="mt-8 flex flex-wrap gap-2">
                                <LinkButton to="/history" icon={<ClockCounterClockwise size={16} aria-hidden="true" />}>
                                    Ver historial
                                </LinkButton>
                            </div>
                        </>
                    ) : (
                        <EmptyState icon={<UploadSimple aria-hidden="true" />} title="Sin subidas">
                            Cuando subas datos, aquí verás el resultado de la última detección.
                        </EmptyState>
                    )}
                </Card>

                {/* Granjas */}
                <Card className="lg:col-span-4" index={2}>
                    <CardHeader title="Granjas" icon={<Barn size={18} aria-hidden="true" />} />
                    <Cifra valor={numero(granjas.length)} etiqueta={granjas.length === 1 ? 'granja registrada' : 'granjas registradas'} />
                    <LinkButton to="/farms" variant="ghost" size="sm" className="mt-4 -ml-3" icon={<ArrowRight size={14} aria-hidden="true" />}>
                        Gestionar granjas
                    </LinkButton>
                </Card>

                {/* Última detección individual */}
                <Card className="lg:col-span-4" index={3}>
                    <CardHeader title="Última detección" />
                    {ultima ? (
                        <>
                            <div className="flex items-center gap-3">
                                <p className="font-mono text-h3">{ultima.animal_tag}</p>
                                <Chip tone={ultima.result === 'Celo' ? 'info' : 'neutral'}>{ultima.result}</Chip>
                            </div>
                            <p className="mt-2 text-small text-ink-3">
                                Confianza {porcentaje(ultima.confidence, 1)} · {ultima.farm_name}
                            </p>
                        </>
                    ) : (
                        <p className="text-small text-ink-3">Aún no hay detecciones.</p>
                    )}
                </Card>

                {/* Acumulado */}
                <Card className="lg:col-span-8" index={4}>
                    <CardHeader title="Acumulado" description="Todas las subidas de celo de este equipo." />
                    <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
                        <Cifra valor={numero(resumen.subidas)} etiqueta={resumen.subidas === 1 ? 'subida' : 'subidas'} />
                        <Cifra valor={numero(resumen.analizados)} etiqueta="animales analizados" />
                        <Cifra
                            valor={porcentaje(resumen.analizados ? resumen.celo / resumen.analizados : null, 1)}
                            etiqueta="de detecciones en celo"
                            destacada
                        />
                    </div>
                </Card>

                {/* Sincronización con la nube */}
                <Card className="lg:col-span-4" index={5}>
                    <CardHeader title="Última sincronización" icon={<CloudArrowUp size={18} aria-hidden="true" />} />
                    <p className="font-display text-h1 tabular text-ink">{sync?.last_sync ? fecha(sync.last_sync) : 'Nunca'}</p>
                    <p className="mt-1 text-small text-ink-3">con SheepCare Cloud</p>
                    <LinkButton to="/settings" variant="ghost" size="sm" className="mt-4 -ml-3" icon={<ArrowRight size={14} aria-hidden="true" />}>
                        Ajustes de sincronización
                    </LinkButton>
                </Card>
            </div>
        </>
    );
}
