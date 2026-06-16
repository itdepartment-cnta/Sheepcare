import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { farmsApi, resultsApi } from '../api';
import type { Farm, DetectionResult } from '../api';

export default function HistoryView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [results, setResults] = useState<DetectionResult[]>([]);
    const [farmFilter, setFarmFilter] = useState<number | ''>('');
    const [resultFilter, setResultFilter] = useState('');

    const load = () => {
        resultsApi.list({
            farm_id: farmFilter || undefined,
            result: resultFilter || undefined,
        }).then(setResults);
    };

    useEffect(() => { farmsApi.list().then(setFarms); }, []);
    useEffect(() => { load(); }, [farmFilter, resultFilter]);

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-grafito">📋 Historial de Detecciones</h1>
                    <p className="text-gray-500 text-sm mt-1">Consulta todos los resultados de detección</p>
                </div>
                <button onClick={load} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
                    <RefreshCw size={16} className="text-gray-500" />
                </button>
            </div>

            {/* Filters */}
            <div className="flex gap-4 mb-6">
                <select
                    value={farmFilter}
                    onChange={e => setFarmFilter(Number(e.target.value) || '')}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-acido"
                >
                    <option value="">Todas las Granjas</option>
                    {farms.map(f => (
                        <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                </select>

                <select
                    value={resultFilter}
                    onChange={e => setResultFilter(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-acido"
                >
                    <option value="">Todos los Resultados</option>
                    <option value="Celo">Celo</option>
                    <option value="No celo">No celo</option>
                </select>
            </div>

            {/* Table */}
            {results.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center shadow-sm">
                    <p className="text-gray-400">No se encontraron resultados de detección.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-grafito text-white">
                            <tr>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Animal</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Granja</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Resultado</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Confianza</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Archivo</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Fecha</th>
                            </tr>
                        </thead>
                        <tbody>
                            {results.map(r => (
                                <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                                    <td className="px-4 py-3">
                                        <span className="font-medium">{r.animal_tag}</span>
                                        {r.animal_name && <span className="text-gray-400 ml-1">({r.animal_name})</span>}
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{r.farm_name}</td>
                                    <td className="px-4 py-3">
                                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${r.result === 'Celo' ? 'bg-coral/10 text-coral' : 'bg-gray-100 text-gray-600'
                                            }`}>
                                            {r.result}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{(r.confidence * 100).toFixed(1)}%</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{r.filename}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{r.created_at?.slice(0, 10)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
