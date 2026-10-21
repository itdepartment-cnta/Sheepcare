import { lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';

// Cada pantalla se carga cuando se visita (la guía de CNTA pide dividir por ruta
// y no pasar de 200 KB de JS inicial).
const Dashboard = lazy(() => import('./views/Dashboard'));
const FarmsView = lazy(() => import('./views/Farms'));
const UploadView = lazy(() => import('./views/UploadView'));
const HistoryView = lazy(() => import('./views/History'));
const AnimalsView = lazy(() => import('./views/Animals'));
const WeatherView = lazy(() => import('./views/Weather'));
const SettingsView = lazy(() => import('./views/Settings'));

function App() {
    return (
        <Routes>
            {/* Pantallas con la barra lateral. El diseño se monta una sola vez. */}
            <Route element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="farms" element={<FarmsView />} />
                <Route path="upload" element={<UploadView />} />
                <Route path="history" element={<HistoryView />} />
                <Route path="animals" element={<AnimalsView />} />
                <Route path="weather" element={<WeatherView />} />
                <Route path="settings" element={<SettingsView />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}

export default App
