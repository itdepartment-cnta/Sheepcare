import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowsClockwise, Barn, MapPin, PencilSimple, Plus, TrashSimple } from '@phosphor-icons/react';
import { farmsApi } from '../api';
import type { Farm, FarmCoordinates } from '../api';
import { mensajeDeError } from '../lib/errors';
import { fecha, numero } from '../lib/format';
import {
    avisar, Button, Card, CardHeader, Chip, ConfirmDialog, EmptyState, ErrorState, IconButton, PageHeader,
    Table, TableSkeleton, Td, TextField, Th, Tr,
} from '../components/ui';

const ERROR_COORDENADAS =
    'La latitud (de -90 a 90) y la longitud (de -180 a 180) deben ser números y rellenarse las dos, o dejarse vacías.';

export default function FarmsView() {
    const [farms, setFarms] = useState<Farm[] | null>(null);
    const [errorCarga, setErrorCarga] = useState(false);
    const [intento, setIntento] = useState(0);

    const [showForm, setShowForm] = useState(false);
    const [editing, setEditing] = useState<Farm | null>(null);
    const [name, setName] = useState('');
    const [location, setLocation] = useState('');
    const [latitude, setLatitude] = useState('');
    const [longitude, setLongitude] = useState('');
    const [errorCoords, setErrorCoords] = useState('');
    const [errorNombre, setErrorNombre] = useState('');
    const [errorServidor, setErrorServidor] = useState('');
    const [guardando, setGuardando] = useState(false);

    const [aBorrar, setABorrar] = useState<Farm | null>(null);
    const [borrando, setBorrando] = useState(false);

    useEffect(() => {
        let vigente = true;
        farmsApi.list()
            .then(f => { if (vigente) setFarms(f); })
            .catch(() => { if (vigente) setErrorCarga(true); });
        return () => { vigente = false; };
    }, [intento]);

    const recargar = () => {
        setErrorCarga(false);
        setFarms(null);
        setIntento(n => n + 1);
    };

    const limpiarFormulario = () => {
        setName('');
        setLocation('');
        setLatitude('');
        setLongitude('');
        setErrorCoords('');
        setErrorNombre('');
        setErrorServidor('');
    };

    // Acepta coma decimal ("42,8"). Devuelve null si ambos están vacíos y
    // undefined si hay un valor inválido o falta uno de los dos.
    const parseCoords = (): FarmCoordinates | null | undefined => {
        const lat = latitude.trim().replace(',', '.');
        const lon = longitude.trim().replace(',', '.');
        if (!lat && !lon) return null;
        if (!lat || !lon) return undefined;
        const la = Number(lat);
        const lo = Number(lon);
        if (!Number.isFinite(la) || !Number.isFinite(lo)) return undefined;
        if (la < -90 || la > 90 || lo < -180 || lo > 180) return undefined;
        return { latitude: la, longitude: lo };
    };

    const cerrarFormulario = () => {
        setShowForm(false);
        setEditing(null);
        limpiarFormulario();
    };

    const abrirNueva = () => {
        setEditing(null);
        limpiarFormulario();
        setShowForm(true);
    };

    const abrirEdicion = (f: Farm) => {
        setEditing(f);
        setName(f.name);
        setLocation(f.location);
        setLatitude(f.latitude != null ? String(f.latitude) : '');
        setLongitude(f.longitude != null ? String(f.longitude) : '');
        setErrorCoords('');
        setErrorNombre('');
        setErrorServidor('');
        setShowForm(true);
    };

    const guardar = async (e: FormEvent) => {
        e.preventDefault();
        if (!name.trim()) {
            setErrorNombre('Pon un nombre a la granja.');
            return;
        }
        const parsed = parseCoords();
        if (parsed === undefined) {
            setErrorCoords(ERROR_COORDENADAS);
            return;
        }
        setErrorCoords('');
        setErrorNombre('');
        setErrorServidor('');
        setGuardando(true);
        try {
            if (editing) {
                // Al editar siempre se envían: vacías significa «quitar las coordenadas».
                await farmsApi.update(editing.id, name, location, parsed ?? { latitude: null, longitude: null });
            } else {
                await farmsApi.create(name, location, parsed ?? undefined);
            }
            avisar.ok(editing ? 'Granja actualizada' : 'Granja creada', name.trim());
            cerrarFormulario();
            recargar();
        } catch (err) {
            setErrorServidor(mensajeDeError(err, 'No se pudo guardar la granja. Inténtalo de nuevo.'));
        } finally {
            setGuardando(false);
        }
    };

    const confirmarBorrado = async () => {
        if (!aBorrar) return;
        setBorrando(true);
        try {
            await farmsApi.delete(aBorrar.id);
            avisar.ok('Granja eliminada', aBorrar.name);
            setABorrar(null);
            recargar();
        } catch (err) {
            avisar.error('No se pudo eliminar la granja', mensajeDeError(err, 'Inténtalo de nuevo.'));
        } finally {
            setBorrando(false);
        }
    };

    return (
        <>
            <PageHeader
                eyebrow="Gestión"
                title="Granjas"
                description="Registra y gestiona tus granjas."
                actions={
                    <>
                        <Button icon={<ArrowsClockwise size={16} aria-hidden="true" />} onClick={recargar}>
                            Actualizar
                        </Button>
                        {!showForm && (
                            <Button variant="primary" icon={<Plus size={16} aria-hidden="true" />} onClick={abrirNueva}>
                                Añadir granja
                            </Button>
                        )}
                    </>
                }
            />

            {showForm && (
                <Card className="mb-4" index={0}>
                    <CardHeader
                        title={editing ? `Editar «${editing.name}»` : 'Nueva granja'}
                        icon={editing ? <PencilSimple size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
                    />
                    <form onSubmit={guardar} noValidate className="space-y-5">
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <TextField
                                label="Nombre"
                                required
                                autoFocus
                                value={name}
                                error={errorNombre}
                                onChange={e => { setName(e.target.value); setErrorNombre(''); }}
                            />
                            <TextField
                                label="Ubicación"
                                hint="Opcional. Municipio o zona."
                                value={location}
                                onChange={e => setLocation(e.target.value)}
                            />
                        </div>

                        <div>
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <TextField
                                    label="Latitud"
                                    inputMode="decimal"
                                    invalid={!!errorCoords}
                                    value={latitude}
                                    onChange={e => { setLatitude(e.target.value); setErrorCoords(''); }}
                                />
                                <TextField
                                    label="Longitud"
                                    inputMode="decimal"
                                    invalid={!!errorCoords}
                                    value={longitude}
                                    onChange={e => { setLongitude(e.target.value); setErrorCoords(''); }}
                                />
                            </div>
                            {errorCoords ? (
                                <p role="alert" className="mt-1.5 text-small font-medium text-danger-text">{errorCoords}</p>
                            ) : (
                                <p className="mt-1.5 text-small text-ink-3">
                                    Opcionales. Por ejemplo, 42,8125 y -1,6458. Permiten consultar el tiempo de la granja.
                                </p>
                            )}
                        </div>

                        {errorServidor && (
                            <p role="alert" className="rounded-md bg-danger-bg px-3 py-2.5 text-small text-danger-text">{errorServidor}</p>
                        )}

                        <div className="flex gap-2">
                            <Button type="submit" variant="primary" loading={guardando}>
                                {editing ? 'Guardar cambios' : 'Crear granja'}
                            </Button>
                            <Button onClick={cerrarFormulario} disabled={guardando}>Cancelar</Button>
                        </div>
                    </form>
                </Card>
            )}

            <Card padded={false} index={1}>
                {errorCarga ? (
                    <ErrorState action={<Button onClick={recargar}>Reintentar</Button>}>
                        Revisa que el servicio local esté en marcha e inténtalo de nuevo.
                    </ErrorState>
                ) : farms === null ? (
                    <TableSkeleton rows={4} cols={6} />
                ) : farms.length === 0 ? (
                    <EmptyState
                        icon={<Barn aria-hidden="true" />}
                        title="Aún no hay granjas"
                        action={!showForm && <Button variant="primary" onClick={abrirNueva}>Añadir tu primera granja</Button>}
                    >
                        Crea una granja para empezar a subir datos de celo y de calidad de leche.
                    </EmptyState>
                ) : (
                    <Table caption="Granjas registradas" minWidth="48rem">
                        <thead>
                            <tr>
                                <Th align="right">N.º</Th>
                                <Th>Granja</Th>
                                <Th>Ubicación</Th>
                                <Th>Coordenadas</Th>
                                <Th>Alta</Th>
                                <Th align="right"><span className="sr-only">Acciones</span></Th>
                            </tr>
                        </thead>
                        <tbody>
                            {farms.map(f => (
                                <Tr key={f.id}>
                                    <Td numeric muted>{numero(f.id)}</Td>
                                    <Td strong>
                                        {f.name}
                                        {f.access === 'shared' && <Chip tone="info" className="ml-2">Compartida contigo</Chip>}
                                    </Td>
                                    <Td muted={!f.location}>{f.location || '—'}</Td>
                                    <Td>
                                        {f.latitude != null && f.longitude != null ? (
                                            <span className="inline-flex items-center gap-1.5 tabular text-ink-2">
                                                <MapPin size={14} aria-hidden="true" className="text-brand-700" />
                                                {numero(f.latitude, 4)}, {numero(f.longitude, 4)}
                                            </span>
                                        ) : (
                                            <Chip>Sin coordenadas</Chip>
                                        )}
                                    </Td>
                                    <Td muted>{fecha(f.created_at)}</Td>
                                    <Td>
                                        {/* Una granja compartida se ve y se le suben datos, pero no se edita ni se borra. */}
                                        {f.access !== 'shared' && (
                                            <div className="flex justify-end gap-0.5">
                                                <IconButton label={`Editar ${f.name}`} onClick={() => abrirEdicion(f)}>
                                                    <PencilSimple size={18} aria-hidden="true" />
                                                </IconButton>
                                                <IconButton label={`Eliminar ${f.name}`} tone="danger" onClick={() => setABorrar(f)}>
                                                    <TrashSimple size={18} aria-hidden="true" />
                                                </IconButton>
                                            </div>
                                        )}
                                    </Td>
                                </Tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Card>

            <ConfirmDialog
                open={aBorrar !== null}
                title={aBorrar ? `¿Eliminar «${aBorrar.name}»?` : ''}
                confirmLabel="Eliminar granja"
                loading={borrando}
                onConfirm={confirmarBorrado}
                onCancel={() => { if (!borrando) setABorrar(null); }}
            >
                Se borrarán también sus animales, subidas y resultados. Esta acción no se puede deshacer.
            </ConfirmDialog>
        </>
    );
}
