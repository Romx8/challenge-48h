import { useEffect, useMemo, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import TextPressure from './components/TextPressure';

gsap.registerPlugin(ScrollTrigger);

const DEFAULT_FILTERS = {
  startDate: '',
  endDate: '',
  minLat: '41.0',
  maxLat: '51.5',
  minLng: '-5.5',
  maxLng: '9.8',
  minAqi: '',
  maxAqi: '',
  aggregateBy: 'none',
  limit: '300',
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8787').replace(/\/$/, '');

function getAqiColor(aqi) {
  if (aqi <= 20) return '#38d67a';
  if (aqi <= 40) return '#8adf4a';
  if (aqi <= 60) return '#ffd449';
  if (aqi <= 80) return '#ff9c38';
  return '#ff5f5f';
}

function getAqiLabel(aqi) {
  if (aqi <= 20) return 'Très faible';
  if (aqi <= 40) return 'Faible';
  if (aqi <= 60) return 'Modéré';
  if (aqi <= 80) return 'Élevé';
  return 'Très élevé';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function InteractiveIndexCard() {
  const [indexPreview, setIndexPreview] = useState(50);

  function onIndexPreviewChange(event) {
    setIndexPreview(Number(event.target.value));
  }

  return (
    <article className="panel index-scale-card" aria-label="Indice interactif">
      <p>Indice interactif (fictif)</p>
      <h3>{indexPreview}</h3>
      <small className="index-scale-note">N&apos;impacte pas les filtres ni les appels API.</small>
      <div className="index-scale-track" aria-hidden="true" />
      <input
        className="index-scale-input"
        type="range"
        min="0"
        max="100"
        value={indexPreview}
        onChange={onIndexPreviewChange}
        aria-label="Ajuster l'indice"
      />
      <div className="index-scale-ticks" aria-hidden="true">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
    </article>
  );
}

function App() {
  const appRef = useRef(null);
  const titleRef = useRef(null);
  const sunRef = useRef(null);
  const sunGlowRef = useRef(null);
  const sunFlareRef = useRef(null);
  const moonRef = useRef(null);
  const moonAuraRef = useRef(null);
  const mapPanelRef = useRef(null);
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markerLayerRef = useRef(null);
  const lenisRef = useRef(null);

  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [meta, setMeta] = useState(null);
  const [mapReady, setMapReady] = useState(false);

  const stats = useMemo(() => {
    if (!readings.length) {
      return {
        total: 0,
        averageAqi: 0,
        worstAqi: 0,
        zoneCount: 0,
      };
    }

    const averageAqi = Math.round(
      readings.reduce((sum, item) => sum + item.aqi, 0) / readings.length
    );

    const worstAqi = Math.max(...readings.map((item) => item.aqi));
    const zoneCount = new Set(readings.map((item) => item.city)).size;

    return {
      total: readings.length,
      averageAqi,
      worstAqi,
      zoneCount,
    };
  }, [readings]);

  const starField = useMemo(
    () =>
      Array.from({ length: 48 }, (_, index) => {
        const x = (index * 37 + 13) % 100;
        const y = (index * 29 + 17) % 100;
        const size = 2 + ((index * 11) % 4);
        const delay = -((index * 0.43) % 5.2);
        const duration = 3.8 + ((index * 0.27) % 2.8);
        const opacity = 0.34 + ((index * 0.07) % 0.46);

        return {
          id: index + 1,
          x,
          y,
          size,
          delay,
          duration,
          opacity: opacity.toFixed(2),
        };
      }),
    []
  );

  useEffect(() => {
    const lenis = new Lenis({
      autoRaf: true,
      duration: 1.22,
      smoothWheel: true,
      wheelMultiplier: 0.95,
      touchMultiplier: 1.1,
    });
    lenisRef.current = lenis;

    lenis.on('scroll', ScrollTrigger.update);

    const ctx = gsap.context(() => {
      gsap.from(titleRef.current, {
        opacity: 0,
        y: 74,
        scale: 0.96,
        duration: 1.3,
        ease: 'power3.out',
      });

      gsap.to(sunFlareRef.current, {
        rotate: 7,
        x: 12,
        y: 8,
        duration: 8,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.to(sunGlowRef.current, {
        opacity: 0.82,
        scale: 1.1,
        duration: 4,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.to(sunRef.current, {
        y: -9,
        duration: 4.8,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.set(moonRef.current, {
        opacity: 0,
        scale: 0.78,
        x: 24,
        y: 14,
      });

      gsap.to(moonRef.current, {
        y: -7,
        duration: 5.4,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.to(moonAuraRef.current, {
        opacity: 0.74,
        scale: 1.13,
        duration: 4.6,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.from('.reveal-item', {
        opacity: 0,
        y: 70,
        duration: 0.95,
        stagger: 0.14,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: '.dashboard-section',
          start: 'top 78%',
        },
      });

      gsap.timeline({
        scrollTrigger: {
          trigger: mapPanelRef.current,
          start: 'top 84%',
          end: 'top 36%',
          scrub: 1.2,
        },
      })
        .to('.night-overlay', { opacity: 1, ease: 'none', duration: 1 }, 0)
        .to(
          sunRef.current,
          {
            opacity: 0.14,
            scale: 0.8,
            ease: 'none',
            duration: 1,
          },
          0
        )
        .to(
          sunGlowRef.current,
          {
            opacity: 0.08,
            ease: 'none',
            duration: 1,
          },
          0
        )
        .to(
          moonRef.current,
          {
            opacity: 1,
            scale: 1,
            x: 0,
            ease: 'none',
            duration: 1,
          },
          0
        )
        .to('.sky-noise', { opacity: 0.34, ease: 'none', duration: 1 }, 0);
    }, appRef);

    return () => {
      ctx.revert();
      lenis.destroy();
      lenisRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const bootMap = () => {
      if (cancelled || mapRef.current) return;

      const L = window.L;
      if (!L || !mapContainerRef.current) {
        timer = setTimeout(bootMap, 120);
        return;
      }

      const map = L.map(mapContainerRef.current, {
        zoomControl: false,
      }).setView([46.7, 2.6], 6);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);

      markerLayerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapReady(true);

      requestAnimationFrame(() => {
        map.invalidateSize();
      });
    };

    bootMap();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerLayerRef.current = null;
        setMapReady(false);
      }
    };
  }, []);

  useEffect(() => {
    const L = window.L;
    if (!L || !mapReady || !mapRef.current || !markerLayerRef.current) return;

    mapRef.current.invalidateSize();
    markerLayerRef.current.clearLayers();

    if (!readings.length) return;

    const bounds = [];

    readings.forEach((item) => {
      const color = getAqiColor(item.aqi);
      const icon = L.divIcon({
        className: 'aqi-div-icon-wrapper',
        html: `<span class="aqi-badge" style="--aqi-color:${color}">${Math.round(item.aqi)}</span>`,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -20],
      });

      const marker = L.marker([item.latitude, item.longitude], { icon });

      const aqiLabel = meta?.mode === 'city' ? 'AQI moyen' : 'AQI';
      const sampleInfo = item.sampleSize
        ? `<br/>Échantillons: ${item.sampleSize}`
        : '';

      marker.bindPopup(
        `<strong>${escapeHtml(item.city)}</strong><br/>${aqiLabel}: ${item.aqi} (${getAqiLabel(item.aqi)})<br/>Date: ${new Date(item.measuredAt).toLocaleString('fr-FR')}${sampleInfo}`
      );

      markerLayerRef.current.addLayer(marker);
      bounds.push([item.latitude, item.longitude]);
    });

    if (bounds.length === 1) {
      mapRef.current.setView(bounds[0], 8, { animate: true });
      return;
    }

    mapRef.current.fitBounds(bounds, {
      padding: [28, 28],
      maxZoom: 10,
      animate: true,
      duration: 1.1,
    });
  }, [mapReady, readings, meta?.mode]);

  async function fetchReadings(nextFilters) {
    setLoading(true);
    setError('');

    const params = new URLSearchParams();

    if (nextFilters.startDate) params.set('start_date', nextFilters.startDate);
    if (nextFilters.endDate) params.set('end_date', nextFilters.endDate);
    if (nextFilters.minLat !== '') params.set('min_lat', nextFilters.minLat);
    if (nextFilters.maxLat !== '') params.set('max_lat', nextFilters.maxLat);
    if (nextFilters.minLng !== '') params.set('min_lng', nextFilters.minLng);
    if (nextFilters.maxLng !== '') params.set('max_lng', nextFilters.maxLng);
    if (nextFilters.minAqi !== '') params.set('min_index', nextFilters.minAqi);
    if (nextFilters.maxAqi !== '') params.set('max_index', nextFilters.maxAqi);
    if (nextFilters.aggregateBy) params.set('aggregate_by', nextFilters.aggregateBy);
    if (nextFilters.limit) params.set('limit', nextFilters.limit);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/readings?${params.toString()}`,
        { method: 'GET' }
      );

      if (!response.ok) {
        throw new Error(`API backend indisponible (${response.status})`);
      }

      const payload = await response.json();
      setReadings(Array.isArray(payload.items) ? payload.items : []);
      setMeta(
        payload.meta || {
          total: 0,
          returned: 0,
          mode: nextFilters.aggregateBy === 'city' ? 'city' : 'none',
          generatedAt: new Date().toISOString(),
          filters: nextFilters,
        }
      );
    } catch (fetchError) {
      setReadings([]);
      setMeta({
        total: 0,
        returned: 0,
        mode: nextFilters.aggregateBy === 'city' ? 'city' : 'none',
        generatedAt: new Date().toISOString(),
        filters: nextFilters,
      });
      setError(fetchError instanceof Error ? fetchError.message : 'Erreur réseau');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchReadings(DEFAULT_FILTERS);
  }, []);

  function onFilterChange(event) {
    const { name, value } = event.target;
    setFilters((previous) => ({ ...previous, [name]: value }));
  }

  function onFilterSubmit(event) {
    event.preventDefault();
    fetchReadings(filters);
  }

  function onResetFilters() {
    setFilters(DEFAULT_FILTERS);
    fetchReadings(DEFAULT_FILTERS);
  }

  function onScrollIndicatorClick(event) {
    event.preventDefault();

    if (lenisRef.current) {
      lenisRef.current.scrollTo('#dashboard', {
        duration: 1.18,
        easing: (value) => 1 - (1 - value) ** 3,
      });
      return;
    }

    const target = document.getElementById('dashboard');
    target?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

  return (
    <div className="app" ref={appRef}>
      <div className="night-overlay" aria-hidden="true">
        <div className="night-stars">
          {starField.map((star) => (
            <span
              key={`star-${star.id}`}
              className="night-star"
              style={{
                '--star-x': `${star.x}%`,
                '--star-y': `${star.y}%`,
                '--star-size': `${star.size}px`,
                '--star-delay': `${star.delay}s`,
                '--star-duration': `${star.duration}s`,
                '--star-opacity': star.opacity,
              }}
            />
          ))}
        </div>
      </div>
      <div className="sky-noise" aria-hidden="true" />

      <div className="sun-system" aria-hidden="true" ref={sunRef}>
        <div className="sun-aura" ref={sunGlowRef} />
        <div className="sun-bloom" />
        <div className="sun-disc" />
        <div className="sun-flare" ref={sunFlareRef}>
          {[1, 2, 3].map((value) => (
            <span key={`orb-${value}`} className={`flare-orb flare-orb-${value}`} />
          ))}
          <span className="flare-arc flare-arc-1" />
          <span className="flare-arc flare-arc-2" />
        </div>
      </div>

      <div className="moon-system" aria-hidden="true" ref={moonRef}>
        <div className="moon-aura" ref={moonAuraRef} />
        <div className="moon-disc">
          <span className="moon-rim" />
          <span className="moon-marble moon-marble-1" />
          <span className="moon-marble moon-marble-2" />
          <span className="moon-marble moon-marble-3" />
          <span className="moon-crater moon-crater-1" />
          <span className="moon-crater moon-crater-2" />
          <span className="moon-crater moon-crater-3" />
        </div>
      </div>

      <header className="hero">
        <div ref={titleRef} className="hero-title-wrap">
          <TextPressure
            text="Air map"
            flex={false}
            alpha={false}
            stroke={false}
            width={false}
            weight
            italic={false}
            fontFamily='"SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
            fontUrl=""
            loadFont={false}
            textColor="#fafdff"
            strokeColor="#5aa7ff"
            minFontSize={64}
          />
        </div>
        {/* <p>Prototype technique: API filtrable, worker cyclique, cartographie dynamique.</p> */}
        <a
          className="scroll-indicator"
          href="#dashboard"
          aria-label="Descendre"
          onClick={onScrollIndicatorClick}
        >
          ↓
        </a>
      </header>

      <main>
        <section id="dashboard" className="dashboard-section">
          <div className="panel controls-panel reveal-item">
            <h2>Filtres</h2>
            <form className="filters-form" onSubmit={onFilterSubmit}>
              <label>
                Date début
                <input
                  type="date"
                  name="startDate"
                  value={filters.startDate}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Date fin
                <input
                  type="date"
                  name="endDate"
                  value={filters.endDate}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Latitude min
                <input
                  type="number"
                  step="0.01"
                  name="minLat"
                  value={filters.minLat}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Latitude max
                <input
                  type="number"
                  step="0.01"
                  name="maxLat"
                  value={filters.maxLat}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Longitude min
                <input
                  type="number"
                  step="0.01"
                  name="minLng"
                  value={filters.minLng}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Longitude max
                <input
                  type="number"
                  step="0.01"
                  name="maxLng"
                  value={filters.maxLng}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Indice min
                <input
                  type="number"
                  min="0"
                  max="100"
                  name="minAqi"
                  value={filters.minAqi}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Indice max
                <input
                  type="number"
                  min="0"
                  max="100"
                  name="maxAqi"
                  value={filters.maxAqi}
                  onChange={onFilterChange}
                />
              </label>

              <label>
                Restitution
                <select
                  name="aggregateBy"
                  value={filters.aggregateBy}
                  onChange={onFilterChange}
                >
                  <option value="none">Mesures brutes</option>
                  <option value="city">Indice moyen par ville</option>
                </select>
              </label>

              <label>
                Limite
                <input
                  type="number"
                  min="10"
                  max="1000"
                  name="limit"
                  value={filters.limit}
                  onChange={onFilterChange}
                />
              </label>

              <div className="filters-actions">
                <button type="submit" disabled={loading}>
                  {loading ? 'Chargement...' : 'Appliquer'}
                </button>
                <button type="button" onClick={onResetFilters} disabled={loading}>
                  Réinitialiser
                </button>
              </div>
            </form>

            <InteractiveIndexCard />
          </div>

          <div className="stats-grid reveal-item">
            <article className="panel stat-card">
              <p>Mesures</p>
              <h3>{stats.total}</h3>
            </article>
            <article className="panel stat-card">
              <p>AQI moyen</p>
              <h3>{stats.averageAqi}</h3>
            </article>
            <article className="panel stat-card">
              <p>AQI max</p>
              <h3>{stats.worstAqi}</h3>
            </article>
            <article className="panel stat-card">
              <p>Zones actives</p>
              <h3>{stats.zoneCount}</h3>
            </article>
          </div>

          <div className="panel map-panel reveal-item" ref={mapPanelRef}>
            <div className="map-header">
              <h2>Carte</h2>
              <p>
                {meta?.returned ?? 0} points • mode{' '}
                {meta?.mode === 'city' ? 'moyenne par ville' : 'brut'} • mise à
                jour{' '}
                {meta?.generatedAt
                  ? new Date(meta.generatedAt).toLocaleTimeString('fr-FR')
                  : '--:--'}
              </p>
            </div>

            {error ? <p className="status error">{error}</p> : null}
            {!error && loading ? (
              <p className="status">Chargement des données...</p>
            ) : null}
            {!error && !loading && !readings.length ? (
              <p className="status">Aucune donnée pour ces filtres.</p>
            ) : null}

            <div ref={mapContainerRef} className="leaflet-map" />
          </div>

          <article className="panel about-panel reveal-item">
            <h2>À propos</h2>
            <p>
              <strong>Sources :</strong> les données sont issues de <strong>data.gouv.fr</strong> et de{' '}
              <strong>GeoD&apos;Air</strong>.
            </p>
            <p>
              <strong>Indice :</strong> l&apos;indice affiché sur la carte représente une fusion entre
              les mesures de <strong>pollution</strong> et les conditions <strong>météorologiques</strong>,
              pour donner un niveau synthétique et lisible de la qualité de l&apos;air.
            </p>
          </article>
        </section>

        <footer className="page-note">
          Projet réalisé dans le cadre du Challenge 48h
          <div className="credits">
            <a href="https://www.linkedin.com/in/romeo-bernard-666169292/" target="_blank" rel="noreferrer">
              Bernard Romeo
            </a>
            <a href="https://www.linkedin.com/in/yehya-abou-khechfe-55b4a9387/" target="_blank" rel="noreferrer">
              Abou Khechfe Yehya
            </a>
            <a href="https://quentincontreau.com/" target="_blank" rel="noreferrer">
              Contreau Quentin
            </a>
            <a href="https://dyskolos.fr" target="_blank" rel="noreferrer">
              Beuillé Baptiste
            </a>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
