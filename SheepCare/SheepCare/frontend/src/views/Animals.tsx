import { useEffect, useMemo, useState } from 'react';
import { PawPrint, ArrowsClockwise } from '@phosphor-icons/react';
import { farmsApi, animalsApi } from '../api';
import type { Farm, Animal } from '../api';
import { fecha, numero } from '../lib/format';
import {
    Button, Card, EmptyState, ErrorState, PageHeader, SelectField, Table, TableSkeleton, Td, Th, Tr,
} from '../components/ui';

// El backend local puede devolver el nombre de la granja junto al animal.
type AnimalConGranja = Animal & { farm_name?: string };

export default function AnimalsView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [animals, setAnimals] = useState<AnimalConGranja[] | null>(null);
    const [farmFilter, setFarmFilter] = useState<number | ''>('');
    const [error, setError] = useState(false);
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        farmsApi.list().then(setFarms).catch(() => setFarms([]));
    }, []);

    useEffect(() => {
        let vigente = true;
        animalsApi.list(farmFilter || undefined)
            .then(a => { if (vigente) setAnimals(a); })
            .catch(() => { if (vigente) setError(true); });
        return () => { vigente = false; };
    }, [farmFilter, intento]);

    const nombreGranja = useMemo(() => new Map(farms.map(f => [f.id, f.name])), [farms]);

    const recargar = () => {
        setError(false);
        setAnimals(null);
        setIntento(n => n + 1);
    };

    const cambiarGranja = (valor: string) => {
        setAnimals(null);
        setError(false);
        setFarmFilter(Number(valor) || '');
    };

    return (
        <>
            <PageHeader
                eyebrow="Gestión"
                title="Animales"
                description="Se registran solos al subir los archivos de datos."
                actions={
                    <Button icon={<ArrowsClockwise size={16} aria-hidden="true" />} onClick={recargar}>
                        Actualizar
                    </Button>
                }
            />

            <div className="mb-4 max-w-xs reveal" style={{ '--i': 1 } as React.CSSProperties}>
                <SelectField label="Granja" value={farmFilter} onChange={e => cambiarGranja(e.target.value)}>
                    <option value="">Todas las granjas</option>
                    {farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                </SelectField>
            </div>

            <Card padded={false} index={2}>
                {error ? (
                    <ErrorState action={<Button onClick={recargar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                ) : animals === null ? (
                    <TableSkeleton rows={6} cols={5} />
                ) : animals.length === 0 ? (
                    <EmptyState icon={<PawPrint aria-hidden="true" />} title="Aún no hay animales">
                        Se crean automáticamente al subir un archivo de datos.
                    </EmptyState>
                ) : (
                    <Table caption="Animales registrados">
                        <thead>
                            <tr>
                                <Th align="right">N.º</Th>
                                <Th>Crotal</Th>
                                <Th>Nombre</Th>
                                <Th>Granja</Th>
                                <Th>Registrado</Th>
                            </tr>
                        </thead>
                        <tbody>
                            {animals.map(a => (
                                <Tr key={a.id}>
                                    <Td numeric muted>{numero(a.id)}</Td>
                                    <Td mono strong>{a.external_tag}</Td>
                                    <Td muted={!a.name}>{a.name || '—'}</Td>
                                    <Td muted>{a.farm_name || nombreGranja.get(a.farm_id) || '—'}</Td>
                                    <Td muted>{fecha(a.created_at)}</Td>
                                </Tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Card>
        </>
    );
}
