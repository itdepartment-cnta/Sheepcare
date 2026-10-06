import { useEffect, useState } from 'react';
import { Barn } from '@phosphor-icons/react';
import { farmsApi } from '../api';
import type { Farm } from '../api';
import EstrusUploadCard from '../components/EstrusUploadCard';
import MilkQualityUploadCard from '../components/MilkQualityUploadCard';
import { Card, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton, Button } from '../components/ui';

/**
 * Dos tarjetas independientes, una por tipo de análisis. El estado vacío de
 * «no hay granjas» es común a las dos: sin granja no se puede subir nada.
 */
export default function UploadView() {
    const [farms, setFarms] = useState<Farm[] | null>(null);
    const [error, setError] = useState(false);
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        let vigente = true;
        farmsApi.list()
            .then(f => { if (vigente) setFarms(f); })
            .catch(() => { if (vigente) setError(true); });
        return () => { vigente = false; };
    }, [intento]);

    const cabecera = (
        <PageHeader
            eyebrow="Análisis"
            title="Subir datos"
            description="Detección de celo y calidad de leche a partir de tus archivos."
        />
    );

    if (error) {
        return (
            <>
                {cabecera}
                <Card>
                    <ErrorState action={<Button onClick={() => { setError(false); setIntento(n => n + 1); }}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                </Card>
            </>
        );
    }

    if (farms === null) {
        return (
            <>
                {cabecera}
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" role="status" aria-label="Cargando">
                    <Skeleton className="h-96 rounded-xl" />
                    <Skeleton className="h-96 rounded-xl" />
                </div>
            </>
        );
    }

    if (farms.length === 0) {
        return (
            <>
                {cabecera}
                <Card>
                    <EmptyState
                        icon={<Barn aria-hidden="true" />}
                        title="Primero, una granja"
                        action={<LinkButton to="/farms" variant="primary">Registrar una granja</LinkButton>}
                    >
                        Cada análisis se guarda dentro de una granja, así que necesitas registrar una antes de subir datos.
                    </EmptyState>
                </Card>
            </>
        );
    }

    return (
        <>
            {cabecera}
            <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
                <EstrusUploadCard farms={farms} />
                <MilkQualityUploadCard farms={farms} />
            </div>
        </>
    );
}
