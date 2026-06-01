'use client';

import React, { useRef, useEffect, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { Search, Layers, MapPin } from 'lucide-react';
import { useStore } from '@/store/useStore';

export default function LeadMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const { leads, mapViewState, selectLead } = useStore();
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!mapContainer.current) return;
    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) return;

    mapboxgl.accessToken = token;
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [mapViewState.lng, mapViewState.lat],
      zoom: mapViewState.zoom,
    });

    map.current.addControl(new mapboxgl.NavigationControl(), 'top-right');

    return () => { map.current?.remove(); };
  }, []);

  // Add/update lead markers
  useEffect(() => {
    if (!map.current) return;

    // Clear existing markers
    document.querySelectorAll('.lead-marker').forEach((el) => el.remove());

    leads.forEach((lead) => {
      if (!lead.preferences?.location_preferences?.length) return;

      const color = lead.warmth_tier === 'HOT' ? '#ef4444'
        : lead.warmth_tier === 'WARM' ? '#f59e0b'
        : lead.warmth_tier === 'COLD' ? '#3b82f6'
        : '#6b7280';

      const el = document.createElement('div');
      el.className = 'lead-marker';
      el.style.cssText = `
        width: 24px; height: 24px; border-radius: 50%;
        background: ${color}; border: 3px solid white;
        cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        transition: transform 0.2s;
      `;
      if (lead.warmth_score >= 80) {
        el.style.animation = 'pulse-glow 2s infinite';
      }
      el.onmouseenter = () => { el.style.transform = 'scale(1.3)'; };
      el.onmouseleave = () => { el.style.transform = 'scale(1)'; };
      el.onclick = () => { selectLead(lead.id); };

      // Use first location or default
      const lng = lead.preferences?.lng || -97.7431;
      const lat = lead.preferences?.lat || 30.2672;

      const popup = new mapboxgl.Popup({ offset: 15, closeButton: false })
        .setHTML(`
          <div style="padding:8px;font-size:12px;">
            <strong>${lead.name || lead.phone}</strong><br/>
            <span style="color:${color}">${lead.warmth_tier}</span> · ${lead.warmth_score}%<br/>
            <span style="color:#94a3b8">${lead.last_message?.substring(0, 40) || ''}</span>
          </div>
        `);

      new mapboxgl.Marker(el)
        .setLngLat([lng, lat])
        .setPopup(popup)
        .addTo(map.current!);
    });
  }, [leads, selectLead]);

  return (
    <div className="flex flex-col h-full bg-slate-900 border-l border-slate-700/50">
      {/* Search & Controls */}
      <div className="p-3 border-b border-slate-700/50 flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <button
          onClick={() => setShowHeatmap(!showHeatmap)}
          className={`p-2 rounded-lg transition-colors ${showHeatmap ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}
          title="Toggle heatmap"
        >
          <Layers className="w-4 h-4" />
        </button>
      </div>

      {/* Map Container */}
      <div ref={mapContainer} className="flex-1 relative">
        {/* Legend */}
        <div className="absolute bottom-4 left-4 z-10 bg-slate-900/90 backdrop-blur rounded-lg p-3 space-y-1">
          {[
            { color: '#ef4444', label: '🔥 Hot' },
            { color: '#f59e0b', label: '⏳ Warm' },
            { color: '#3b82f6', label: '❄️ Cold' },
            { color: '#6b7280', label: '🆕 New' },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-xs text-slate-300">
              <span className="w-3 h-3 rounded-full" style={{ background: item.color }} />
              {item.label}
            </div>
          ))}
        </div>

        {/* Lead count */}
        <div className="absolute top-4 left-4 z-10 bg-slate-900/90 backdrop-blur rounded-lg px-3 py-2">
          <div className="flex items-center gap-1 text-xs text-slate-300">
            <MapPin className="w-3 h-3" />
            {leads.size} leads mapped
          </div>
        </div>
      </div>
    </div>
  );
}
