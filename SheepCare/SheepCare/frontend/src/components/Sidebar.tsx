import { NavLink, useLocation } from 'react-router-dom';
import { Building2, Upload, LayoutDashboard, History, PawPrint, Calendar, Settings } from 'lucide-react';

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Panel' },
    { to: '/farms', icon: Building2, label: 'Granjas' },
    { to: '/upload', icon: Upload, label: 'Subir' },
    { to: '/history', icon: History, label: 'Historial' },
    { to: '/animals', icon: PawPrint, label: 'Animales' },
    { to: '/calendar', icon: Calendar, label: 'Calendario' },
    { to: '/settings', icon: Settings, label: 'Ajustes' },
];

export default function Sidebar() {
    const location = useLocation();

    return (
        <aside className="w-[264px] min-w-[264px] bg-grafito flex flex-col h-screen">
            <div className="px-5 py-6 border-b border-white/10">
                <h1 className="text-acido text-xl font-bold tracking-tight">
                    SHEEP<span className="italic">CARE</span>
                </h1>
                <p className="text-gray-400 text-xs mt-1">Sistema de Detección Inteligente</p>
            </div>

            <nav className="flex-1 py-4">
                {navItems.map((item) => {
                    const isActive = item.to === '/'
                        ? location.pathname === '/'
                        : location.pathname.startsWith(item.to);
                    const Icon = item.icon;
                    const isExternal = item.to === '/calendar';
                    if (isExternal) {
                        return (
                            <a
                                key={item.to}
                                href="http://localhost:8002/"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 px-5 py-3 text-sm transition-all text-gray-400 hover:text-white hover:bg-white/5 border-l-[3px] border-transparent"
                            >
                                <Icon size={18} />
                                <span>{item.label}</span>
                            </a>
                        );
                    }
                    return (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={`flex items-center gap-3 px-5 py-3 text-sm transition-all ${isActive
                                ? 'bg-acido/10 text-acido border-l-[3px] border-acido'
                                : 'text-gray-400 hover:text-white hover:bg-white/5 border-l-[3px] border-transparent'
                                }`}
                        >
                            <Icon size={18} />
                            <span>{item.label}</span>
                        </NavLink>
                    );
                })}
            </nav>

            <div className="px-4 pt-3 pb-4 border-t border-white/10">
                <p className="text-gray-500 text-[9px] uppercase tracking-widest mb-2 text-center">Con el apoyo de</p>
                <div className="bg-white/95 rounded-lg p-2 flex flex-col gap-2">
                    <img src="/logos/Logotipo-CNTA.png" alt="CNTA" className="h-8 w-full object-contain" />
                    <img src="/logos/genovis.png" alt="Genovis" className="h-8 w-full object-contain" />
                    <img src="/logos/open-agri.png" alt="OpenAgri" className="h-8 w-full object-contain" />
                    <img src="/logos/UE.png" alt="Unión Europea" className="h-8 w-full object-contain" />
                </div>
                <p className="text-gray-500 text-[10px] mt-2">v1.0.0</p>
            </div>
        </aside>
    );
}
