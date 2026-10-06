import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CloudRain, Info, MapPin, Thermometer } from '@phosphor-icons/react';
import { farmsApi, weatherApi } from '../api';
import type { Farm, NivelTHI, PuntoPrevision, Prevision, THIActual } from '../api';
import { estadoHttp, mensajeDeError as detalleDeError } from '../lib/errors';
import { numero } from '../lib/format';
import { Card, Chip, EmptyState, ErrorState, PageHeader, SelectField, Skeleton } from '../components/ui';

type Tono = 'ok' | 'warn' | 'danger';

// El color refuerza, no sustituye: cada nivel lleva su etiqueta de texto.
const NIVELES: Record<NivelTHI, { etiqueta: string; tono: Tono; fondo: string; consejo: string }> = {
    sin_estres: { etiqueta: 'Sin estrés', tono: 'ok', fondo: 'bg-ok-bg', consejo: 'Sin estrés térmico.' },
    leve: { etiqueta: 'Estrés leve', tono: 'warn', fondo: 'bg-warn-bg', consejo: 'Conviene asegurar sombra y agua fresca.' },
    moderado: {
        etiqueta: 'Estrés moderado', tono: 'warn', fondo: 'bg-warn-bg',
        consejo: 'Refuerza sombra, ventilación y agua, y evita manejar a los animales en las horas de más calor.',
    },
    severo: {
        etiqueta: 'Estrés severo', tono: 'danger', fondo: 'bg-danger-bg',
        consejo: 'Prioriza refrescar al rebaño: sombra, ventilación, agua abundante, y evita moverlo.',
    },
    critico: {
        etiqueta: 'Estrés crítico', tono: 'danger', fondo: 'bg-danger-bg',
        consejo: 'Riesgo para la salud de los animales: actúa de inmediato.',
    },
};

interface Dia {
    clave: string;
    fecha: Date;
    thiMax: number | null;
    nivel: NivelTHI | null;
    tMin: number | null;
    tMax: number | null;
    lluviaMax: number | null;
}

// Agrupa los puntos de 3 h por día en la hora local del navegador. El primer
// y el último día son parciales: la previsión empieza «ahora» y dura 5 días.
function agruparPorDia(puntos: PuntoPrevision[]): Dia[] {
    const dias = new Map<string, Dia>();
    for (const p of puntos) {
        const fecha = new Date(p.timestamp);
        const clave = fecha.toLocaleDateString('sv-SE'); // AAAA-MM-DD en hora local
        let d = dias.get(clave);
        if (!d) {
            d = { clave, fecha, thiMax: null, nivel: null, tMin: null, tMax: null, lluviaMax: null };
            dias.set(clave, d);
        }
        if (p.thi != null && (d.thiMax == null || p.thi > d.thiMax)) {
            d.thiMax = p.thi;
            d.nivel = p.level;
        }
        if (p.temperature != null) {
            d.tMin = d.tMin == null ? p.temperature : Math.min(d.tMin, p.temperature);
            d.tMax = d.tMax == null ? p.temperature : Math.max(d.tMax, p.temperature);
        }
        if (p.rain_probability != null) {
            d.lluviaMax = d.lluviaMax == null ? p.rain_probability : Math.max(d.lluviaMax, p.rain_probability);
        }
    }
    return [...dias.values()].sort((a, b) => a.clave.localeCompare(b.clave));
}

type Accion = 'granjas' | 'ajustes' | null;

// En la versión local un 409 puede ser «sin coordenadas» o «sin clave de
// OpenWeatherMap»; el backend lo dice en el detalle.
function mensajeDeError(e: unknown): { texto: string; accion: Accion } {
    const estado = estadoHttp(e);
    if (estado === 409) {
        return /clave/i.test(detalleDeError(e, ''))
            ? { texto: 'Falta tu clave de OpenWeatherMap.', accion: 'ajustes' }
            : { texto: 'Esta granja no tiene coordenadas.', accion: 'granjas' };
    }
    if (estado === 404) {
        return { texto: 'No se encontró la granja.', accion: null };
    }
    if (estado === 502) {
        return { texto: 'No se pudo obtener el tiempo. Si el problema continúa, comprueba tu clave de OpenWeatherMap en Ajustes.', accion: 'ajustes' };
    }
    if (estado === 503) {
        return { texto: 'El servicio meteorológico no está disponible ahora mismo. Inténtalo de nuevo en unos minutos.', accion: null };
    }
    return { texto: 'No se pudo obtener el tiempo. Inténtalo de nuevo.', accion: null };
}

export default function WeatherView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [farmId, setFarmId] = useState<number | null>(null);
    const [loadingFarms, setLoadingFarms] = useState(true);
    const [thi, setThi] = useState<THIActual | null>(null);
    const [prevision, setPrevision] = useState<Prevision | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<{ texto: string; accion: Accion } | null>(null);

    // Elegir granja deja la vista en «cargando» y vacía lo anterior. Se hace aquí,
    // no dentro del efecto, para no disparar renders en cascada.
    const seleccionar = (id: number) => {
        setFarmId(id);
        setLoading(true);
        setError(null);
        setThi(null);
        setPrevision(null);
    };

    useEffect(() => {
        farmsApi.list()
            .then(lista => {
                setFarms(lista);
                // Por defecto, la primera granja que tenga coordenadas.
                const primera = lista.find(f => f.latitude != null && f.longitude != null) ?? lista[0];
                if (primera) seleccionar(primera.id);
            })
            .catch(() => setFarms([]))
            .finally(() => setLoadingFarms(false));
    }, []);

    useEffect(() => {
        if (farmId == null) return;
        // Si el usuario cambia de granja mientras carga, se descarta la respuesta vieja.
        let vigente = true;
        Promise.all([weatherApi.thi(farmId), weatherApi.forecast(farmId)])
            .then(([t, p]) => {
                if (!vigente) return;
                setThi(t);
                setPrevision(p);
            })
            .catch(e => {
                if (vigente) setError(mensajeDeError(e));
            })
            .finally(() => {
                if (vigente) setLoading(false);
            });
        return () => { vigente = false; };
    }, [farmId]);

    const dias = useMemo(() => (prevision ? agruparPorDia(prevision.forecast) : []), [prevision]);
    const hoy = new Date().toLocaleDateString('sv-SE');
    const farm = farms.find(f => f.id === farmId);

    return (
        <>
            <PageHeader
                eyebrow="Clima"
                title="Tiempo y estrés térmico"
                description="Índice de temperatura y humedad (THI) de cada granja, actual y previsto a 5 días."
            />

            {loadingFarms ? (
                <div className="space-y-4" aria-busy="true">
                    <Skeleton className="h-10 w-72" />
                    <Skeleton className="h-40 w-full" />
                </div>
            ) : farms.length === 0 ? (
                <Card index={0}>
                    <EmptyState
                        icon={<MapPin aria-hidden="true" />}
                        title="Aún no hay granjas"
                        action={<Link to="/farms" className="font-medium text-ink underline underline-offset-2 hover:text-brand-700">Ir a Granjas</Link>}
                    >
                        Crea una granja y añade sus coordenadas para consultar su tiempo.
                    </EmptyState>
                </Card>
            ) : (
                <>
                    <div className="mb-5 flex flex-wrap items-end gap-x-4 gap-y-2">
                        <SelectField
                            id="granja"
                            label="Granja"
                            className="w-full sm:w-80"
                            value={farmId ?? ''}
                            onChange={e => seleccionar(Number(e.target.value))}
                        >
                            {farms.map(f => (
                                <option key={f.id} value={f.id}>
                                    {f.name}{f.latitude == null ? ' (sin coordenadas)' : ''}
                                </option>
                            ))}
                        </SelectField>
                        {farm && farm.latitude != null && farm.longitude != null && (
                            <span className="inline-flex items-center gap-1.5 pb-2 text-small tabular text-ink-3">
                                <MapPin size={14} aria-hidden="true" className="text-brand-700" />
                                {numero(farm.latitude, 4)}, {numero(farm.longitude, 4)}
                            </span>
                        )}
                    </div>

                    {loading && (
                        <div className="space-y-4" role="status" aria-busy="true">
                            <span className="sr-only">Consultando el tiempo…</span>
                            <Skeleton className="h-40 w-full" />
                            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
                            </div>
                        </div>
                    )}

                    {error && (
                        <Card index={0}>
                            <ErrorState
                                title={error.texto}
                                action={error.accion ? (
                                    <Link
                                        to={error.accion === 'ajustes' ? '/settings' : '/farms'}
                                        className="font-medium text-ink underline underline-offset-2 hover:text-brand-700"
                                    >
                                        {error.accion === 'ajustes' ? 'Ir a Ajustes' : 'Añadir coordenadas en Granjas'}
                                    </Link>
                                ) : undefined}
                            />
                        </Card>
                    )}

                    {thi && (
                        <div className="bezel mb-5 reveal" style={{ '--i': 0 } as React.CSSProperties}>
                            <div className={`bezel-core p-5 sm:p-6 ${NIVELES[thi.level].fondo}`}>
                                <p className="text-micro font-medium uppercase tracking-[0.1em] text-ink-2">THI actual</p>
                                <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
                                    <span className="font-display tabular text-display text-ink">{numero(thi.thi, 1)}</span>
                                    <Chip tone={NIVELES[thi.level].tono}>{NIVELES[thi.level].etiqueta}</Chip>
                                </div>
                                <p className="mt-3 max-w-prose text-body text-ink-2">{NIVELES[thi.level].consejo}</p>
                            </div>
                        </div>
                    )}

                    {dias.length > 0 && (
                        <section aria-labelledby="proximos-dias">
                            <h2 id="proximos-dias" className="mb-3 font-display text-h2 text-ink">Próximos días</h2>
                            <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                                {dias.map((d, i) => {
                                    const nivel = d.nivel ?? 'sin_estres';
                                    const etiquetaDia = d.clave === hoy
                                        ? 'Hoy'
                                        : d.fecha.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric' });
                                    return (
                                        <li key={d.clave} className="reveal" style={{ '--i': i + 1 } as React.CSSProperties}>
                                            <div className="bezel h-full">
                                                <div className="bezel-core h-full p-4">
                                                    <p className="text-small font-medium capitalize text-ink">{etiquetaDia}</p>
                                                    <p className="mt-2 text-micro text-ink-3">THI máx.</p>
                                                    <p className="font-display tabular text-h1 text-ink">
                                                        {d.thiMax != null ? numero(d.thiMax, 1) : '—'}
                                                    </p>
                                                    <Chip tone={NIVELES[nivel].tono} className="mt-1">{NIVELES[nivel].etiqueta}</Chip>
                                                    <dl className="mt-3 space-y-1 text-small text-ink-2">
                                                        <div className="flex items-center gap-1.5">
                                                            <dt className="sr-only">Temperatura mínima y máxima</dt>
                                                            <Thermometer size={14} aria-hidden="true" className="text-ink-3" />
                                                            <dd className="tabular">
                                                                {d.tMin != null && d.tMax != null
                                                                    ? `${Math.round(d.tMin)}° / ${Math.round(d.tMax)}°`
                                                                    : '—'}
                                                            </dd>
                                                        </div>
                                                        <div className="flex items-center gap-1.5">
                                                            <dt className="sr-only">Probabilidad de lluvia</dt>
                                                            <CloudRain size={14} aria-hidden="true" className="text-ink-3" />
                                                            <dd className="tabular">
                                                                {d.lluviaMax != null ? `${Math.round(d.lluviaMax * 100)} %` : '—'}
                                                            </dd>
                                                        </div>
                                                    </dl>
                                                </div>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ul>
                            <p className="mt-4 flex max-w-prose items-start gap-2 text-small text-ink-3">
                                <Info size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                                El primer y el último día son parciales. Umbrales generales de ganado (72 / 79 / 84 / 89), no calibrados específicamente para ovino.
                            </p>
                        </section>
                    )}
                </>
            )}
        </>
    );
}
