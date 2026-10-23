import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowUpRight, CalendarBlank, CheckCircle, ClockCounterClockwise, DownloadSimple, UploadSimple, Waveform } from '@phosphor-icons/react';
import api, { uploadsApi } from '../api';
import type { Farm, UploadResult } from '../api';
import { mensajeDeError } from '../lib/errors';
import { FC_URL } from '../lib/config';
import { numero, porcentaje } from '../lib/format';
import {
    avisar, Button, Card, CardHeader, Chip, ExternalButton, FileDrop, LinkButton, SelectField, Stat, Table, Td, Th, Tr,
} from './ui';

const nombreGranja = (f: Farm) => (f.location ? `${f.name} · ${f.location}` : f.name);

/**
 * Tarjeta de detección de celo. Autocontenida: su estado no se comparte con la de
 * calidad de leche, ni siquiera la granja seleccionada.
 */
export default function EstrusUploadCard({ farms }: { farms: Farm[] }) {
    const [selectedFarm, setSelectedFarm] = useState<number | ''>('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [descargando, setDescargando] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const [errorGranja, setErrorGranja] = useState('');
    const [errorArchivo, setErrorArchivo] = useState('');
    const [errorServidor, setErrorServidor] = useState('');

    const descargarExcel = async (filename: string) => {
        setDescargando(true);
        try {
            const response = await api.get(`/uploads/download/${filename}`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const enlace = document.createElement('a');
            // Sin el prefijo UUID, para un nombre de fichero limpio
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
            const data = await uploadsApi.upload(file, Number(selectedFarm));
            setResult(data);
            setFile(null);
            avisar.ok('Análisis completado', `${numero(data.total_animals)} animales analizados, ${numero(data.celo_count)} en celo.`);
        } catch (err) {
            setErrorServidor(mensajeDeError(err, 'No se pudo analizar el archivo. Comprueba su formato e inténtalo de nuevo.'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card index={1}>
                <CardHeader
                    title="Detección de celo"
                    description="Excel (.xlsx) o CSV con las medidas de resistencia de cada animal."
                    icon={<Waveform size={18} aria-hidden="true" />}
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
                            accept=".xlsx,.xls,.csv"
                            file={file}
                            onFile={f => { setFile(f); setErrorArchivo(''); }}
                        />
                        {errorArchivo && <p role="alert" className="mt-1.5 text-small font-medium text-danger-text">{errorArchivo}</p>}
                    </div>

                    {errorServidor && (
                        <p role="alert" className="rounded-md bg-danger-bg px-3 py-2.5 text-small text-danger-text">{errorServidor}</p>
                    )}

                    <Button type="submit" variant="primary" loading={loading} icon={<UploadSimple size={16} aria-hidden="true" />}>
                        {loading ? 'Procesando…' : 'Subir y detectar'}
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
                        <Stat size="md" value={numero(result.total_animals)} label="Animales" />
                        <Stat size="md" tone="info" value={numero(result.celo_count)} label="En celo" />
                        <Stat size="md" value={numero(result.no_celo_count)} label="No en celo" />
                    </div>

                    <h3 className="mb-2 mt-6 text-micro font-medium uppercase tracking-[0.1em] text-ink-3">Resultado por animal</h3>
                    <div className="overflow-hidden rounded-lg border border-line">
                        <Table caption="Resultado de la detección de celo por animal" maxHeight="18rem" minWidth="0">
                            <thead>
                                <tr>
                                    <Th>Animal</Th>
                                    <Th>Resultado</Th>
                                    <Th align="right">Confianza</Th>
                                </tr>
                            </thead>
                            <tbody>
                                {result.results.map((r, i) => (
                                    <Tr key={`${r.animal_id}-${i}`}>
                                        <Td mono strong>{r.animal_id}</Td>
                                        <Td><Chip tone={r.result === 'Celo' ? 'info' : 'neutral'}>{r.result}</Chip></Td>
                                        <Td numeric muted>{porcentaje(r.confidence)}</Td>
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
                        <LinkButton to="/history" icon={<ClockCounterClockwise size={16} aria-hidden="true" />}>Ver en el historial</LinkButton>
                        <ExternalButton href={FC_URL} variant="ghost" icon={<CalendarBlank size={16} aria-hidden="true" />}>
                            Ver en el calendario <ArrowUpRight size={14} aria-hidden="true" />
                        </ExternalButton>
                    </div>
                </Card>
            )}
        </div>
    );
}
