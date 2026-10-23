// En el instalador el calendario va en otro puerto (VITE_FC_URL lo fija build-release.ps1);
// en desarrollo y con Docker sigue siendo el 8002.
export const FC_URL = (import.meta.env.VITE_FC_URL as string | undefined) ?? 'http://localhost:8002/';
