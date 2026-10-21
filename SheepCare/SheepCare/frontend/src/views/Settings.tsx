import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ArrowsClockwise, Cloud, CloudSun, Lightning, LinkBreak, PlugsConnected, Timer, WifiHigh, WifiSlash } from '@phosphor-icons/react';
import { settingsApi } from '../api';
import type { CloudConfig, ConnectivityStatus, SyncStatus, WeatherConfig } from '../api';
import { mensajeDeError } from '../lib/errors';
import { fechaHora, numero } from '../lib/format';
import {
    avisar, Button, Card, CardHeader, Chip, ConfirmDialog, ErrorState, PageHeader, Skeleton, TextField,
} from '../components/ui';

/** Par etiqueta/valor semántico: <dt> y <dd> dentro de un <dl>. */
function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
    return (
        <div className="flex items-baseline justify-between gap-4">
            <dt className="text-small text-ink-3">{etiqueta}</dt>
            <dd className="text-right text-body text-ink">{children}</dd>
        </div>
    );
}

/** Clave de OpenWeatherMap que cada usuario aporta para consultar el tiempo. */
function WeatherKeyCard() {
    const [config, setConfig] = useState<WeatherConfig | null>(null);
    const [errorCarga, setErrorCarga] = useState(false);
    const [editando, setEditando] = useState(false);
    const [clave, setClave] = useState('');
    const [errorClave, setErrorClave] = useState('');
    const [guardando, setGuardando] = useState(false);
    const [confirmarBorrado, setConfirmarBorrado] = useState(false);
    const [borrando, setBorrando] = useState(false);

    const cargar = useCallback(() => {
        settingsApi.weatherConfig()
            .then(c => { setConfig(c); setErrorCarga(false); })
            .catch(() => setErrorCarga(true));
    }, []);

    useEffect(() => { cargar(); }, [cargar]);

    const cerrar = () => {
        setEditando(false);
        setClave('');
        setErrorClave('');
    };

    const guardar = async (e: FormEvent) => {
        e.preventDefault();
        const limpia = clave.trim();
        if (!limpia) {
            setErrorClave('Pega aquí tu clave de OpenWeatherMap.');
            return;
        }
        if (/\s/.test(limpia)) {
            setErrorClave('La clave no puede contener espacios.');
            return;
        }
        setGuardando(true);
        try {
            setConfig(await settingsApi.saveWeatherKey(limpia));
            cerrar();
            avisar.ok('Clave guardada', 'Ya puedes consultar el tiempo de tus granjas.');
        } catch (err) {
            setErrorClave(mensajeDeError(err, 'No se pudo guardar la clave. Inténtalo de nuevo.'));
        } finally {
            setGuardando(false);
        }
    };

    const borrar = async () => {
        setBorrando(true);
        try {
            setConfig(await settingsApi.clearWeatherKey());
            setConfirmarBorrado(false);
            avisar.ok('Clave eliminada', 'Se ha borrado la clave de OpenWeatherMap.');
        } catch (err) {
            avisar.error('No se pudo eliminar la clave', mensajeDeError(err, 'Inténtalo de nuevo.'));
        } finally {
            setBorrando(false);
        }
    };

    return (
        <>
            <Card index={2} className="mt-4">
                <CardHeader
                    title="Servicio meteorológico"
                    description="El tiempo de tus granjas se consulta en OpenWeatherMap con tu propia clave."
                    icon={<CloudSun size={18} aria-hidden="true" />}
                />

                {errorCarga ? (
                    <ErrorState action={<Button onClick={cargar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                ) : config === null ? (
                    <Skeleton className="h-16 w-full" />
                ) : (
                    <div className="space-y-5">
                        <div className="rounded-lg border border-line bg-canvas p-4">
                            <div className="flex flex-wrap items-center gap-2">
                                {config.configured ? <Chip tone="ok">Clave guardada</Chip> : <Chip>Sin clave</Chip>}
                                {config.configured && (
                                    <span className="tabular text-body text-ink-2">…{config.key_hint}</span>
                                )}
                            </div>
                            <p className="mt-2 text-small text-ink-3">
                                {config.configured
                                    ? 'La clave se guarda solo en este equipo y no se vuelve a mostrar.'
                                    : 'Sin clave no se puede consultar el tiempo. Puedes obtener una gratuita registrándote en openweathermap.org.'}
                            </p>
                        </div>

                        {editando && (
                            <form onSubmit={guardar} noValidate className="space-y-4 rounded-lg border border-line bg-canvas p-4">
                                <TextField
                                    label="Clave de OpenWeatherMap"
                                    required
                                    autoFocus
                                    type="password"
                                    autoComplete="off"
                                    spellCheck={false}
                                    value={clave}
                                    error={errorClave}
                                    onChange={e => { setClave(e.target.value); setErrorClave(''); }}
                                />
                                <div className="flex gap-2">
                                    <Button type="submit" variant="primary" loading={guardando}>Guardar clave</Button>
                                    <Button onClick={cerrar} disabled={guardando}>Cancelar</Button>
                                </div>
                            </form>
                        )}

                        {!editando && (
                            <div className="flex flex-wrap gap-2">
                                <Button variant={config.configured ? 'secondary' : 'primary'} onClick={() => setEditando(true)}>
                                    {config.configured ? 'Cambiar clave' : 'Añadir clave'}
                                </Button>
                                {config.configured && (
                                    <Button variant="danger" onClick={() => setConfirmarBorrado(true)}>Eliminar clave</Button>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </Card>

            <ConfirmDialog
                open={confirmarBorrado}
                title="¿Eliminar la clave?"
                confirmLabel="Eliminar clave"
                loading={borrando}
                onConfirm={borrar}
                onCancel={() => { if (!borrando) setConfirmarBorrado(false); }}
            >
                Dejará de poder consultarse el tiempo hasta que añadas otra clave.
            </ConfirmDialog>
        </>
    );
}

export default function SettingsView() {
    const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
    const [cloudConfig, setCloudConfig] = useState<CloudConfig | null>(null);
    const [cargado, setCargado] = useState(false);
    const [errorCarga, setErrorCarga] = useState(false);
    const [connectivity, setConnectivity] = useState<ConnectivityStatus | null>(null);
    const [syncing, setSyncing] = useState(false);
    const connectivityTimer = useRef<ReturnType<typeof setInterval> | null>(null);

    // Formulario de credenciales de la nube
    const [showCloudForm, setShowCloudForm] = useState(false);
    const [cloudUrl, setCloudUrl] = useState('');
    const [cloudEmail, setCloudEmail] = useState('');
    const [cloudPassword, setCloudPassword] = useState('');
    const [errores, setErrores] = useState<{ url?: string; email?: string; password?: string }>({});
    const [errorServidor, setErrorServidor] = useState('');
    const [cloudSaving, setCloudSaving] = useState(false);

    const [confirmarDesconexion, setConfirmarDesconexion] = useState(false);
    const [desconectando, setDesconectando] = useState(false);

    const load = useCallback(() => {
        Promise.all([settingsApi.syncStatus(), settingsApi.cloudConfig()])
            .then(([s, c]) => {
                setSyncStatus(s);
                setCloudConfig(c);
            })
            .then(() => setErrorCarga(false))
            .catch(() => setErrorCarga(true))
            .finally(() => setCargado(true));
    }, []);

    useEffect(() => { load(); }, [load]);

    // Comprueba la conexión cada 30 s mientras la nube esté configurada
    useEffect(() => {
        if (!cloudConfig?.configured) return;
        const poll = () => settingsApi.checkConnectivity().then(setConnectivity).catch(() => { });
        poll();
        connectivityTimer.current = setInterval(poll, 30_000);
        return () => {
            if (connectivityTimer.current) clearInterval(connectivityTimer.current);
        };
    }, [cloudConfig?.configured]);

    const configurada = !!cloudConfig?.configured;
    const conectividad = configurada ? connectivity : null;

    const handleSync = async () => {
        setSyncing(true);
        try {
            const r = await settingsApi.syncNow();
            if (r.success) {
                const partes = [`${numero(r.synced_count)} enviados`, `${numero(r.pulled_count ?? 0)} recibidos`];
                if (r.removed_count) partes.push(`${numero(r.removed_count)} ${r.removed_count === 1 ? 'granja ya no es visible' : 'granjas ya no son visibles'}`);
                if (r.blocked_count) partes.push(`${numero(r.blocked_count)} sin permiso (no se envían)`);
                avisar.ok('Sincronización completada', `${partes.join(', ')}.`);
            } else {
                avisar.error('No se pudo sincronizar', r.error || 'Inténtalo de nuevo.');
            }
            load();
        } catch (err) {
            avisar.error('No se pudo sincronizar', mensajeDeError(err, 'Inténtalo de nuevo.'));
        } finally {
            setSyncing(false);
        }
    };

    const abrirFormulario = () => {
        setCloudUrl(cloudConfig?.cloud_url || '');
        setCloudEmail(cloudConfig?.email || '');
        setCloudPassword('');
        setErrores({});
        setErrorServidor('');
        setShowCloudForm(true);
    };

    const cerrarFormulario = () => {
        setShowCloudForm(false);
        setCloudPassword('');
        setErrores({});
        setErrorServidor('');
    };

    const handleSaveCloud = async (e: FormEvent) => {
        e.preventDefault();
        const nuevos = {
            url: cloudUrl.trim() ? undefined : 'Indica la dirección de la nube.',
            email: cloudEmail.trim() ? undefined : 'Indica el correo de la cuenta.',
            password: cloudPassword.trim() ? undefined : 'Indica la contraseña.',
        };
        setErrores(nuevos);
        setErrorServidor('');
        if (nuevos.url || nuevos.email || nuevos.password) return;

        setCloudSaving(true);
        try {
            const result = await settingsApi.saveCloudConfig(cloudUrl, cloudEmail, cloudPassword);
            setCloudConfig(result);
            setConnectivity(null);
            cerrarFormulario();
            avisar.ok('Credenciales guardadas', 'La conexión con la nube se ha probado correctamente.');
        } catch (err) {
            setErrorServidor(mensajeDeError(err, 'No se pudo conectar con la nube. Revisa los datos e inténtalo de nuevo.'));
        } finally {
            setCloudSaving(false);
        }
    };

    const handleClearCloud = async () => {
        setDesconectando(true);
        try {
            await settingsApi.clearCloudConfig();
            setCloudConfig(null);
            setConnectivity(null);
            cerrarFormulario();
            setConfirmarDesconexion(false);
            avisar.ok('Sincronización desactivada', 'Se han eliminado las credenciales de la nube.');
        } catch (err) {
            avisar.error('No se pudo desconectar', mensajeDeError(err, 'Inténtalo de nuevo.'));
        } finally {
            setDesconectando(false);
        }
    };

    return (
        <>
            <PageHeader
                eyebrow="Sistema"
                title="Ajustes"
                description="Conexión con la nube y servicios externos."
            />

            <div className="max-w-2xl">
                <Card index={1}>
                    <CardHeader
                        title="Sincronización con la nube"
                        description="Envía los datos locales a SheepCare Cloud y trae los creados allí."
                        icon={<Cloud size={18} aria-hidden="true" />}
                    />

                    {errorCarga ? (
                        <ErrorState action={<Button onClick={load}>Reintentar</Button>}>
                            Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                        </ErrorState>
                    ) : !cargado ? (
                        <div className="space-y-3" role="status" aria-label="Cargando">
                            <Skeleton className="h-16 w-full" />
                            <Skeleton className="h-24 w-full" />
                        </div>
                    ) : (
                        <div className="space-y-5">
                            {/* Estado de las credenciales */}
                            <div className="rounded-lg border border-line bg-canvas p-4">
                                <div className="flex flex-wrap items-center gap-2">
                                    {configurada ? (
                                        <Chip tone="ok">Conectado</Chip>
                                    ) : (
                                        <Chip>No configurado</Chip>
                                    )}
                                    {configurada && <span className="text-body font-medium text-ink">{cloudConfig?.email}</span>}
                                </div>
                                <p className="mt-2 break-all text-small text-ink-3">
                                    {configurada
                                        ? cloudConfig?.cloud_url
                                        : 'Configura las credenciales de la nube para activar la sincronización en los dos sentidos.'}
                                </p>
                            </div>

                            {/* Conectividad */}
                            {configurada && (
                                <p
                                    role="status"
                                    className={
                                        'flex flex-wrap items-center gap-2 rounded-md px-3 py-2 text-small ' +
                                        (conectividad === null
                                            ? 'bg-canvas-soft text-ink-2'
                                            : conectividad.reachable
                                                ? 'bg-ok-bg text-ok-text'
                                                : 'bg-warn-bg text-warn-text')
                                    }
                                >
                                    {conectividad === null ? (
                                        <>Comprobando la conexión…</>
                                    ) : conectividad.reachable ? (
                                        <>
                                            <WifiHigh size={16} aria-hidden="true" />
                                            <span>La nube es accesible.</span>
                                            <span className="ml-auto inline-flex items-center gap-1">
                                                <Lightning size={14} aria-hidden="true" />
                                                Sincronización automática activa
                                            </span>
                                        </>
                                    ) : (
                                        <>
                                            <WifiSlash size={16} aria-hidden="true" />
                                            La nube no es accesible. Solo se puede sincronizar a mano.
                                        </>
                                    )}
                                </p>
                            )}

                            {/* Última sincronización */}
                            {syncStatus && (
                                <dl className="space-y-2">
                                    <Dato etiqueta="Última sincronización">{syncStatus.last_sync ? fechaHora(syncStatus.last_sync) : 'Nunca'}</Dato>
                                    <Dato etiqueta="Estado">
                                        {syncStatus.last_status ? (
                                            <Chip tone={syncStatus.last_status === 'success' ? 'ok' : 'danger'}>
                                                {syncStatus.last_status === 'success' ? 'Correcta' : syncStatus.last_status === 'error' ? 'Con errores' : syncStatus.last_status}
                                            </Chip>
                                        ) : '—'}
                                    </Dato>
                                    {syncStatus.last_error && (
                                        <div className="rounded-md bg-danger-bg px-3 py-2 text-small text-danger-text">
                                            <p>La última sincronización no se completó. Comprueba la conexión con la nube y vuelve a intentarlo.</p>
                                            <details className="mt-1">
                                                <summary className="cursor-pointer font-medium">Detalle técnico</summary>
                                                <p className="mt-1 break-words font-mono">{syncStatus.last_error}</p>
                                            </details>
                                        </div>
                                    )}
                                    {(syncStatus.blocked_count ?? 0) > 0 && (
                                        <p className="rounded-md bg-warn-bg px-3 py-2 text-small text-warn-text">
                                            {syncStatus.blocked_count === 1
                                                ? '1 dato no se envió a la nube'
                                                : `${syncStatus.blocked_count} datos no se enviaron a la nube`}
                                            {' '}porque no tienes permiso sobre su granja. Se conservan en este equipo y no se vuelven a intentar.
                                        </p>
                                    )}
                                </dl>
                            )}

                            {/* Formulario de credenciales */}
                            {showCloudForm && (
                                <form onSubmit={handleSaveCloud} noValidate className="space-y-4 rounded-lg border border-line bg-canvas p-4">
                                    <h3 className="text-h3">Credenciales de la nube</h3>
                                    <TextField
                                        label="Dirección de la nube"
                                        required
                                        autoFocus
                                        type="url"
                                        placeholder="https://sheepcare.cnta.es"
                                        value={cloudUrl}
                                        error={errores.url}
                                        onChange={e => { setCloudUrl(e.target.value); setErrores(x => ({ ...x, url: undefined })); }}
                                    />
                                    <TextField
                                        label="Correo de la cuenta"
                                        required
                                        type="email"
                                        autoComplete="username"
                                        value={cloudEmail}
                                        error={errores.email}
                                        onChange={e => { setCloudEmail(e.target.value); setErrores(x => ({ ...x, email: undefined })); }}
                                    />
                                    <TextField
                                        label="Contraseña"
                                        required
                                        type="password"
                                        autoComplete="current-password"
                                        value={cloudPassword}
                                        error={errores.password}
                                        onChange={e => { setCloudPassword(e.target.value); setErrores(x => ({ ...x, password: undefined })); }}
                                    />
                                    {errorServidor && (
                                        <p role="alert" className="rounded-md bg-danger-bg px-3 py-2.5 text-small text-danger-text">{errorServidor}</p>
                                    )}
                                    <div className="flex gap-2">
                                        <Button type="submit" variant="primary" loading={cloudSaving}>
                                            {cloudSaving ? 'Probando…' : 'Guardar y probar'}
                                        </Button>
                                        <Button onClick={cerrarFormulario} disabled={cloudSaving}>Cancelar</Button>
                                    </div>
                                </form>
                            )}

                            {/* Acciones */}
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant={showCloudForm ? 'secondary' : 'primary'}
                                    loading={syncing}
                                    icon={<ArrowsClockwise size={16} aria-hidden="true" />}
                                    onClick={handleSync}
                                >
                                    {syncing ? 'Sincronizando…' : 'Sincronizar ahora'}
                                </Button>
                                {!showCloudForm && (
                                    <Button icon={<PlugsConnected size={16} aria-hidden="true" />} onClick={abrirFormulario}>
                                        {configurada ? 'Cambiar credenciales' : 'Configurar la nube'}
                                    </Button>
                                )}
                                {configurada && !showCloudForm && (
                                    <Button variant="danger" icon={<LinkBreak size={16} aria-hidden="true" />} onClick={() => setConfirmarDesconexion(true)}>
                                        Desconectar
                                    </Button>
                                )}
                            </div>

                            <p className="flex items-start gap-2 border-t border-line pt-4 text-small text-ink-3">
                                <Timer size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                                Cuando hay conexión con la nube se sincroniza solo cada 15 minutos. Necesitas una cuenta en SheepCare Cloud para usar esta función.
                            </p>
                        </div>
                    )}
                </Card>

                <WeatherKeyCard />
            </div>

            <ConfirmDialog
                open={confirmarDesconexion}
                title="¿Desconectar de la nube?"
                confirmLabel="Desconectar"
                loading={desconectando}
                onConfirm={handleClearCloud}
                onCancel={() => { if (!desconectando) setConfirmarDesconexion(false); }}
            >
                Se eliminarán las credenciales guardadas y dejará de sincronizarse. Tus datos locales no se borran.
            </ConfirmDialog>
        </>
    );
}
