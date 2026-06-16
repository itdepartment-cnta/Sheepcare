import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './views/Dashboard';
import FarmsView from './views/Farms';
import UploadView from './views/UploadView';
import HistoryView from './views/History';
import AnimalsView from './views/Animals';
import CalendarView from './views/Calendar';
import SettingsView from './views/Settings';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/farms" element={<FarmsView />} />
        <Route path="/upload" element={<UploadView />} />
        <Route path="/history" element={<HistoryView />} />
        <Route path="/animals" element={<AnimalsView />} />
        <Route path="/calendar" element={<CalendarView />} />
        <Route path="/settings" element={<SettingsView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default App
