// API Service for Archgen Text-to-CAD Backend
import { API_BASE_URL, WS_BASE_URL } from '../config';

// ==================== TYPE DEFINITIONS ====================

export interface CADGenerationRequest {
    prompt: string;
    session_id?: string;
    new_session?: boolean;
    model_name?: string;
    max_iterations?: number;
    min_quality_score?: number;
    temperature?: number;
    timeout?: number;
}

export interface CADGenerationResponse {
    session_id: string;
    model_id?: string;
    success: boolean;
    script: string;
    final_score: number;
    iterations: number;
    message: string;
    validation_results: Record<string, Record<string, unknown>>;
    generation_time_seconds: number;
    prompt_count: number;
    error_summary?: string;
    svg_path?: string;
}

export interface ConversationMessage {
    role: string;
    content: string;
    timestamp: string;
    metadata: Record<string, unknown>;
}

export interface ConversationHistory {
    session_id: string;
    messages: ConversationMessage[];
    total_messages: number;
    created_at: string;
    last_used: string;
}

export type GenerationStage =
    | 'queued'
    | 'validating_prompt'
    | 'retrieving_examples'
    | 'generating_script'
    | 'validating_syntax'
    | 'executing_engine'
    | 'validating_geometry'
    | 'refining'
    | 'exporting_model'
    | 'completed'
    | 'failed';

export interface ProgressUpdate {
    stage: GenerationStage;
    progress: number;  // 0.0 to 1.0
    message: string;
    iteration?: number;
    max_iterations?: number;
    details?: Record<string, unknown>;
}

export class AuthError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AuthError';
    }
}

// ==================== API FUNCTIONS ====================

export async function login(username: string, password: string) {
    const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

/**
 * Generate a CAD model from a text prompt
 */
export async function generateCAD(request: CADGenerationRequest): Promise<CADGenerationResponse> {
    const token = localStorage.getItem('archgen_token');
    
    const response = await fetch(`${API_BASE_URL}/generate-cad`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        if (response.status === 401 || response.status === 403) {
            throw new AuthError(error.detail || `HTTP ${response.status}`);
        }
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

export async function getCloudSessions(): Promise<string> {
    const token = localStorage.getItem('archgen_token');
    const response = await fetch(`${API_BASE_URL}/user/sessions`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
    });
    if (!response.ok) throw new Error('Failed to fetch cloud sessions');
    const data = await response.json();
    return data.sessions_json;
}

export async function setCloudSessions(sessionsJson: string): Promise<void> {
    const token = localStorage.getItem('archgen_token');
    await fetch(`${API_BASE_URL}/user/sessions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ sessions_json: sessionsJson })
    });
}

/**
 * Get conversation history for a session
 */
export async function getConversation(sessionId: string): Promise<ConversationHistory> {
    const response = await fetch(`${API_BASE_URL}/conversation/${sessionId}`);

    if (!response.ok) {
        throw new Error(`Failed to fetch conversation: ${response.status}`);
    }

    return response.json();
}

/**
 * Clear conversation history for a session
 */
export async function clearConversation(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/conversation/${sessionId}`, {
        method: 'DELETE',
    });

    if (!response.ok) {
        throw new Error(`Failed to clear conversation: ${response.status}`);
    }
}

/**
 * Check backend health status
 */
export async function healthCheck(): Promise<{ status: string; initialized: boolean }> {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
}

// ==================== WEBSOCKET CONNECTION ====================

export type ProgressCallback = (update: ProgressUpdate) => void;
export type ErrorCallback = (error: Error) => void;
export type CloseCallback = () => void;

export class CADWebSocket {
    private ws: WebSocket | null = null;
    private sessionId: string;
    private onProgress: ProgressCallback;
    private onError: ErrorCallback;
    private onClose: CloseCallback;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 3;

    constructor(
        sessionId: string,
        onProgress: ProgressCallback,
        onError: ErrorCallback,
        onClose: CloseCallback
    ) {
        this.sessionId = sessionId;
        this.onProgress = onProgress;
        this.onError = onError;
        this.onClose = onClose;
    }

    connect(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            return;
        }

        this.ws = new WebSocket(`${WS_BASE_URL}/ws/${this.sessionId}`);

        this.ws.onopen = () => {
            console.log(`WebSocket connected for session: ${this.sessionId}`);
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            try {
                const update: ProgressUpdate = JSON.parse(event.data);
                this.onProgress(update);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        this.ws.onerror = (event) => {
            console.error('WebSocket error:', event);
            this.onError(new Error('WebSocket connection error'));
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                setTimeout(() => this.connect(), 1000 * this.reconnectAttempts);
            } else {
                this.onClose();
            }
        };
    }

    disconnect(): void {
        this.maxReconnectAttempts = 0; // prevent onclose from reconnecting
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// ==================== MODEL IMAGE URLS ====================

/**
 * Get URL for rendered model image
 */
export function getModelImageUrl(sessionId: string, view: 'isometric' | 'front' | 'top' | 'left' | 'right' | 'back' = 'isometric'): string {
    return `${API_BASE_URL}/models/${sessionId}/${view}.png`;
}

/**
 * Get all available model view URLs
 */
export function getAllModelViewUrls(sessionId: string): Record<string, string> {
    const views = ['isometric', 'front', 'top', 'left', 'right', 'back'] as const;
    return Object.fromEntries(views.map(v => [v, getModelImageUrl(sessionId, v)]));
}

// Submit feedback for a model
export async function submitFeedback(
  modelId: string,
  data: { rating: number; comment?: string; useful?: boolean }
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/feedback/${modelId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`Feedback failed: ${response.statusText}`);
  return response.json();
}
