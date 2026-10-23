import { useState } from 'react';
import { DownloadSimple, FileText } from '@phosphor-icons/react';
import type { Farm, InformePdf } from '../api';
import { estadoHttp } from '../lib/errors';
import { avisar, Button, Card, CardHeader, SelectField, TextField } from './ui';

interface Props {
    farms: Farm[];
    /** Id corto y unico por tarjeta: enlaza las etiquetas con sus campos. */
    id: string;
    titulo: string;
    descargar: (farmId: number, desde?: string, hasta?: string) => Promise<InformePdf>;
    index?: number;
}

const mensajeDeError = (e: unknown): string => {
    const estado = estadoHttp(e);
    if (estado === 404) return 'No se encontró la granja.';
    if (estado === 422) return 'Las fechas no son válidas.';
    if (estado === 503 || estado === 504) {
        return 'El servicio de informes no está disponible ahora mismo. Inténtalo de nuevo en unos minutos.';
    }
    return 'No se pudo generar el informe. Inténtalo de nuevo.';
};

/**
 * Descarga de un informe en PDF de una granja (celo, calidad de leche...).
 *
 * Autocontenida: lleva su propio estado y no comparte la granja con los
 * filtros de la tabla ni con otras tarjetas. Las fechas son opcionales; sin
 * ellas el informe incluye todos los datos de la granja.
 */
export default function FarmReportCard({ farms, id, titulo, descargar, index }: Props) {
    const [farmId, setFarmId] = useState<number | ''>('');
    const [desde, setDesde] = useState('');
    const [hasta, setHasta] = useState('');
    const [loading, setLoading] = useState(false);
    const [errorGranja, setErrorGranja] = useState('');
    const [errorFechas, setErrorFechas] = useState('');
    const [errorServidor, setErrorServidor] = useState('');

    const handleDownload = async () => {
        setErrorServidor('');
        setErrorGranja(farmId ? '' : 'Selecciona una granja.');
        const fechasMal = !!desde && !!hasta && hasta < desde;
        setErrorFechas(fechasMal ? 'La fecha final no puede ser anterior a la inicial.' : '');
        if (!farmId || fechasMal) return;

        setLoading(true);
        try {
            const { blob, filename } = await descargar(Number(farmId), desde, hasta);
            // Descarga sin salir de la página: enlace temporal sobre el blob.
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            avisar.ok('Informe generado', filename);
        } catch (e) {
            setErrorServidor(mensajeDeError(e));
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card className="h-full" index={index}>
            <CardHeader
                title={titulo}
                description="Sin fechas, incluye todos los datos."
                icon={<FileText size={18} aria-hidden="true" />}
            />
            <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                <SelectField
                    id={`${id}-granja`}
                    label="Granja"
                    value={farmId}
                    error={errorGranja}
                    onChange={e => { setFarmId(Number(e.target.value) || ''); setErrorGranja(''); }}
                >
                    <option value="">Selecciona una granja</option>
                    {farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                </SelectField>
                </div>
                <TextField
                    id={`${id}-desde`}
                    label="Desde"
                    type="date"
                    value={desde}
                    invalid={!!errorFechas}
                    onChange={e => { setDesde(e.target.value); setErrorFechas(''); }}
                />
                <TextField
                    id={`${id}-hasta`}
                    label="Hasta"
                    type="date"
                    value={hasta}
                    error={errorFechas}
                    onChange={e => { setHasta(e.target.value); setErrorFechas(''); }}
                />
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                    <Button
                        variant="secondary"
                        loading={loading}
                        icon={<DownloadSimple size={16} aria-hidden="true" />}
                        onClick={handleDownload}
                    >
                        {loading ? 'Generando…' : 'Descargar informe'}
                    </Button>
                </div>
            </div>
            {errorServidor && (
                <p role="alert" className="mt-4 rounded-md bg-danger-bg px-3 py-2.5 text-small text-danger-text">{errorServidor}</p>
            )}
        </Card>
    );
}
