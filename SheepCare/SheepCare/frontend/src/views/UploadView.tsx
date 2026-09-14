import { useEffect, useState, useRef } from 'react';
import { Upload, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { farmsApi, uploadsApi, milkQualityApi } from '../api';
import type { Farm, UploadResult, MilkQualityUploadResult } from '../api';

function EstrusUploadCard({ farms }: { farms: Farm[] }) {
    const [selectedFarm, setSelectedFarm] = useState<number | ''>('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const [error, setError] = useState('');
    const fileRef = useRef<HTMLInputElement>(null);

    const handleSubmit = async () => {
        if (!selectedFarm) { setError('Selecciona una granja'); return; }
        if (!file) { setError('Selecciona un archivo'); return; }

        setLoading(true);
        setError('');
        setResult(null);
        try {
            const data = await uploadsApi.upload(file, Number(selectedFarm));
            setResult(data);
            setFile(null);
            if (fileRef.current) fileRef.current.value = '';
        } catch (e: any) {
            const detail = e.response?.data?.detail;
            if (Array.isArray(detail)) {
                setError(detail.map((d: any) => d.msg).join('; '));
            } else if (typeof detail === 'string') {
                setError(detail);
            } else {
                setError(e.message || 'Error al subir');
            }
        } finally {
            setLoading(false);
        }
    };

    const formatProcessingTime = (ms: number | null | undefined) => {
        if (ms == null || isNaN(ms)) return null;
        return `Resultados obtenidos en ${Math.round(ms)} ms`;
    };

    return (
        <div>
            <h2 className="text-lg font-bold text-grafito mb-1">🐑 Detección de Celo</h2>
            <p className="text-gray-500 text-sm mb-4">Sube archivos Excel (.xlsx) o CSV con datos de resistencia de animales.</p>

            <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Granja *</label>
                    <select
                        value={selectedFarm}
                        onChange={e => setSelectedFarm(Number(e.target.value) || '')}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                    >
                        <option value="">Selecciona una granja...</option>
                        {farms.map(f => (
                            <option key={f.id} value={f.id}>{f.name} ({f.location || 'no location'})</option>
                        ))}
                    </select>
                </div>

                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Archivo *</label>
                    <input
                        ref={fileRef}
                        type="file"
                        accept=".xlsx,.xls,.csv"
                        onChange={e => setFile(e.target.files?.[0] || null)}
                        className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-cian/10 file:text-cian file:text-sm file:font-medium hover:file:bg-cian/20"
                    />
                    <p className="text-xs text-gray-400 mt-1">Formato: Col A = ID Animal, Col C+ = Fechas con valores de resistencia</p>
                </div>

                {error && (
                    <div className="flex items-center gap-2 text-coral text-sm mb-4 p-3 bg-coral/5 rounded-lg">
                        <AlertCircle size={14} /> {error}
                    </div>
                )}

                <button
                    onClick={handleSubmit}
                    disabled={loading || !selectedFarm || !file}
                    className="flex items-center gap-2 bg-acido text-white px-6 py-2.5 rounded-lg hover:bg-acido/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    {loading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                    {loading ? 'Procesando...' : 'Subir y Detectar'}
                </button>
            </div>

            {result && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm mt-6">
                    <div className="flex items-center gap-2 mb-4">
                        <CheckCircle size={20} className="text-acido" />
                        <h3 className="text-lg font-semibold text-grafito">Procesamiento Completado</h3>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-6 text-sm">
                        <div className="p-3 bg-gray-50 rounded-lg">
                            <p className="text-gray-500">Total Animales</p>
                            <p className="text-xl font-bold">{result.total_animals}</p>
                        </div>
                        <div className="p-3 bg-coral/5 rounded-lg">
                            <p className="text-coral">🟢 Celo</p>
                            <p className="text-xl font-bold text-coral">{result.celo_count}</p>
                        </div>
                        <div className="p-3 bg-gray-50 rounded-lg">
                            <p className="text-gray-500">🔴 No celo</p>
                            <p className="text-xl font-bold">{result.no_celo_count}</p>
                        </div>
                    </div>

                    <h4 className="font-semibold text-sm text-gray-500 mb-3 uppercase tracking-wide">Resultados por Animal</h4>
                    <div className="max-h-64 overflow-y-auto border rounded-lg">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50 sticky top-0">
                                <tr>
                                    <th className="text-left px-3 py-2 font-medium text-gray-500">Animal</th>
                                    <th className="text-left px-3 py-2 font-medium text-gray-500">Resultado</th>
                                    <th className="text-left px-3 py-2 font-medium text-gray-500">Confianza</th>
                                </tr>
                            </thead>
                            <tbody>
                                {result.results.map((r, i) => (
                                    <tr key={i} className="border-t border-gray-100">
                                        <td className="px-3 py-2">{r.animal_id}</td>
                                        <td className="px-3 py-2">
                                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${r.result === 'Celo' ? 'bg-coral/10 text-coral' : 'bg-gray-100 text-gray-600'
                                                }`}>
                                                {r.result}
                                            </span>
                                        </td>
                                        <td className="px-3 py-2 text-gray-500">{(r.confidence * 100).toFixed(0)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="mt-4 flex gap-3 items-center flex-wrap">
                        <a href="/history" className="text-sm text-cian hover:underline">Ver en Historial →</a>
                        <a href="http://localhost:8002/" target="_blank" rel="noopener noreferrer" className="text-sm text-cian hover:underline">Ver en Calendario →</a>
                        {result.result_file && (
                            <a href={`/api/uploads/download/${result.result_file}`}
                                className="text-sm bg-acido text-white px-3 py-1 rounded hover:bg-acido/90 transition-colors"
                                download>
                                📥 Descargar Excel Resultado
                            </a>
                        )}
                    </div>

                    {formatProcessingTime(result.processing_time_ms) && (
                        <p className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">
                            ⏱ {formatProcessingTime(result.processing_time_ms)}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

function MilkQualityUploadCard({ farms }: { farms: Farm[] }) {
    const [selectedFarm, setSelectedFarm] = useState<number | ''>('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<MilkQualityUploadResult | null>(null);
    const [error, setError] = useState('');
    const fileRef = useRef<HTMLInputElement>(null);

    const handleSubmit = async () => {
        if (!selectedFarm) { setError('Selecciona una granja'); return; }
        if (!file) { setError('Selecciona un archivo'); return; }

        setLoading(true);
        setError('');
        setResult(null);
        try {
            const data = await milkQualityApi.upload(file, Number(selectedFarm));
            setResult(data);
            setFile(null);
            if (fileRef.current) fileRef.current.value = '';
        } catch (e: any) {
            const detail = e.response?.data?.detail;
            if (Array.isArray(detail)) {
                setError(detail.map((d: any) => d.msg).join('; '));
            } else if (typeof detail === 'string') {
                setError(detail);
            } else {
                setError(e.message || 'Error al subir');
            }
        } finally {
            setLoading(false);
        }
    };

    const formatProcessingTime = (ms: number | null | undefined) => {
        if (ms == null || isNaN(ms)) return null;
        return `Resultados obtenidos en ${Math.round(ms)} ms`;
    };

    return (
        <div>
            <h2 className="text-lg font-bold text-grafito mb-1">🥛 Calidad de Leche</h2>
            <p className="text-gray-500 text-sm mb-4">Sube el Excel espectral (.xlsx) con columnas fijas de longitud de onda.</p>

            <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Granja *</label>
                    <select
                        value={selectedFarm}
                        onChange={e => setSelectedFarm(Number(e.target.value) || '')}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                    >
                        <option value="">Selecciona una granja...</option>
                        {farms.map(f => (
                            <option key={f.id} value={f.id}>{f.name} ({f.location || 'no location'})</option>
                        ))}
                    </select>
                </div>

                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Archivo *</label>
                    <input
                        ref={fileRef}
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={e => setFile(e.target.files?.[0] || null)}
                        className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-cian/10 file:text-cian file:text-sm file:font-medium hover:file:bg-cian/20"
                    />
                    <p className="text-xs text-gray-400 mt-1">Formato: Col A = id, resto = columnas de longitud de onda (esquema fijo)</p>
                </div>

                {error && (
                    <div className="flex items-center gap-2 text-coral text-sm mb-4 p-3 bg-coral/5 rounded-lg">
                        <AlertCircle size={14} /> {error}
                    </div>
                )}

                <button
                    onClick={handleSubmit}
                    disabled={loading || !selectedFarm || !file}
                    className="flex items-center gap-2 bg-acido text-white px-6 py-2.5 rounded-lg hover:bg-acido/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    {loading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                    {loading ? 'Procesando...' : 'Subir y Predecir'}
                </button>
            </div>

            {result && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm mt-6">
                    <div className="flex items-center gap-2 mb-4">
                        <CheckCircle size={20} className="text-acido" />
                        <h3 className="text-lg font-semibold text-grafito">Procesamiento Completado</h3>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-6 text-sm">
                        <div className="p-3 bg-gray-50 rounded-lg">
                            <p className="text-gray-500">Total Muestras</p>
                            <p className="text-xl font-bold">{result.total_samples}</p>
                        </div>
                        <div className="p-3 bg-gray-50 rounded-lg">
                            <p className="text-gray-500">Lower</p>
                            <p className="text-xl font-bold">{result.lower_count}</p>
                        </div>
                        <div className="p-3 bg-coral/5 rounded-lg">
                            <p className="text-coral">Upper</p>
                            <p className="text-xl font-bold text-coral">{result.upper_count}</p>
                        </div>
                    </div>

                    <h4 className="font-semibold text-sm text-gray-500 mb-3 uppercase tracking-wide">Resultados por Muestra</h4>
                    <div className="max-h-64 overflow-y-auto border rounded-lg">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50 sticky top-0">
                                <tr>
                                    <th className="text-left px-3 py-2 font-medium text-gray-500">ID</th>
                                    <th className="text-left px-3 py-2 font-medium text-gray-500">Resultado</th>
                                </tr>
                            </thead>
                            <tbody>
                                {result.results.map((r, i) => (
                                    <tr key={i} className="border-t border-gray-100">
                                        <td className="px-3 py-2">{r.animal_id}</td>
                                        <td className="px-3 py-2">
                                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${r.result === 'Upper' ? 'bg-coral/10 text-coral' : 'bg-gray-100 text-gray-600'
                                                }`}>
                                                {r.result}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="mt-4 flex gap-3 items-center flex-wrap">
                        <a href="/history" className="text-sm text-cian hover:underline">Ver en Historial →</a>
                        {result.result_file && (
                            <a href={`/api/milk-quality/uploads/download/${result.result_file}`}
                                className="text-sm bg-acido text-white px-3 py-1 rounded hover:bg-acido/90 transition-colors"
                                download>
                                📥 Descargar Excel Resultado
                            </a>
                        )}
                    </div>

                    {formatProcessingTime(result.processing_time_ms) && (
                        <p className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">
                            ⏱ {formatProcessingTime(result.processing_time_ms)}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

export default function UploadView() {
    const [farms, setFarms] = useState<Farm[]>([]);

    useEffect(() => {
        farmsApi.list().then(setFarms);
    }, []);

    if (farms.length === 0) {
        return (
            <div className="text-center py-20">
                <AlertCircle size={48} className="mx-auto text-gray-300 mb-4" />
                <h2 className="text-xl font-semibold text-gray-500 mb-2">No hay granjas registradas</h2>
                <p className="text-gray-400 mb-4">Necesitas registrar una granja antes de subir datos.</p>
                <a href="/farms" className="inline-block bg-acido text-white px-6 py-2 rounded-lg hover:bg-acido/90">
                    Registrar Granja
                </a>
            </div>
        );
    }

    return (
        <div>
            <h1 className="text-2xl font-bold text-grafito mb-2">📂 Subir Datos</h1>
            <p className="text-gray-500 mb-8">Sube los datos de tus animales para obtener predicciones.</p>

            <div className="grid md:grid-cols-2 gap-6">
                <EstrusUploadCard farms={farms} />
                <MilkQualityUploadCard farms={farms} />
            </div>
        </div>
    );
}
