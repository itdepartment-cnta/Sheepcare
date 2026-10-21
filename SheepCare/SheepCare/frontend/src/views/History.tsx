import { useEffect, useState } from 'react';
import { ArrowsClockwise, ClockCounterClockwise } from '@phosphor-icons/react';
import { farmsApi, resultsApi, milkQualityApi, reportsApi } from '../api';
import type { Farm, DetectionResult, MilkQualityResult } from '../api';
import FarmReportCard from '../components/FarmReportCard';
import { fecha, numero, porcentaje } from '../lib/format';
import {
    Button, Card, Chip, EmptyState, ErrorState, PageHeader, SelectField, Table, TableSkeleton, Td, Th, Tr,
} from '../components/ui';

type Kind = 'celo' | 'milk_quality';

// Filas que se pintan de una vez: con miles de resultados, pintarlas todas deja la pantalla bloqueada.
const PAGINA = 200;

interface UnifiedRow {
    key: string;
    kind: Kind;
    animal_tag: string;
    animal_name: string;
    farm_name: string;
    result: string;
    confidence: number | null;
    filename: string;
    created_at: string;
}

const KIND_LABELS: Record<Kind, string> = {
    celo: 'Celo',
    milk_quality: 'Calidad de leche',
};

// El modelo de calidad de leche devuelve "Lower"/"Upper"; se muestran en
// español sin tocar el valor real que guarda/filtra el backend.
const MILK_QUALITY_LABELS: Record<string, string> = { Lower: 'Alta', Upper: 'Media' };

function displayResult(r: UnifiedRow): string {
    return r.kind === 'milk_quality' ? (MILK_QUALITY_LABELS[r.result] ?? r.result) : r.result;
}

function toUnified(r: DetectionResult): UnifiedRow {
    return {
        key: `celo-${r.id}`,
        kind: 'celo',
        animal_tag: r.animal_tag,
        animal_name: r.animal_name,
        farm_name: r.farm_name,
        result: r.result,
        confidence: r.confidence,
        filename: r.filename,
        created_at: r.created_at,
    };
}

function toUnifiedMilkQuality(r: MilkQualityResult): UnifiedRow {
    return {
        key: `milk-${r.id}`,
        kind: 'milk_quality',
        animal_tag: r.animal_tag,
        animal_name: r.animal_name,
        farm_name: r.farm_name,
        result: r.result,
        confidence: null,
        filename: r.filename,
        created_at: r.created_at,
    };
}

const toneOf = (r: UnifiedRow) =>
    r.result === 'Celo' ? 'info' : r.result === 'Upper' ? 'warn' : r.result === 'Lower' ? 'ok' : 'neutral';

export default function HistoryView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [rows, setRows] = useState<UnifiedRow[] | null>(null);
    const [limite, setLimite] = useState(PAGINA);
    const [error, setError] = useState(false);
    const [intento, setIntento] = useState(0);
    const [farmFilter, setFarmFilter] = useState<number | ''>('');
    const [typeFilter, setTypeFilter] = useState<Kind | ''>('');
    const [resultFilter, setResultFilter] = useState('');

    useEffect(() => { farmsApi.list().then(setFarms).catch(() => setFarms([])); }, []);

    useEffect(() => {
        let vigente = true;
        const farmId = farmFilter || undefined;
        Promise.all([
            typeFilter === 'milk_quality'
                ? Promise.resolve([] as DetectionResult[])
                : resultsApi.list({ farm_id: farmId, result: resultFilter || undefined }),
            typeFilter === 'celo'
                ? Promise.resolve([] as MilkQualityResult[])
                : milkQualityApi.results({ farm_id: farmId }),
        ])
            .then(([celoResults, milkResults]) => {
                if (!vigente) return;
                const merged = [
                    ...celoResults.map(toUnified),
                    // El backend local no filtra la leche por resultado: se hace aquí.
                    ...milkResults
                        .filter(r => !resultFilter || r.result === resultFilter)
                        .map(toUnifiedMilkQuality),
                ];
                merged.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
                setRows(merged);
                setLimite(PAGINA);
            })
            .catch(() => { if (vigente) setError(true); });
        return () => { vigente = false; };
    }, [farmFilter, typeFilter, resultFilter, intento]);

    const recargar = () => {
        setError(false);
        setRows(null);
        setIntento(n => n + 1);
    };

    const resultOptions = typeFilter === 'milk_quality'
        ? [{ value: 'Lower', label: 'Alta' }, { value: 'Upper', label: 'Media' }]
        : typeFilter === 'celo'
            ? [{ value: 'Celo', label: 'Celo' }, { value: 'No celo', label: 'No celo' }]
            : [
                { value: 'Celo', label: 'Celo' }, { value: 'No celo', label: 'No celo' },
                { value: 'Lower', label: 'Alta' }, { value: 'Upper', label: 'Media' },
            ];

    const hayFiltros = farmFilter !== '' || typeFilter !== '' || resultFilter !== '';
    const limpiarFiltros = () => { setFarmFilter(''); setTypeFilter(''); setResultFilter(''); };

    return (
        <>
            <PageHeader
                eyebrow="Resultados"
                title="Historial"
                description="Consulta los resultados de detección de celo y de calidad de leche."
                actions={
                    <Button icon={<ArrowsClockwise size={16} aria-hidden="true" />} onClick={recargar}>
                        Actualizar
                    </Button>
                }
            />

            <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <FarmReportCard
                index={0}
                farms={farms}
                id="informe-celo"
                titulo="Informe de celo (PDF)"
                descripcion="Resumen de la detección de celo de una granja: animales en celo, gráfica por subida y detalle."
                descargar={reportsApi.estrusPdf}
            />
            <FarmReportCard
                index={1}
                farms={farms}
                id="informe-leche"
                titulo="Informe de calidad de leche (PDF)"
                descripcion="Resumen de la calidad de leche (SCC) de una granja: muestras con calidad media, gráfica por subida y detalle."
                descargar={reportsApi.milkQualityPdf}
            />
            </div>

            <Card padded={false} index={2}>
                <div className="grid grid-cols-1 gap-4 border-b border-line p-4 sm:grid-cols-3 sm:p-5">
                    <SelectField label="Granja" value={farmFilter} onChange={e => setFarmFilter(Number(e.target.value) || '')}>
                        <option value="">Todas las granjas</option>
                        {farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </SelectField>
                    <SelectField
                        label="Tipo"
                        value={typeFilter}
                        onChange={e => { setTypeFilter(e.target.value as Kind | ''); setResultFilter(''); }}
                    >
                        <option value="">Todos los tipos</option>
                        <option value="celo">Celo</option>
                        <option value="milk_quality">Calidad de leche</option>
                    </SelectField>
                    <SelectField label="Resultado" value={resultFilter} onChange={e => setResultFilter(e.target.value)}>
                        <option value="">Todos los resultados</option>
                        {resultOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </SelectField>
                </div>

                {/* Siempre montado: al filtrar, el lector de pantalla anuncia el nuevo recuento */}
                <p
                    role="status"
                    className={rows && !error ? 'border-b border-line px-5 py-2.5 text-small text-ink-3' : 'sr-only'}
                >
                    {rows && !error
                        ? rows.length === 1
                            ? '1 resultado'
                            : rows.length > limite
                                ? `Mostrando ${numero(limite)} de ${numero(rows.length)} resultados`
                                : `${numero(rows.length)} resultados`
                        : ''}
                </p>

                {error ? (
                    <ErrorState action={<Button onClick={recargar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                ) : rows === null ? (
                    <TableSkeleton rows={6} cols={7} />
                ) : rows.length === 0 ? (
                    <EmptyState
                        icon={<ClockCounterClockwise aria-hidden="true" />}
                        title={hayFiltros ? 'Ningún resultado con estos filtros' : 'Aún no hay resultados'}
                        action={hayFiltros ? <Button onClick={limpiarFiltros}>Quitar filtros</Button> : undefined}
                    >
                        {hayFiltros
                            ? 'Prueba con otra granja, tipo o resultado.'
                            : 'Sube un archivo desde «Subir datos» y sus resultados aparecerán aquí.'}
                    </EmptyState>
                ) : (
                    <>
                    <Table caption="Historial de resultados" minWidth="52rem" maxHeight="36rem">
                        <thead>
                            <tr>
                                <Th>Animal</Th>
                                <Th>Granja</Th>
                                <Th>Tipo</Th>
                                <Th>Resultado</Th>
                                <Th align="right">Confianza</Th>
                                <Th>Archivo</Th>
                                <Th>Fecha</Th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.slice(0, limite).map(r => (
                                <Tr key={r.key}>
                                    <Td>
                                        <span className="font-mono font-medium text-ink">{r.animal_tag}</span>
                                        {r.animal_name && <span className="text-ink-3"> ({r.animal_name})</span>}
                                    </Td>
                                    <Td muted>{r.farm_name || '—'}</Td>
                                    <Td muted>{KIND_LABELS[r.kind]}</Td>
                                    <Td>
                                        {/* El resaltado mira el valor CRUDO, no el traducido */}
                                        <Chip tone={toneOf(r)}>{displayResult(r)}</Chip>
                                    </Td>
                                    <Td numeric muted>{r.confidence == null ? '—' : porcentaje(r.confidence, 1)}</Td>
                                    <Td muted>{r.filename || '—'}</Td>
                                    <Td muted>{fecha(r.created_at)}</Td>
                                </Tr>
                            ))}
                        </tbody>
                    </Table>
                    {rows.length > limite && (
                        <div className="flex justify-center border-t border-line p-4">
                            <Button onClick={() => setLimite(n => n + PAGINA)}>
                                Mostrar {numero(Math.min(PAGINA, rows.length - limite))} más
                            </Button>
                        </div>
                    )}
                    </>
                )}
            </Card>
        </>
    );
}
