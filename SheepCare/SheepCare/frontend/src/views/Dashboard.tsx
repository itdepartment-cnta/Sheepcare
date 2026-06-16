import { useEffect, useState } from 'react';
import { LayoutDashboard, Upload, Activity, Cloud } from 'lucide-react';
import { farmsApi, resultsApi, uploadsApi, settingsApi } from '../api';

export default function Dashboard() {
    const [farmCount, setFarmCount] = useState(0);
    const [latest, setLatest] = useState<any>(null);
    const [lastUpload, setLastUpload] = useState<any>(null);
    const [syncStatus, setSyncStatus] = useState<any>(null);

    useEffect(() => {
        farmsApi.list().then(r => setFarmCount(r.length));
        resultsApi.latest().then(r => setLatest(r));
        uploadsApi.list().then(r => setLastUpload(r[0] || null));
        settingsApi.syncStatus().then(r => setSyncStatus(r));
    }, []);

    const stats = [
        { icon: Building2, label: 'Granjas', value: farmCount, color: 'text-acido' },
        { icon: Activity, label: 'Animales Procesados', value: latest ? '✓' : '—', color: 'text-cian' },
        { icon: Cloud, label: 'Última Sincronización', value: syncStatus?.last_sync?.slice(0, 10) || 'Nunca', color: 'text-gray-500' },
    ];

    return (
        <div>
            <h1 className="text-2xl font-bold text-grafito mb-2">🐑 Panel Principal</h1>
            <p className="text-gray-500 mb-8">Sistema de Detección Inteligente de Celos — Resumen</p>

            {/* Stat cards */}
            <div className="grid grid-cols-3 gap-6 mb-8">
                {stats.map((s, i) => (
                    <div key={i} className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
                        <div className="flex items-center gap-3 mb-2">
                            <s.icon size={20} className={s.color} />
                            <span className="text-sm text-gray-500">{s.label}</span>
                        </div>
                        <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                    </div>
                ))}
            </div>

            {/* Latest Upload */}
            {lastUpload && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm mb-6">
                    <h2 className="text-lg font-semibold text-grafito mb-4">📂 Última Carga</h2>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <span className="text-gray-500">Granja:</span>
                            <p className="font-medium">{lastUpload.farm_name}</p>
                        </div>
                        <div>
                            <span className="text-gray-500">Archivo:</span>
                            <p className="font-medium">{lastUpload.filename}</p>
                        </div>
                        <div>
                            <span className="text-gray-500">Fecha:</span>
                            <p className="font-medium">{lastUpload.upload_date?.slice(0, 10)}</p>
                        </div>
                        <div>
                            <span className="text-gray-500">Animales:</span>
                            <p className="font-medium">{lastUpload.total_animals}</p>
                        </div>
                        <div>
                            <span className="text-gray-500 text-coral">🟢 Celo:</span>
                            <p className="font-medium text-coral">{lastUpload.celo_count}</p>
                        </div>
                        <div>
                            <span className="text-gray-500">🔴 No celo:</span>
                            <p className="font-medium">{lastUpload.no_celo_count}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Latest result */}
            {latest && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-grafito mb-4">📊 Última Detección</h2>
                    <div className="flex items-center gap-4">
                        <div className={`w-3 h-3 rounded-full ${latest.result === 'Celo' ? 'bg-coral' : 'bg-verde-texto'}`} />
                        <div>
                            <p className="font-medium">
                                {latest.animal_tag} — <span className={latest.result === 'Celo' ? 'text-coral' : 'text-verde-texto'}>{latest.result}</span>
                            </p>
                            <p className="text-sm text-gray-500">
                                Confianza: {(latest.confidence * 100).toFixed(1)}% · {latest.farm_name}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {!lastUpload && !latest && (
                <div className="bg-white rounded-lg border border-gray-200 p-12 shadow-sm text-center">
                    <Upload size={48} className="mx-auto text-gray-300 mb-4" />
                    <h2 className="text-lg font-semibold text-gray-500 mb-2">Sin datos aún</h2>
                    <p className="text-gray-400 mb-4">Comienza registrando una granja y subiendo datos.</p>
                    <a href="/farms" className="inline-block bg-acido text-white px-6 py-2 rounded-lg hover:bg-acido/90 transition-colors">
                        Registrar Explotación
                    </a>
                </div>
            )}
        </div>
    );
}

function Building2(props: any) { return <LayoutDashboard {...props} />; }
