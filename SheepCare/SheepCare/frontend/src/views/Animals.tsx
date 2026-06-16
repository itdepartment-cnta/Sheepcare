import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { farmsApi, animalsApi } from '../api';
import type { Farm, Animal } from '../api';

export default function AnimalsView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [animals, setAnimals] = useState<Animal[]>([]);
    const [farmFilter, setFarmFilter] = useState<number | ''>('');

    useEffect(() => {
        farmsApi.list().then(setFarms);
    }, []);

    useEffect(() => {
        animalsApi.list(farmFilter || undefined).then(setAnimals);
    }, [farmFilter]);

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-grafito">🐑 Animales</h1>
                    <p className="text-gray-500 text-sm mt-1">Los animales se registran automáticamente desde los archivos subidos</p>
                </div>
                <button onClick={() => animalsApi.list(farmFilter || undefined).then(setAnimals)}
                    className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
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
            </div>

            {animals.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center shadow-sm">
                    <p className="text-gray-400 mb-2">No hay animales registrados.</p>
                    <p className="text-gray-400 text-sm">Los animales se crean automáticamente al subir archivos de datos.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-grafito text-white">
                            <tr>
                                <th className="text-left px-4 py-3 text-sm font-semibold">ID</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Crota</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Nombre</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Granja</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Registrado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {animals.map(a => (
                                <tr key={a.id} className="border-t border-gray-100 hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm text-gray-500">{a.id}</td>
                                    <td className="px-4 py-3 font-medium">{a.external_tag}</td>
                                    <td className="px-4 py-3 text-gray-500">{a.name || '—'}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{(a as any).farm_name || ''}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{a.created_at?.slice(0, 10)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
