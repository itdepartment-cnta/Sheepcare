import { useEffect, useState } from 'react';
import { ArrowSquareOut, ArrowsClockwise, CalendarBlank } from '@phosphor-icons/react';
import { uploadsApi } from '../api';
import type { UploadSummary } from '../api';
import { fecha, numero } from '../lib/format';
import { Button, Card, CardHeader, Chip, EmptyState, ErrorState, ExternalButton, PageHeader, LinkButton, Skeleton } from '../components/ui';

const FARMCALENDAR_WEB_URL = 'http://localhost:8002/';

export default function CalendarView() {
    const [uploads, setUploads] = useState<UploadSummary[] | null>(null);
    const [error, setError] = useState(false);
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        let vigente = true;
        uploadsApi.list()
            .then(u => { if (vigente) setUploads(u); })
            .catch(() => { if (vigente) setError(true); });
        return () => { vigente = false; };
    }, [intento]);

    const recargar = () => {
        setError(false);
        setUploads(null);
        setIntento(n => n + 1);
    };

    return (
        <>
            <PageHeader
                eyebrow="Seguimiento"
                title="Detecciones registradas"
                description="Cada carga se registra como Observation en el Farm Calendar."
                actions={
                    <>
                        <Button icon={<ArrowsClockwise size={16} aria-hidden="true" />} onClick={recargar}>Actualizar</Button>
                        <ExternalButton
                            href={FARMCALENDAR_WEB_URL}
                            variant="primary"
                            icon={<ArrowSquareOut size={16} aria-hidden="true" />}
                        >
                            Abrir Farm Calendar
                        </ExternalButton>
                    </>
                }
            />

            <Card padded={false} index={0}>
                {error ? (
                    <ErrorState action={<Button onClick={recargar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                ) : uploads === null ? (
                    <div className="space-y-3 p-5" role="status" aria-label="Cargando">
                        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
                    </div>
                ) : uploads.length === 0 ? (
                    <EmptyState
                        icon={<CalendarBlank aria-hidden="true" />}
                        title="Aún no hay detecciones registradas"
                        action={<LinkButton to="/upload" variant="primary">Subir datos</LinkButton>}
                    >
                        Sube un archivo desde «Subir datos» para crear la primera.
                    </EmptyState>
                ) : (
                    <>
                        <div className="px-5 pt-5">
                            <CardHeader title="Últimas detecciones" icon={<CalendarBlank size={18} aria-hidden="true" />} />
                        </div>
                        <ul className="divide-y divide-line border-t border-line">
                            {uploads.slice(0, 20).map(u => (
                                <li key={u.id} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-3 transition-colors duration-200 ease-snap hover:bg-canvas-soft">
                                    <div className="min-w-0">
                                        <p className="truncate text-body font-medium text-ink">{u.farm_name}</p>
                                        <p className="truncate text-small text-ink-3">{u.filename} · {fecha(u.upload_date)}</p>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2 text-small text-ink-2">
                                        <span className="tabular">{numero(u.total_animals)} animales</span>
                                        {u.celo_count > 0 && <Chip tone="info">{numero(u.celo_count)} en celo</Chip>}
                                        <Chip>{numero(u.no_celo_count)} no celo</Chip>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </>
                )}
            </Card>
        </>
    );
}
