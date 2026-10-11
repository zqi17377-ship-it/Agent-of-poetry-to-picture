export type Job = {id: string; artwork_id: string; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'needs_review'; stage: string; error: string | null; call_count: number; elapsed_ms: number; provider_request_id: string | null; usage: Record<string, unknown>};
export type Version = {id: string; parent_version_id: string | null; revision_text: string; operation: string; created_at: string; model: string; text_mode: string; brief: {rationale: string; additions: string[]; anchors?: {source_quote: string; visual_element: string; connection: string}[]}; interpretation: {emotions: string[]; imagery: {image: string; source_quote: string}[]; ambiguities: string[]; relations?: string[]}; quality_report: {flags: string[]; rationale: string}};
export type Artwork = {id: string; text: string; title: string; author: string; aspect_ratio: string; created_at: string; versions: Version[]; jobs: Job[]};
export type HistoryItem = {id: string; title: string; author: string; created_at: string; latest_version: Version | null; status: string};
export type Config = {image_provider: string; text_provider: string; supports_edit: boolean; free_demo: boolean; aspect_ratios: string[]};

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, body === undefined ? undefined : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === 'string' ? detail : response.status === 422 ? '请检查文字长度和填写内容。' : '连接暂时中断，请确认应用正在运行后重试。');
  }
  return response.json();
}

export const imageUrl = (id: string, download = false) => `/api/versions/${id}/image${download ? '?download=true' : ''}`;
