import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Cloud, CheckCircle, AlertCircle, XCircle, Wifi, WifiOff, Zap } from 'lucide-react';
import { settingsApi } from '../api';
import type { SyncStatus, CloudConfig, ConnectivityStatus } from '../api';

export default function SettingsView() {
    const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
    const [cloudConfig, setCloudConfig] = useState<CloudConfig | null>(null);
    const [connectivity, setConnectivity] = useState<ConnectivityStatus | null>(null);
    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState<string>('');
    const connectivityTimer = useRef<ReturnType<typeof setInterval> | null>(null);

    // Cloud config form
    const [showCloudForm, setShowCloudForm] = useState(false);
    const [cloudUrl, setCloudUrl] = useState('');
    const [cloudEmail, setCloudEmail] = useState('');
    const [cloudPassword, setCloudPassword] = useState('');
    const [cloudError, setCloudError] = useState('');
    const [cloudSaving, setCloudSaving] = useState(false);

    const load = () => {
        settingsApi.syncStatus().then(setSyncStatus);
        settingsApi.cloudConfig().then(setCloudConfig);
    };

    useEffect(() => { load(); }, []);

    // Poll connectivity every 30 s when cloud is configured
    useEffect(() => {
        if (!cloudConfig?.configured) {
            setConnectivity(null);
            return;
        }
        const poll = () => settingsApi.checkConnectivity().then(setConnectivity).catch(() => {});
        poll();
        connectivityTimer.current = setInterval(poll, 30_000);
        return () => {
            if (connectivityTimer.current) clearInterval(connectivityTimer.current);
        };
    }, [cloudConfig?.configured]);

    const handleSync = async () => {
        setSyncing(true);
        setSyncResult('');
        try {
            const r = await settingsApi.syncNow();
            setSyncResult(
                r.success
                    ? `✅ Sincronizados ${r.synced_count} registros (push + pull)`
                    : `❌ ${r.error}`
            );
            load();
        } catch (e: any) {
            const detail = e.response?.data?.detail || e.message;
            setSyncResult(`❌ ${detail}`);
        } finally {
            setSyncing(false);
        }
    };

    const handleSaveCloud = async () => {
        if (!cloudUrl.trim() || !cloudEmail.trim() || !cloudPassword.trim()) {
            setCloudError('Todos los campos son obligatorios');
            return;
        }
        setCloudSaving(true);
        setCloudError('');
        try {
            const result = await settingsApi.saveCloudConfig(cloudUrl, cloudEmail, cloudPassword);
            setCloudConfig(result);
            setShowCloudForm(false);
            setCloudPassword('');
        } catch (e: any) {
            const detail = e.response?.data?.detail || e.message;
            setCloudError(detail);
        } finally {
            setCloudSaving(false);
        }
    };

    const handleClearCloud = async () => {
        if (!confirm('¿Eliminar la configuración de sincronización cloud?')) return;
        await settingsApi.clearCloudConfig();
        setCloudConfig(null);
        setShowCloudForm(false);
        setCloudPassword('');
    };

    return (
        <div>
            <h1 className="text-2xl font-bold text-grafito mb-2">⚙️ Ajustes</h1>
            <p className="text-gray-500 mb-8">Configuración de la sincronización en la nube</p>

            <div className="max-w-2xl">
                {/* Cloud Sync */}
                <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                        <Cloud size={18} className="text-cian" />
                        <h2 className="text-lg font-semibold text-grafito">Sincronización Cloud</h2>
                    </div>

                    {/* Cloud credentials status */}
                    {cloudConfig?.configured ? (
                        <div className="mb-4 p-3 bg-acido/5 rounded-lg border border-acido/20">
                            <div className="flex items-center gap-2 mb-1">
                                <CheckCircle size={14} className="text-acido" />
                                <span className="text-sm font-medium text-grafito">Conectado</span>
                            </div>
                            <p className="text-xs text-gray-500">{cloudConfig.email}</p>
                            <p className="text-xs text-gray-400 mt-0.5">{cloudConfig.cloud_url}</p>
                        </div>
                    ) : (
                        <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="flex items-center gap-2 mb-1">
                                <XCircle size={14} className="text-gray-400" />
                                <span className="text-sm font-medium text-gray-500">No configurado</span>
                            </div>
                            <p className="text-xs text-gray-400">
                                Configura las credenciales cloud para habilitar la sincronización bidireccional.
                            </p>
                        </div>
                    )}

                    {/* Connectivity badge */}
                    {cloudConfig?.configured && (
                        <div className={`mb-4 flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${
                            connectivity === null
                                ? 'bg-gray-50 border-gray-200 text-gray-400'
                                : connectivity.reachable
                                    ? 'bg-green-50 border-green-200 text-green-700'
                                    : 'bg-amber-50 border-amber-200 text-amber-700'
                        }`}>
                            {connectivity === null ? (
                                <><div className="w-2 h-2 rounded-full bg-gray-300 animate-pulse" />Comprobando conexión...</>
                            ) : connectivity.reachable ? (
                                <><Wifi size={13} /><span>Cloud accesible</span><span className="ml-auto flex items-center gap-1 text-green-600"><Zap size={11} />Sincronización automática activa</span></>
                            ) : (
                                <><WifiOff size={13} /><span>Cloud no accesible — solo sincronización manual</span></>
                            )}
                        </div>
                    )}

                    {/* Sync status */}
                    {syncStatus && (
                        <div className="space-y-2 text-sm mb-4">
                            <div className="flex justify-between">
                                <span className="text-gray-500">Última Sinc.:</span>
                                <span>{syncStatus.last_sync || 'Nunca'}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Estado:</span>
                                <span className={`font-medium ${syncStatus.last_status === 'success' ? 'text-verde-texto' : 'text-coral'}`}>
                                    {syncStatus.last_status || '—'}
                                </span>
                            </div>
                            {syncStatus.last_error && (
                                <div className="text-coral text-xs">{syncStatus.last_error}</div>
                            )}
                        </div>
                    )}

                    {/* Cloud config form */}
                    {showCloudForm && (
                        <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                            <h3 className="text-sm font-semibold text-grafito mb-3">Credenciales Cloud</h3>
                            <div className="space-y-2">
                                <input
                                    value={cloudUrl}
                                    onChange={e => setCloudUrl(e.target.value)}
                                    placeholder="URL Cloud (ej. https://cloud.myserver.com)"
                                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                                />
                                <input
                                    value={cloudEmail}
                                    onChange={e => setCloudEmail(e.target.value)}
                                    placeholder="Email (cuenta cloud)"
                                    type="email"
                                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                                />
                                <input
                                    value={cloudPassword}
                                    onChange={e => setCloudPassword(e.target.value)}
                                    placeholder="Contraseña"
                                    type="password"
                                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-acido"
                                />
                                {cloudError && (
                                    <div className="flex items-center gap-1 text-coral text-xs">
                                        <AlertCircle size={12} /> {cloudError}
                                    </div>
                                )}
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSaveCloud}
                                        disabled={cloudSaving}
                                        className="bg-acido text-white px-3 py-1.5 text-sm rounded-lg hover:bg-acido/90 disabled:opacity-50"
                                    >
                                        {cloudSaving ? 'Guardando...' : 'Guardar y Probar'}
                                    </button>
                                    <button
                                        onClick={() => setShowCloudForm(false)}
                                        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                                    >
                                        Cancelar
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex gap-2 flex-wrap">
                        <button
                            onClick={handleSync}
                            disabled={syncing}
                            className="flex items-center gap-2 bg-cian text-white px-4 py-2 rounded-lg hover:bg-cian/90 disabled:opacity-50 transition-colors text-sm"
                        >
                            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                            {syncing ? 'Sincronizando...' : 'Sincronizar Ahora'}
                        </button>
                        {!showCloudForm && (
                            <button
                                onClick={() => {
                                    setCloudUrl(cloudConfig?.cloud_url || '');
                                    setCloudEmail(cloudConfig?.email || '');
                                    setShowCloudForm(true);
                                }}
                                className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                            >
                                {cloudConfig?.configured ? 'Cambiar Credenciales' : 'Configurar Cloud'}
                            </button>
                        )}
                        {cloudConfig?.configured && !showCloudForm && (
                            <button
                                onClick={handleClearCloud}
                                className="flex items-center gap-2 px-4 py-2 border border-coral/30 text-coral rounded-lg hover:bg-coral/5 transition-colors text-sm"
                            >
                                <XCircle size={14} /> Desconectar
                            </button>
                        )}
                    </div>

                    {syncResult && (
                        <p className="mt-3 text-sm">{syncResult}</p>
                    )}

                    <div className="mt-4 pt-3 border-t border-gray-100">
                        <p className="text-xs text-gray-400">
                            La sincronización envía datos locales a la nube y trae datos creados en la nube.
                            Cuando hay conexión con el cloud, se sincroniza automáticamente cada 15 minutos.
                            Necesitas una cuenta en SHEEPCARE Cloud para usar esta función.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
