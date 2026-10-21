import { NavLink } from 'react-router-dom';
import {
    SquaresFour, Barn, UploadSimple, ClockCounterClockwise, PawPrint, CloudSun,
    CalendarBlank, GearSix, Moon, Sun, ArrowUpRight,
} from '@phosphor-icons/react';
import type { Icon } from '@phosphor-icons/react';
import type { Tema } from '../lib/theme';

interface Item {
    to?: string;
    href?: string;
    icon: Icon;
    label: string;
}

const FC_URL = 'http://localhost:8002/';

// La versión la pone el script del instalador (VITE_APP_VERSION); en desarrollo no existe.
const VERSION = import.meta.env.VITE_APP_VERSION as string | undefined;

const GRUPOS: { titulo: string; items: Item[] }[] = [
    {
        titulo: 'Análisis',
        items: [
            { to: '/', icon: SquaresFour, label: 'Panel' },
            { to: '/upload', icon: UploadSimple, label: 'Subir datos' },
            { to: '/history', icon: ClockCounterClockwise, label: 'Historial' },
            { to: '/weather', icon: CloudSun, label: 'Tiempo' },
        ],
    },
    {
        titulo: 'Gestión',
        items: [
            { to: '/farms', icon: Barn, label: 'Granjas' },
            { to: '/animals', icon: PawPrint, label: 'Animales' },
            { href: FC_URL, icon: CalendarBlank, label: 'Calendario' },
        ],
    },
    { titulo: 'Sistema', items: [{ to: '/settings', icon: GearSix, label: 'Ajustes' }] },
];

const ENLACE =
    'group relative flex items-center gap-3 rounded-control px-3 py-2.5 text-body max-lg:justify-center text-side-ink-2 ' +
    'transition-[background-color,color] duration-200 ease-snap hover:bg-side-hover hover:text-side-ink';

export default function Sidebar({ tema, onAlternarTema }: { tema: Tema; onAlternarTema: () => void }) {
    return (
        <aside className="flex h-dvh w-[72px] min-w-[72px] flex-col bg-side text-side-ink lg:w-[264px] lg:min-w-[264px]">
            {/* Marca */}
            <div className="border-b border-side-line px-5 pb-5 pt-6 max-lg:px-2 max-lg:pb-4">
                <div className="flex items-center gap-3 max-lg:justify-center">
                    <img src="/sheepcare.svg" alt="" width={32} height={32} className="size-8" />
                    <p className="font-display text-h3 font-semibold tracking-tight max-lg:sr-only">
                        Sheep<span className="text-brand-500">Care</span>
                    </p>
                </div>
                <p className="mt-3 text-small text-side-ink-2 max-lg:hidden">Detección inteligente en ovino</p>
            </div>

            {/* Navegación */}
            <nav aria-label="Principal" className="flex-1 overflow-y-auto px-3 py-4 max-lg:px-2">
                {GRUPOS.map(grupo => (
                    <div key={grupo.titulo} className="mb-5 last:mb-0">
                        <p className="mb-1.5 px-3 text-micro font-medium uppercase tracking-[0.1em] text-side-ink-2 max-lg:sr-only">
                            {grupo.titulo}
                        </p>
                        <div aria-hidden="true" className="mx-3 mb-2 hidden border-t border-side-line max-lg:block" />
                        <ul className="space-y-0.5">
                            {grupo.items.map(item => {
                                const Icono = item.icon;
                                return (
                                    <li key={item.label}>
                                        {item.href ? (
                                            // Farm Calendar vive en otra aplicación: se abre aparte.
                                            <a href={item.href} target="_blank" rel="noopener noreferrer" title={item.label} className={ENLACE}>
                                                <Icono size={20} aria-hidden="true" />
                                                <span className="flex-1 max-lg:sr-only">{item.label}</span>
                                                <ArrowUpRight size={14} aria-hidden="true" className="opacity-60 max-lg:hidden" />
                                                <span className="sr-only">(se abre en una pestaña nueva)</span>
                                            </a>
                                        ) : (
                                            <NavLink
                                                to={item.to!}
                                                title={item.label}
                                                end={item.to === '/'}
                                                className={({ isActive }) =>
                                                    ENLACE + (isActive ? ' bg-side-hover text-side-ink' : '')
                                                }
                                            >
                                                {({ isActive }) => (
                                                    <>
                                                        {/* Indicador del elemento activo: lima, reservado a estados activos */}
                                                        <span
                                                            aria-hidden="true"
                                                            className={
                                                                'absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-500 ' +
                                                                'transition-opacity duration-200 ease-snap ' +
                                                                (isActive ? 'opacity-100' : 'opacity-0')
                                                            }
                                                        />
                                                        <Icono size={20} weight={isActive ? 'fill' : 'regular'} aria-hidden="true" />
                                                        <span className="max-lg:sr-only">{item.label}</span>
                                                    </>
                                                )}
                                            </NavLink>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                ))}
            </nav>

            {/* Financiadores, versión y tema */}
            <div className="border-t border-side-line px-4 pb-4 pt-4 max-lg:px-2">
                <p className="mb-2 text-center max-lg:hidden text-micro uppercase tracking-[0.1em] text-side-ink-2">Con el apoyo de</p>
                <div className="grid grid-cols-2 max-lg:hidden gap-1.5 rounded-lg bg-white p-2">
                    <img src="/logos/Logotipo-CNTA.png" alt="CNTA" className="h-7 w-full object-contain" />
                    <img src="/logos/genovis.png" alt="Genovis" className="h-7 w-full object-contain" />
                    <img src="/logos/open-agri.png" alt="OpenAgri" className="h-7 w-full object-contain" />
                    <img src="/logos/UE.png" alt="Unión Europea" className="h-7 w-full object-contain" />
                </div>

                <div className="mt-3 flex items-center gap-1 max-lg:mt-0 max-lg:flex-col">
                    <p className="flex-1 px-3 text-micro text-side-ink-2 max-lg:hidden">{VERSION ? `v${VERSION}` : 'desarrollo'}</p>
                    <button
                        type="button"
                        onClick={onAlternarTema}
                        aria-pressed={tema === 'dark'}
                        aria-label={tema === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
                        title={tema === 'dark' ? 'Modo claro' : 'Modo oscuro'}
                        className="inline-flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-control text-side-ink-2 transition-[background-color,color,transform] duration-200 ease-snap hover:bg-side-hover hover:text-side-ink active:scale-95"
                    >
                        {tema === 'dark' ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
                    </button>
                </div>
            </div>
        </aside>
    );
}
