"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";

export function AdminSimulationHeader() {
  const [clock, setClock] = useState<string>("Initializing...");
  const [multiplier, setMultiplier] = useState<number>(1);
  const [isOpen, setIsOpen] = useState(false);
  const { language } = useLanguage();
  const copy = language === "vi"
    ? { clock: "Đồng hồ mô phỏng hệ thống", pacing: "Tốc độ", settings: "Cài đặt mô phỏng", speed: "Tốc độ mô phỏng", help: "Điều chỉnh số giờ mô phỏng trôi qua trong mỗi 10 giây thực." }
    : { clock: "System simulation clock", pacing: "Pacing", settings: "Simulation settings", speed: "Simulation speed", help: "Adjusts how many simulated hours pass per 10 real-world seconds." };

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
    const socket = new WebSocket(apiBase.replace(/^http/, "ws") + "/ws/status");
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "TIME_TICK") {
          if (msg.system_clock) {
            const dt = new Date(msg.system_clock);
            setClock(dt.toLocaleString("vi-VN", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false
            }));
          }
          if (msg.time_acceleration_factor !== undefined) {
            setMultiplier(msg.time_acceleration_factor);
          }
        }
      } catch (e) {
        console.error("Error parsing socket msg:", e);
      }
    };
    return () => socket.close();
  }, []);

  const updateMultiplier = async (val: number) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiBase}/api/v1/simulation/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ time_acceleration_factor: val }),
      });
      if (res.ok) {
        setMultiplier(val);
        setIsOpen(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="bg-[#001e3d] text-white px-6 py-4 flex items-center justify-between border-b border-[#002d58]/40 sticky top-0 z-50">
      <div className="flex items-center gap-4">
        <span className="flex h-3 w-3 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#86bb44] opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-[#86bb44]"></span>
        </span>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-300 font-bold">{copy.clock}</div>
          <div className="text-lg font-mono font-bold tracking-widest text-[#86bb44]">{clock}</div>
        </div>
      </div>

      <div className="flex items-center gap-3 relative">
        <div className="bg-[#002d58] border border-white/10 rounded px-2.5 py-1 text-xs font-mono text-slate-200">
          {copy.pacing}: <strong className="text-[#86bb44] font-bold">{multiplier}h/10s</strong>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-2 rounded bg-white/10 hover:bg-white/20 transition-colors border border-white/10 text-white flex items-center justify-center"
          title={copy.settings}
        >
          ⚙️
        </button>

        {isOpen && (
          <div className="absolute right-0 top-12 bg-[#001e3d] border border-white/10 rounded-lg shadow-xl p-4 w-72 z-[999] animate-slide-in">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wide mb-3 border-b border-white/10 pb-1.5">{copy.speed}</h4>
            <div className="grid grid-cols-3 gap-2">
              {[1, 2, 5].map((val) => (
                <button
                  key={val}
                  onClick={() => updateMultiplier(val)}
                  className={`py-1.5 rounded text-xs font-mono font-bold transition-all ${
                    multiplier === val
                      ? "bg-[#86bb44] text-slate-950 shadow-md"
                      : "bg-white/10 hover:bg-white/20 text-slate-200"
                  }`}
                >
                  {val}h/10s
                </button>
              ))}
            </div>
            <div className="mt-3 text-[10px] text-slate-300 italic">
              {copy.help}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
