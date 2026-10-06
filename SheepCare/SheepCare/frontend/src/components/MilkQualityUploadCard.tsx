import { useState } from 'react';
import type { FormEvent } from 'react';
import { CheckCircle, ClockCounterClockwise, DownloadSimple, Flask, UploadSimple } from '@phosphor-icons/react';
import api, { milkQualityApi } from '../api';
import type { Farm, MilkQualityUploadResult } from '../api';
import { mensajeDeError } from '../lib/errors';
import { numero } from '../lib/format';
import {
    avisar, Button, Card, CardHeader, Chip, FileDrop, LinkButton, SelectField, Stat, Table, Td, Th, Tr,
} from './ui';

// El modelo devuelve «Lower»/«Upper»; se muestran en español sin tocar el valor real.
const MILK_QUALITY_LABELS: Record<string, string> = { Lower: 'Buena', Upper: 'Mala' };

const nombreGranja = (f: Farm) => (f.location ? `${f.name} · ${f.location}` : f.name);

/**
 * Tarjeta de calidad de leche (SCC).
 *
 * Autocontenida: lleva su propio estado y no comparte nada con la de celo, ni
 * siquiera la granja seleccionada.
 *
 * Diferencias deliberadas respecto a la tarjeta de celo, por paridad con la
 * versión Edge:
 *   - No admite .csv: el espectro viene siempre en Excel.
 *   - La tabla no tiene columna de confianza: el modelo usa predict() y no
 *     expone probabilidad.
 *   - No hay enlace a Calendario.
 */
export default function MilkQualityUploadCard({ farms }: { farms: Farm[] }) {
    const [selectedFarm, setSelectedFarm] = useState<number | ''>('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [descargando, setDescargando] = useState(false);
    const [result, setResult] = useState<MilkQualityUploadResult | null>(null);
    const [errorGranja, setErrorGranja] = useState('');
    const [errorArchivo, setErrorArchivo] = useState('');
    const [errorServidor, setErrorServidor] = useState('');

    const descargarExcel = async (filename: string) => {
        setDescargando(true);
        try {
            const response = await api.get(`/milk-quality/uploads/download/${filename}`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const enlace = document.createElement('a');
            enlace.href = url;
            enlace.setAttribute('download', filename.replace(/^[a-f0-9]{32}_resultado_/, 'resultado_'));
            document.body.appendChild(enlace);
            enlace.click();
            enlace.remove();
            window.URL.revokeObjectURL(url);
        } catch {
            avisar.error('No se pudo descargar el archivo', 'Inténtalo de nuevo en unos segundos.');
        } finally {
            setDescargando(false);
        }
    };

    const enviar = async (e: FormEvent) => {
        e.preventDefault();
        setErrorGranja(selectedFarm ? '' : 'Elige una granja.');
        setErrorArchivo(file ? '' : 'Elige un archivo.');
        setErrorServidor('');
        if (!selectedFarm || !file) return;

        setLoading(true);
        setResult(null);
        try {
            const data = await milkQualityApi.upload(file, Number(selectedFarm));
            setResult(data);
            setFile(null);
            avisar.ok('Análisis completado', `${numero(data.total_samples)} muestras analizadas, ${numero(data.upper_count)} de calidad mala.`);
        } catch (err) {
            setErrorServidor(mensajeDeError(err, 'No se pudo analizar el archivo. Comprueba su formato e inténtalo de nuevo.'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card index={2}>
                <CardHeader
                    title="Calidad de leche"
                    description="Excel (.xlsx) con el espectro de cada muestra, en columnas de longitud de onda."
                    icon={<Flask size={18} aria-hidden="true" />}
                />
                <form onSubmit={enviar} noValidate className="space-y-5">
                    <SelectField
                        label="Granja"
                        required
                        value={selectedFarm}
                        error={errorGranja}
                        onChange={e => { setSelectedFarm(Number(e.target.value) || ''); setErrorGranja(''); }}
                    >
                        <option value="">Elige una granja…</option>
                        {farms.map(f => <option key={f.id} value={f.id}>{nombreGranja(f)}</option>)}
                    </SelectField>

                    <div>
                        <FileDrop
                            label="Archivo"
                            required
                            accept=".xlsx,.xls"
                            file={file}
                            onFile={f => { setFile(f); setErrorArchivo(''); }}
                            hint="Columna A: identificador de la muestra. El resto: longitudes de onda, con el esquema fijo."
                        />
                        {errorArchivo && <p role="alert" className="mt-1.5 text-small font-medium text-danger-text">{errorArchivo}</p>}
                    </div>

                    {errorServidor && (
                        <p role="alert" className="rounded-md bg-danger-bg px-3 py-2.5 text-small text-danger-text">{errorServidor}</p>
                    )}

                    <Button type="submit" variant="primary" loading={loading} icon={<UploadSimple size={16} aria-hidden="true" />}>
                        {loading ? 'Procesando…' : 'Subir y predecir'}
                    </Button>
                </form>
            </Card>

            {result && (
                <Card index={0}>
                    <CardHeader
                        title="Análisis completado"
                        description={Number.isFinite(result.processing_time_ms) ? `Resultados obtenidos en ${numero(result.processing_time_ms)} ms.` : undefined}
                        icon={<CheckCircle size={18} weight="fill" aria-hidden="true" />}
                    />
                    <div className="grid grid-cols-3 gap-4">
                        <Stat size="md" value={numero(result.total_samples)} label="Muestras" />
                        <Stat size="md" value={numero(result.lower_count)} label="Calidad buena" />
                        <Stat size="md" tone="danger" value={numero(result.upper_count)} label="Calidad mala" />
                    </div>

                    <h3 className="mb-2 mt-6 text-micro font-medium uppercase tracking-[0.1em] text-ink-3">Resultado por muestra</h3>
                    <div className="overflow-hidden rounded-lg border border-line">
                        <Table caption="Resultado de la calidad de leche por muestra" maxHeight="18rem" minWidth="0">
                            <thead>
                                <tr>
                                    <Th>Muestra</Th>
                                    <Th>Resultado</Th>
                                </tr>
                            </thead>
                            <tbody>
                                {result.results.map((r, i) => (
                                    <Tr key={`${r.animal_id}-${i}`}>
                                        <Td mono strong>{r.animal_id}</Td>
                                        <Td>
                                            <Chip tone={r.result === 'Upper' ? 'danger' : 'ok'}>
                                                {MILK_QUALITY_LABELS[r.result] ?? r.result}
                                            </Chip>
                                        </Td>
                                    </Tr>
                                ))}
                            </tbody>
                        </Table>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-2">
                        {result.result_file && (
                            <Button
                                variant="primary"
                                loading={descargando}
                                icon={<DownloadSimple size={16} aria-hidden="true" />}
                                onClick={() => descargarExcel(result.result_file)}
                            >
                                Descargar Excel con el resultado
                            </Button>
                        )}
                        <LinkButton to="/history" icon={<ClockCounterClockwise size={16} aria-hidden="true" />}>
                            Ver en el historial
                        </LinkButton>
                    </div>
                </Card>
            )}
        </div>
    );
}
