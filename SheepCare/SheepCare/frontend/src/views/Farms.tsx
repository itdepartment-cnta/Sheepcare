import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, RefreshCw } from 'lucide-react';
import { farmsApi } from '../api';
import type { Farm } from '../api';

export default function FarmsView() {
    const [farms, setFarms] = useState<Farm[]>([]);
    const [showForm, setShowForm] = useState(false);
    const [editing, setEditing] = useState<Farm | null>(null);
    const [name, setName] = useState('');
    const [location, setLocation] = useState('');

    const load = () => farmsApi.list().then(setFarms);

    useEffect(() => { load(); }, []);

    const handleSubmit = async () => {
        if (!name.trim()) return;
        if (editing) {
            await farmsApi.update(editing.id, name, location);
        } else {
            await farmsApi.create(name, location);
        }
        setShowForm(false);
        setEditing(null);
        setName('');
        setLocation('');
        load();
    };

    const handleEdit = (f: Farm) => {
        setEditing(f);
        setName(f.name);
        setLocation(f.location);
        setShowForm(true);
    };

    const handleDelete = async (id: number) => {
        if (!confirm('¿Eliminar esta granja y todos sus datos?')) return;
        await farmsApi.delete(id);
        load();
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-grafito">🏘️ Granjas</h1>
                    <p className="text-gray-500 text-sm mt-1">Registra y gestiona tus granjas</p>
                </div>
                <div className="flex gap-2">
                    {!showForm && (
                        <button
                            onClick={() => { setEditing(null); setName(''); setLocation(''); setShowForm(true); }}
                            className="flex items-center gap-2 bg-acido text-white px-4 py-2 rounded-lg hover:bg-acido/90 transition-colors"
                        >
                            <Plus size={16} /> Añadir Granja
                        </button>
                    )}
                    <button onClick={load} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
                        <RefreshCw size={16} className="text-gray-500" />
                    </button>
                </div>
            </div>

            {showForm && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6 shadow-sm">
                    <h3 className="font-semibold text-grafito mb-4">{editing ? '✏️ Editar Granja' : '➕ Nueva Granja'}</h3>
                    <div className="flex gap-4 mb-4">
                        <input
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="Nombre de la granja *"
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                        />
                        <input
                            value={location}
                            onChange={e => setLocation(e.target.value)}
                            placeholder="Ubicación (opcional)"
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                        />
                    </div>
                    <div className="flex gap-2">
                        <button onClick={handleSubmit} className="bg-acido text-white px-4 py-2 rounded-lg hover:bg-acido/90 transition-colors">
                            {editing ? 'Actualizar' : 'Crear'}
                        </button>
                        <button onClick={() => { setShowForm(false); setEditing(null); }} className="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                            Cancelar
                        </button>
                    </div>
                </div>
            )}

            {farms.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center shadow-sm">
                    <p className="text-gray-400 mb-2">No hay granjas registradas aún.</p>
                    <p className="text-gray-400 text-sm">Crea tu primera granja para empezar a subir datos.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-grafito text-white">
                            <tr>
                                <th className="text-left px-4 py-3 text-sm font-semibold">ID</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Nombre</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Ubicación</th>
                                <th className="text-left px-4 py-3 text-sm font-semibold">Creado</th>
                                <th className="text-right px-4 py-3 text-sm font-semibold">Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {farms.map(f => (
                                <tr key={f.id} className="border-t border-gray-100 hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm text-gray-500">{f.id}</td>
                                    <td className="px-4 py-3 font-medium">{f.name}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{f.location || '—'}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{f.created_at?.slice(0, 10)}</td>
                                    <td className="px-4 py-3 text-right">
                                        <button onClick={() => handleEdit(f)} className="p-1.5 hover:bg-gray-100 rounded transition-colors">
                                            <Pencil size={14} className="text-gray-400" />
                                        </button>
                                        <button onClick={() => handleDelete(f.id)} className="p-1.5 hover:bg-red-50 rounded transition-colors ml-1">
                                            <Trash2 size={14} className="text-coral" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
