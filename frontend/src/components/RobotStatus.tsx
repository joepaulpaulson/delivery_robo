'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Battery, 
  Wifi, 
  Heart, 
  Video
} from 'lucide-react';
import { apiClient } from '@/src/lib/api';

export function RobotStatus() {
  // Demo fallback data - shows even when API fails
  const [battery, setBattery] = useState(85);
  const [heartRate, setHeartRate] = useState(72);
  const [isAlert, setIsAlert] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [status, vitals] = await Promise.all([
          apiClient.getRobotStatus(),
          apiClient.getCurrentVitals(),
        ]);
        if (status.battery_level > 0) setBattery(status.battery_level);
        if (vitals.heart_rate > 0) setHeartRate(vitals.heart_rate);
        setIsAlert(vitals.alert || false);
      } catch (error) {
        console.log('Using demo data');
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getBatteryColor = (level: number) => {
    if (level > 60) return 'text-emerald-400';
    if (level > 30) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Camera Feed Panel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-xl overflow-hidden shadow-xl"
      >
        {/* Header */}
        <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Video className="w-5 h-5 text-blue-400" />
            <h3 className="font-semibold text-slate-200 text-sm">Robot Vision</h3>
          </div>
          <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-red-500/20 border border-red-500/50">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs font-bold text-red-400">LIVE</span>
          </div>
        </div>

        {/* Camera Feed */}
        <div className="relative aspect-video bg-slate-950">
          <img
            src="http://localhost:5000/video_feed"
            alt="Robot Camera Feed"
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="640" height="480"%3E%3Crect fill="%230f172a" width="640" height="480"/%3E%3Ctext fill="%2364748b" font-family="system-ui" font-size="24" font-weight="600" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3ECamera Feed Offline%3C/text%3E%3Ctext fill="%23475569" font-family="system-ui" font-size="14" x="50%25" y="60%25" text-anchor="middle" dominant-baseline="middle"%3ECheck Flask backend connection%3C/text%3E%3C/svg%3E';
            }}
          />
        </div>
      </motion.div>

      {/* System Vitals Panel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-xl p-4 shadow-xl"
      >
        <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          System Vitals
        </h3>
        
        <div className="space-y-3">
          {/* Battery */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/60 border border-slate-700/30">
            <div className="flex items-center gap-3">
              <Battery className={`w-5 h-5 ${getBatteryColor(battery)}`} />
              <span className="text-sm font-medium text-slate-300">Battery</span>
            </div>
            <span className={`text-2xl font-bold ${getBatteryColor(battery)}`}>
              {battery}%
            </span>
          </div>

          {/* WiFi Signal */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/60 border border-slate-700/30">
            <div className="flex items-center gap-3">
              <Wifi className="w-5 h-5 text-blue-400" />
              <span className="text-sm font-medium text-slate-300">Wi-Fi Signal</span>
            </div>
            <div className="flex gap-1 items-end">
              {[1, 2, 3, 4].map((bar) => (
                <div
                  key={bar}
                  className={`w-1.5 rounded-full transition-all ${
                    bar <= 3 ? 'bg-blue-400 h-4' : 'bg-slate-600 h-5'
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Heart Rate */}
          <div className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
            isAlert 
              ? 'bg-red-500/20 border-red-500/50 animate-pulse-glow' 
              : 'bg-slate-800/60 border-slate-700/30'
          }`}>
            <div className="flex items-center gap-3">
              <Heart className={`w-5 h-5 ${isAlert ? 'text-red-400' : 'text-emerald-400'}`} />
              <span className="text-sm font-medium text-slate-300">Heart Rate</span>
            </div>
            <span className={`text-2xl font-bold ${isAlert ? 'text-red-400' : 'text-emerald-400'}`}>
              {heartRate} BPM
            </span>
          </div>
        </div>
      </motion.div>

    </div>
  );
}
