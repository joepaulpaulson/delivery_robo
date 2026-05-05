/**
 * Type definitions for Medical Robot Dashboard
 */

export interface ScheduleItem {
  id: number;
  time: string; // ISO format: "2026-01-03 14:00"
  task: string;
  status: 'completed' | 'pending' | 'missed';
  notes?: string;
  dosage?: string;
}

export interface RobotStatus {
  battery_level: number;
  location: string;
  is_moving: boolean;
  wifi_signal: number;
  last_update: string;
}

export interface PatientVitals {
  heart_rate: number;
  spo2: number;
  temperature: number;
  timestamp: string;
  alert?: boolean;
}

export interface SystemHealth {
  server: string;
  camera: boolean;
  bluetooth: boolean;
  database: boolean;
  timestamp: string;
}
