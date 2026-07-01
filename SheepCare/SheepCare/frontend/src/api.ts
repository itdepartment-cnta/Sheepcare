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
}

export const farmsApi = {
    list: () => api.get<Farm[]>('/farms/').then(r => r.data),
    get: (id: number) => api.get<Farm>(`/farms/${id}`).then(r => r.data),
    create: (name: string, location: string) =>
        api.post<Farm>('/farms/', { name, location }).then(r => r.data),
    update: (id: number, name: string, location: string) =>
        api.put<Farm>(`/farms/${id}`, { name, location }).then(r => r.data),
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

export const settingsApi = {
    system: () => api.get<SystemInfo>('/settings/system').then(r => r.data),
    syncStatus: () => api.get<SyncStatus>('/settings/sync/status').then(r => r.data),
    checkConnectivity: () => api.get<ConnectivityStatus>('/settings/sync/connectivity').then(r => r.data),
    syncNow: () => api.post<{ success: boolean; synced_count: number; error?: string }>('/settings/sync/now').then(r => r.data),
    cloudConfig: () => api.get<CloudConfig>('/settings/cloud/config').then(r => r.data),
    saveCloudConfig: (cloud_url: string, email: string, password: string) =>
        api.post<CloudConfig>('/settings/cloud/config', { cloud_url, email, password }).then(r => r.data),
    clearCloudConfig: () => api.delete('/settings/cloud/config').then(r => r.data),
};

export default api;
