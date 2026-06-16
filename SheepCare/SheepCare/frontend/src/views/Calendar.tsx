import { useEffect, useState } from 'react';
import { Calendar, CheckCircle, XCircle, ExternalLink } from 'lucide-react';
import { uploadsApi } from '../api';
import type { UploadSummary } from '../api';

const FARMCALENDAR_WEB_URL = 'http://localhost:8002/';

export default function CalendarView() {
    const [uploads, setUploads] = useState<UploadSummary[]>([]);

    useEffect(() => {
        uploadsApi.list().then(setUploads);
    }, []);

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-grafito">📅 Detecciones Registradas</h1>
                    <p className="text-gray-500 text-sm mt-1">
                        Cada carga se registra como Observation en el Farm Calendar
                    </p>
                </div>
                <a
                    href={FARMCALENDAR_WEB_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm bg-cian text-white px-4 py-2 rounded-lg hover:bg-cian/90 transition-colors"
                >
                    <ExternalLink size={14} /> Abrir Farm Calendar
                </a>
            </div>

            {/* Lista de detecciones */}
            {uploads.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center shadow-sm">
                    <Calendar size={48} className="mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-400">Aún no hay detecciones registradas.</p>
                    <p className="text-gray-400 text-sm mt-1">Sube un archivo desde la sección Subir para crear la primera.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                        <h2 className="font-semibold text-grafito flex items-center gap-2">
                            <Calendar size={16} /> Últimas detecciones
                        </h2>
                    </div>
                    <div className="divide-y divide-gray-100">
                        {uploads.slice(0, 20).map(u => (
                            <div key={u.id} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50">
                                <div className="flex items-center gap-3">
                                    {u.celo_count > 0 ? (
                                        <CheckCircle size={16} className="text-coral" />
                                    ) : (
                                        <XCircle size={16} className="text-gray-300" />
                                    )}
                                    <div>
                                        <p className="text-sm font-medium text-grafito">{u.farm_name}</p>
                                        <p className="text-xs text-gray-400">{u.filename} · {u.upload_date?.slice(0, 10)}</p>
                                    </div>
                                </div>
                                <div className="flex gap-3 text-xs">
                                    <span className="text-gray-500">{u.total_animals} animales</span>
                                    {u.celo_count > 0 && <span className="text-coral font-medium">🟢 {u.celo_count} celo</span>}
                                    <span className="text-gray-500">🔴 {u.no_celo_count} no celo</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
