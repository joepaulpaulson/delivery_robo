/**
 * API Client for Flask Backend Communication
 */

import { ScheduleItem, RobotStatus, PatientVitals, SystemHealth } from '@/src/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Schedule Endpoints
  async getTodaySchedule(): Promise<ScheduleItem[]> {
    return this.fetchApi<ScheduleItem[]>('/api/schedule/today');
  }

  async completeTask(taskId: number, notes?: string): Promise<{ success: boolean }> {
    return this.fetchApi('/api/schedule/complete', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, notes }),
    });
  }

  // Robot Control Endpoints
  async getRobotStatus(): Promise<RobotStatus> {
    return this.fetchApi<RobotStatus>('/api/robot/status');
  }

  // Vitals Endpoints
  async getCurrentVitals(): Promise<PatientVitals> {
    return this.fetchApi<PatientVitals>('/api/vitals/current');
  }

  // System Health
  async getSystemHealth(): Promise<SystemHealth> {
    return this.fetchApi<SystemHealth>('/api/system/health');
  }

  // Emergency
  async triggerEmergency(type: string = 'user_initiated'): Promise<{ success: boolean }> {
    return this.fetchApi('/api/emergency', {
      method: 'POST',
      body: JSON.stringify({ type }),
    });
  }

  // Voice Command
  async processVoiceCommand(text: string): Promise<{ success: boolean; message: string }> {
    return this.fetchApi('/api/voice/process', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }
}

export const apiClient = new ApiClient();
