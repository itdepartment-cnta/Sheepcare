import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
});

// ── Farms ────────────────────────────────────────────
export interface Farm {
    id: number;
    name: string;
    location: string;
    created_at: string;
    // Posición real de la granja (para el servicio meteorológico).
    latitude?: number | null;
    longitude?: number | null;
    // Relación con la granja según la nube. «shared»: se ve y se le suben datos, pero
    // no se edita ni se borra. Ausente en una granja solo local.
    access?: 'owner' | 'shared' | 'admin' | null;
}

export interface FarmCoordinates {
    latitude: number | null;
    longitude: number | null;
}

export const farmsApi = {
    list: () => api.get<Farm[]>('/farms/').then(r => r.data),
    get: (id: number) => api.get<Farm>(`/farms/${id}`).then(r => r.data),
    create: (name: string, location: string, coords?: FarmCoordinates) =>
        api.post<Farm>('/farms/', { name, location, ...coords }).then(r => r.data),
    // Con `coords` omitido el backend no toca las coordenadas; con
    // {latitude: null, longitude: null} las borra.
    update: (id: number, name: string, location: string, coords?: FarmCoordinates) =>
        api.put<Farm>(`/farms/${id}`, { name, location, ...coords }).then(r => r.data),
    delete: (id: number) => api.delete(`/farms/${id}`),
};

// ── Uploads ──────────────────────────────────────────
export interface AnimalResult {
    animal_id: string;
    result: string;
    confidence: number;
    probability: number;
}

export interface UploadResult {
    upload_id: number;
    farm_id: number;
    filename: string;
    result_file: string;
    total_animals: number;
    celo_count: number;
    no_celo_count: number;
    results: AnimalResult[];
    upload_date: string | null;
    processed_at: string | null;
    processing_time_ms: number;
}

export interface UploadSummary {
    id: number;
    farm_id: number;
    farm_name: string;
    filename: string;
    upload_date: string;
    processed_at: string | null;
    total_animals: number;
    celo_count: number;
    no_celo_count: number;
}

export const uploadsApi = {
    upload: (file: File, farmId: number) => {
        const form = new FormData();
        form.append('file', file);
        form.append('farm_id', String(farmId));
        return api.post<UploadResult>('/uploads/', form).then(r => r.data);
    },
    list: (farmId?: number) =>
        api.get<UploadSummary[]>('/uploads/', { params: { farm_id: farmId } }).then(r => r.data),
    get: (id: number) => api.get(`/uploads/${id}`).then(r => r.data),
};

// ── Milk Quality ─────────────────────────────────────
export interface MilkQualitySampleResult {
    animal_id: string;
    result: string;
}

export interface MilkQualityUploadResult {
    upload_id: number;
    farm_id: number;
    filename: string;
    result_file: string;
    total_samples: number;
    lower_count: number;
    upper_count: number;
    results: MilkQualitySampleResult[];
    upload_date: string | null;
    processed_at: string | null;
    processing_time_ms: number;
}

export interface MilkQualityUploadSummary {
    id: number;
    farm_id: number;
    farm_name: string;
    filename: string;
    upload_date: string;
    processed_at: string | null;
    total_samples: number;
    lower_count: number;
    upper_count: number;
}

export interface MilkQualityResult {
    id: number;
    sample_id: string;
    // Obsoleto: la muestra ya no es un animal. Usa animal_tag (= sample_id).
    animal_id?: number | null;
    upload_id: number;
    result: string;
    created_at: string;
    animal_tag: string;
    animal_name: string;
    filename: string;
    upload_date: string;
    farm_name: string;
}

export const milkQualityApi = {
    upload: (file: File, farmId: number) => {
        const form = new FormData();
        form.append('file', file);
        form.append('farm_id', String(farmId));
        return api.post<MilkQualityUploadResult>('/milk-quality/uploads/', form).then(r => r.data);
    },
    list: (farmId?: number) =>
        api.get<MilkQualityUploadSummary[]>('/milk-quality/uploads/', { params: { farm_id: farmId } }).then(r => r.data),
    get: (id: number) => api.get(`/milk-quality/uploads/${id}`).then(r => r.data),
    results: (params?: { farm_id?: number; upload_id?: number }) =>
        api.get<MilkQualityResult[]>('/milk-quality/results/', { params }).then(r => r.data),
};

// ── Results ──────────────────────────────────────────
export interface DetectionResult {
    id: number;
    animal_id: number;
    upload_id: number;
    result: string;
    confidence: number;
    probability: number;
    created_at: string;
    animal_tag: string;
    animal_name: string;
    filename: string;
    upload_date: string;
    farm_name: string;
}

export const resultsApi = {
    list: (params?: { farm_id?: number; upload_id?: number; result?: string }) =>
        api.get<DetectionResult[]>('/results/', { params }).then(r => r.data),
    latest: (farmId?: number) =>
        api.get<DetectionResult | null>('/results/latest', { params: { farm_id: farmId } }).then(r => r.data),
};

// ── Animals ──────────────────────────────────────────
export interface Animal {
    id: number;
    farm_id: number;
    external_tag: string;
    name: string;
    created_at: string;
}

export const animalsApi = {
    list: (farmId?: number) =>
        api.get<Animal[]>('/animals/', { params: { farm_id: farmId } }).then(r => r.data),
};

// ── Settings ─────────────────────────────────────────
export interface SystemInfo {
    db_path: string;
    project_root: string;
    models_path: string;
    farmcalendar_url: string;
}

export interface SyncStatus {
    last_sync: string | null;
    last_status: string | null;
    last_error: string | null;
    // Datos que la nube rechazó por falta de permiso y que ya no se reenvían.
    blocked_count?: number;
}

export interface CloudConfig {
    configured: boolean;
    email: string;
    cloud_url: string;
    client_id: number;
}

export interface ConnectivityStatus {
    reachable: boolean;
    cloud_url: string;
    checked_at: string;
}

export interface WeatherConfig {
    configured: boolean;
    key_hint: string;
}

export const settingsApi = {
    system: () => api.get<SystemInfo>('/settings/system').then(r => r.data),
    syncStatus: () => api.get<SyncStatus>('/settings/sync/status').then(r => r.data),
    checkConnectivity: () => api.get<ConnectivityStatus>('/settings/sync/connectivity').then(r => r.data),
    syncNow: () => api.post<{ success: boolean; synced_count: number; error?: string }>('/settings/sync/now').then(r => r.data),
    cloudConfig: () => api.get<CloudConfig>('/settings/cloud/config').then(r => r.data),
    saveCloudConfig: (cloud_url: string, email: string, password: string) =>
        api.post<CloudConfig>('/settings/cloud/config', { cloud_url, email, password }).then(r => r.data),
    clearCloudConfig: () => api.delete('/settings/cloud/config').then(r => r.data),
    weatherConfig: () => api.get<WeatherConfig>('/settings/weather').then(r => r.data),
    saveWeatherKey: (api_key: string) =>
        api.put<WeatherConfig>('/settings/weather', { api_key }).then(r => r.data),
    clearWeatherKey: () => api.delete<WeatherConfig>('/settings/weather').then(r => r.data),
};

// ── Tiempo y estrés térmico (OpenAgri Weather Service) ─────────────────
export type NivelTHI = 'sin_estres' | 'leve' | 'moderado' | 'severo' | 'critico';

export interface THIActual {
    farm_id: number;
    latitude: number;
    longitude: number;
    thi: number;
    level: NivelTHI;
}

// Un instante de la previsión (cada 3 h). Las marcas de tiempo llegan en UTC
// con «Z». thi y level son null si falta temperatura o humedad.
export interface PuntoPrevision {
    timestamp: string;
    temperature: number | null;
    humidity: number | null;
    wind_speed: number | null;
    rain_probability: number | null;
    rain_mm_3h: number | null;
    thi: number | null;
    level: NivelTHI | null;
}

export interface Prevision {
    farm_id: number;
    latitude: number;
    longitude: number;
    forecast: PuntoPrevision[];
}

// Las coordenadas salen siempre de la granja en el servidor, no se envían.
export const weatherApi = {
    thi: (farmId: number) =>
        api.get<THIActual>(`/weather/farms/${farmId}/thi`).then(r => r.data),
    forecast: (farmId: number) =>
        api.get<Prevision>(`/weather/farms/${farmId}/forecast`).then(r => r.data),
};

// ── Informes en PDF (OpenAgri Reporting Service) ───────────────────────
// Las fechas son opcionales ('AAAA-MM-DD', inclusive). Sin ellas, el informe
// incluye todos los datos de la granja. El PDF puede tardar unos segundos.
export interface InformePdf {
    blob: Blob;
    filename: string;
}

const pdfDeGranja = (tipo: 'estrus-report' | 'milk-quality-report', farmId: number, fromDate?: string, toDate?: string) =>
    api
        .get<Blob>(`/reporting/farms/${farmId}/${tipo}`, {
            params: { from_date: fromDate || undefined, to_date: toDate || undefined, lang: 'es' },
            responseType: 'blob',
            timeout: 60000,
        })
        .then((r): InformePdf => ({
            blob: r.data,
            filename:
                /filename="([^"]+)"/.exec(r.headers['content-disposition'] ?? '')?.[1] ??
                'informe.pdf',
        }));

export const reportsApi = {
    estrusPdf: (farmId: number, fromDate?: string, toDate?: string) =>
        pdfDeGranja('estrus-report', farmId, fromDate, toDate),
    milkQualityPdf: (farmId: number, fromDate?: string, toDate?: string) =>
        pdfDeGranja('milk-quality-report', farmId, fromDate, toDate),
};

export default api;
