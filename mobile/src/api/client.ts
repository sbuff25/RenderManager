/**
 * Wain API Client
 *
 * Connects to the Wain server REST API with Bearer token auth.
 */

import type {
  ServerStatus,
  JobsResponse,
  WorkersResponse,
} from './types';

export class WainApiClient {
  private baseUrl: string;
  private token: string;

  constructor(serverUrl: string, token: string) {
    this.baseUrl = serverUrl.replace(/\/+$/, '');
    this.token = token;
  }

  setServer(url: string) {
    this.baseUrl = url.replace(/\/+$/, '');
  }

  setToken(token: string) {
    this.token = token;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: Record<string, any>,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (body) {
      headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    try {
      const resp = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || `HTTP ${resp.status}`);
      }

      return data as T;
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Public health check (no auth required) */
  async getStatus(): Promise<ServerStatus> {
    return this.request<ServerStatus>('GET', '/api/status');
  }

  /** Get all jobs */
  async getJobs(status?: string): Promise<JobsResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}&limit=200` : '?limit=200';
    return this.request<JobsResponse>('GET', `/api/jobs${qs}`);
  }

  /** Get all workers */
  async getWorkers(): Promise<WorkersResponse> {
    return this.request<WorkersResponse>('GET', '/api/workers');
  }

  /** Cancel / pause a job */
  async cancelJob(jobId: string): Promise<void> {
    await this.request('POST', `/api/jobs/${jobId}/cancel`);
  }
}

/** Singleton instance — configured from Settings screen */
export const apiClient = new WainApiClient('', '');
