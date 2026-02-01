/**
 * Car-thesien - Application principale
 * 
 * Interface "Leboncoin-like" avec :
 * - Navbar avec logo
 * - Barre de recherche avec filtres
 * - Grille de véhicules (annonces live ou base locale)
 * - Modal de détail avec CarAnalysisCard
 * - Support des annonces temps réel via /api/listings/search
 * 
 * @author Car-thesien Team
 * @version 3.0.0
 */

import React, { useState, useEffect } from 'react';
import CarAnalysisCard from './components/CarAnalysisCard';
import './App.css';

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_URL = '';  // Proxy Vite vers localhost:3030

// Mode de recherche : 'live' (scrapers) ou 'local' (base MongoDB)
const DEFAULT_SEARCH_MODE = 'local';

// =============================================================================
// HELPERS
// =============================================================================

const getGaugeColor = (score) => {
  if (!score) return '#9CA3AF';
  if (score >= 8) return '#22C55E';
  if (score >= 6) return '#84CC16';
  if (score >= 5) return '#EAB308';
  return '#EF4444';
};

const getRecommendation = (score, fiabilite) => {
  if (score >= 15 && fiabilite >= 7) return '🟢 Excellent choix - Achat recommandé';
  if (score >= 12 && fiabilite >= 5) return '🟡 Bon choix - Vérifiez l\'historique';
  if (score >= 10) return '🟠 Acceptable - Négociez le prix';
  return '🔴 Prudence - Risques potentiels';
};

const formatPrice = (price) => {
  if (!price) return 'Prix N/C';
  return new Intl.NumberFormat('fr-FR', { 
    style: 'currency', 
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(price);
};

const formatMileage = (km) => {
  if (!km) return '';
  return new Intl.NumberFormat('fr-FR').format(km) + ' km';
};

// =============================================================================
// COMPOSANTS
// =============================================================================

/**
 * Navbar principale
 */
const Navbar = ({ searchMode, setSearchMode }) => (
  <nav className="navbar">
    <div className="navbar-container">
      <a href="/" className="navbar-logo">
        <span className="logo-icon">🚗</span>
        <span className="logo-text">Car-thésien</span>
      </a>
      
      {/* Toggle mode de recherche */}
      <div className="search-mode-toggle">
        <button 
          className={`mode-btn ${searchMode === 'local' ? 'active' : ''}`}
          onClick={() => setSearchMode('local')}
          title="Base de données locale"
        >
          📊 Base locale
        </button>
        <button 
          className={`mode-btn ${searchMode === 'live' ? 'active' : ''}`}
          onClick={() => setSearchMode('live')}
          title="Annonces temps réel"
        >
          🔴 Annonces live
        </button>
      </div>
      
      <div className="navbar-links">
        <a href="#" className="nav-link">Comment ça marche ?</a>
        <a href="#" className="nav-link btn-cta">Déposer une annonce</a>
      </div>
    </div>
  </nav>
);

/**
 * Barre de recherche avec filtres
 */
const SearchBar = ({ filters, setFilters, marques, onSearch, loading, searchMode }) => {
  const carburants = [
    { value: '', label: 'Tous carburants' },
    { value: 'essence', label: 'Essence' },
    { value: 'diesel', label: 'Diesel' },
    { value: 'hybride', label: 'Hybride' },
    { value: 'electrique', label: 'Électrique' },
  ];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <div className="search-bar">
      <form onSubmit={handleSubmit} className="search-form">
        <div className="filter-group">
          <label>Marque</label>
          <select 
            name="marque" 
            value={filters.marque} 
            onChange={handleChange}
            className="filter-select"
          >
            <option value="">Toutes les marques</option>
            {marques.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Modèle</label>
          <input
            type="text"
            name="modele"
            value={filters.modele}
            onChange={handleChange}
            placeholder="Ex: 3008, Clio..."
            className="filter-input"
          />
        </div>

        <div className="filter-group">
          <label>Carburant</label>
          <select 
            name="carburant" 
            value={filters.carburant} 
            onChange={handleChange}
            className="filter-select"
          >
            {carburants.map(c => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        {/* Filtres spécifiques au mode live */}
        {searchMode === 'live' && (
          <>
            <div className="filter-group">
              <label>Prix max</label>
              <input
                type="number"
                name="prix_max"
                value={filters.prix_max || ''}
                onChange={handleChange}
                placeholder="20000"
                className="filter-input small"
              />
            </div>
            <div className="filter-group">
              <label>Km max</label>
              <input
                type="number"
                name="km_max"
                value={filters.km_max || ''}
                onChange={handleChange}
                placeholder="100000"
                className="filter-input small"
              />
            </div>
          </>
        )}

        {/* Score min pour mode local */}
        {searchMode === 'local' && (
          <div className="filter-group">
            <label>Score min.</label>
            <input
              type="number"
              name="score_min"
              value={filters.score_min}
              onChange={handleChange}
              placeholder="0"
              min="0"
              max="20"
              className="filter-input small"
            />
          </div>
        )}

        <button type="submit" className="search-btn" disabled={loading}>
          {loading ? (
            <span className="btn-loading"></span>
          ) : (
            <>
              <span className="btn-icon">🔍</span>
              <span>{searchMode === 'live' ? 'Rechercher annonces' : 'Rechercher'}</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};

/**
 * Carte véhicule dans la grille
 * Supporte à la fois les véhicules locaux (base MongoDB) et les annonces live
 */
const VehicleCard = ({ vehicle, onClick, isLive = false }) => {
  const getBadgeClass = (badge) => {
    if (!badge) return 'badge-default';
    if (badge.level === 'certified') return 'badge-gold';
    if (badge.level === 'verified') return 'badge-silver';
    return 'badge-bronze';
  };

  const getScoreColor = (score) => {
    if (score >= 15) return '#22C55E';
    if (score >= 12) return '#84CC16';
    if (score >= 10) return '#EAB308';
    return '#F97316';
  };

  // Mode LIVE : affichage annonce externe
  if (isLive) {
    return (
      <div className="vehicle-card vehicle-card-live">
        {/* Image ou placeholder */}
        <div className="vehicle-image">
          {vehicle.photo_url ? (
            <img 
              src={vehicle.photo_url} 
              alt={vehicle.title}
              className="vehicle-photo"
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
          ) : null}
          <div className="image-placeholder" style={{ display: vehicle.photo_url ? 'none' : 'flex' }}>
            <span className="car-emoji">🚗</span>
          </div>
          
          {/* Badge source */}
          <span className="source-badge">{vehicle.source_site}</span>
          
          {/* Badge bonne affaire */}
          {vehicle.is_good_deal && (
            <span className="badge-deal">🔥 Bonne affaire</span>
          )}
        </div>

        {/* Infos annonce */}
        <div className="vehicle-info">
          <h3 className="vehicle-title">{vehicle.title}</h3>
          
          <div className="vehicle-price">{formatPrice(vehicle.price)}</div>
          
          <div className="vehicle-specs">
            {vehicle.year && <span className="spec">{vehicle.year}</span>}
            {vehicle.mileage && <span className="spec">{formatMileage(vehicle.mileage)}</span>}
            {vehicle.city && <span className="spec">📍 {vehicle.city}</span>}
          </div>

          {/* Score expert si disponible */}
          {vehicle.expert_score && (
            <div className="vehicle-score">
              <div 
                className="score-circle"
                style={{ borderColor: getScoreColor(vehicle.expert_score) }}
              >
                <span className="score-value">{vehicle.expert_score?.toFixed(1)}</span>
                <span className="score-max">/20</span>
              </div>
              <span className="score-label">Score Expert</span>
            </div>
          )}

          {/* Alertes fiabilité */}
          {vehicle.reliability_alerts && vehicle.reliability_alerts.length > 0 && (
            <div className="vehicle-alerts">
              <span className="alert-icon">⚠️</span>
              <span className="alert-text">{vehicle.reliability_alerts[0]}</span>
            </div>
          )}
        </div>

        {/* CTAs */}
        <div className="cta-buttons">
          <button className="btn-details" onClick={onClick}>
            Voir l'analyse →
          </button>
          <a 
            href={vehicle.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="btn-external"
            onClick={(e) => e.stopPropagation()}
          >
            Voir l'annonce originale ↗
          </a>
        </div>
      </div>
    );
  }

  // Mode LOCAL : véhicule de la base
  return (
    <div className="vehicle-card" onClick={onClick}>
      {/* Image placeholder */}
      <div className="vehicle-image">
        <div className="image-placeholder">
          <span className="car-emoji">🚗</span>
        </div>
        {vehicle.badge && (
          <span className={`vehicle-badge ${getBadgeClass(vehicle.badge)}`}>
            {vehicle.badge.label}
          </span>
        )}
      </div>

      {/* Infos */}
      <div className="vehicle-info">
        <h3 className="vehicle-title">
          {vehicle.marque} {vehicle.modele}
        </h3>
        
        <div className="vehicle-specs">
          {vehicle.carburant && (
            <span className="spec">{vehicle.carburant}</span>
          )}
          {vehicle.puissance_cv && (
            <span className="spec">{vehicle.puissance_cv} ch</span>
          )}
        </div>

        {/* Score IA */}
        <div className="vehicle-score">
          <div 
            className="score-circle"
            style={{ borderColor: getScoreColor(vehicle.note_finale) }}
          >
            <span className="score-value">{vehicle.note_finale?.toFixed(1)}</span>
            <span className="score-max">/20</span>
          </div>
          <span className="score-label">Score IA</span>
        </div>

        {/* Aperçu qualités */}
        {vehicle.qualites && vehicle.qualites.length > 0 && (
          <div className="vehicle-preview">
            <span className="preview-icon">✓</span>
            <span className="preview-text">
              {vehicle.qualites[0]?.substring(0, 60)}...
            </span>
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="vehicle-cta">
        <button className="btn-details">
          Voir l'analyse complète →
        </button>
      </div>
    </div>
  );
};

/**
 * Modal de détail véhicule
 */
const VehicleModal = ({ vehicle, onClose }) => {
  if (!vehicle) return null;

  // Transformer vehicle_stats en format CarAnalysisCard
  const analysisData = {
    extracted: {
      brand: vehicle.marque,
      model: vehicle.modele,
      fuel: vehicle.carburant,
      power_hp: vehicle.puissance_cv,
    },
    badge_confiance: vehicle.badge ? {
      label: vehicle.badge.label,
      emoji: vehicle.badge.level === 'certified' ? '🥇' : vehicle.badge.level === 'verified' ? '🥈' : '🥉',
      sources_count: Object.values(vehicle.sources || {}).filter(Boolean).length,
      sources: Object.keys(vehicle.sources || {}).filter(k => vehicle.sources[k]),
    } : null,
    scores: {
      global: {
        value: vehicle.note_finale,
        max: 20,
        label: 'Score Global',
      },
      details: vehicle.scores,
    },
    gauges: [
      {
        id: 'fiabilite',
        label: 'Fiabilité',
        value: vehicle.scores?.fiabilite || 5,
        max: 10,
        color: getGaugeColor(vehicle.scores?.fiabilite),
        icon: '🔧',
        description: 'Durabilité mécanique',
      },
      {
        id: 'confort',
        label: 'Confort',
        value: vehicle.scores?.confort || 5,
        max: 10,
        color: getGaugeColor(vehicle.scores?.confort),
        icon: '🛋️',
        description: 'Agrément de conduite',
      },
      {
        id: 'budget',
        label: 'Budget',
        value: vehicle.scores?.budget || 5,
        max: 10,
        color: getGaugeColor(vehicle.scores?.budget),
        icon: '💰',
        description: 'Coût d\'utilisation',
      },
    ],
    pros_cons: {
      pros: vehicle.qualites || [],
      cons: vehicle.defauts || [],
    },
    verdict: {
      text: vehicle.verdict_expert,
      recommendation: getRecommendation(vehicle.note_finale, vehicle.scores?.fiabilite),
    },
    known_issues: vehicle.pannes_connues,
    _source: {
      type: 'vehicle_stats',
      confidence: vehicle.badge?.level === 'certified' ? 'high' : 'medium',
      data_sources: Object.keys(vehicle.sources || {}).filter(k => vehicle.sources[k]),
    },
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <CarAnalysisCard data={analysisData} />
      </div>
    </div>
  );
};

// =============================================================================
// APP PRINCIPALE
// =============================================================================

function App() {
  // États
  const [vehicles, setVehicles] = useState([]);
  const [liveListings, setLiveListings] = useState([]);
  const [marques, setMarques] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchMode, setSearchMode] = useState(DEFAULT_SEARCH_MODE);
  const [filters, setFilters] = useState({
    marque: '',
    modele: '',
    carburant: '',
    score_min: '',
    prix_max: '',
    km_max: '',
  });
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [totalCount, setTotalCount] = useState(0);

  // Chargement initial
  useEffect(() => {
    if (searchMode === 'local') {
      loadVehicles();
    } else {
      setLoading(false);
    }
  }, [searchMode]);

  // Charger les véhicules locaux
  const loadVehicles = async (searchFilters = null) => {
    setLoading(true);
    setError(null);

    try {
      let response;
      
      if (searchFilters && Object.values(searchFilters).some(v => v)) {
        // Recherche avec filtres
        response = await fetch(`${API_URL}/api/vehicles/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(searchFilters),
        });
      } else {
        // Listing par défaut
        response = await fetch(`${API_URL}/api/vehicles?limit=24`);
      }

      if (!response.ok) throw new Error('Erreur serveur');

      const data = await response.json();
      
      setVehicles(data.vehicles || []);
      setTotalCount(data.total || data.count || 0);
      
      // Récupérer les marques disponibles
      if (data.filters_available?.marques) {
        setMarques(data.filters_available.marques);
      }
    } catch (err) {
      setError(err.message);
      console.error('Erreur:', err);
    } finally {
      setLoading(false);
    }
  };

  // Charger les annonces live
  const loadLiveListings = async () => {
    if (!filters.marque) {
      setError('Veuillez sélectionner une marque pour la recherche live');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const searchParams = {
        marque: filters.marque,
        modele: filters.modele || null,
        prix_max: filters.prix_max ? parseInt(filters.prix_max) : null,
        km_max: filters.km_max ? parseInt(filters.km_max) : null,
      };

      const response = await fetch(`${API_URL}/api/listings/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams),
      });

      if (!response.ok) throw new Error('Erreur recherche live');

      const data = await response.json();
      
      setLiveListings(data.listings || []);
      setTotalCount(data.total || 0);
    } catch (err) {
      setError(err.message);
      console.error('Erreur live:', err);
    } finally {
      setLoading(false);
    }
  };

  // Recherche avec filtres
  const handleSearch = () => {
    if (searchMode === 'live') {
      loadLiveListings();
    } else {
      const activeFilters = {};
      if (filters.marque) activeFilters.marque = filters.marque;
      if (filters.modele) activeFilters.modele = filters.modele;
      if (filters.carburant) activeFilters.carburant = filters.carburant;
      loadVehicles(activeFilters);
    }
  };

  // Charger détail véhicule
  const handleVehicleClick = async (vehicle) => {
    try {
      const response = await fetch(`${API_URL}/api/vehicle/${vehicle._id}`);
      if (response.ok) {
        const data = await response.json();
        setSelectedVehicle(data.vehicle);
      } else {
        setSelectedVehicle(vehicle);
      }
    } catch {
      setSelectedVehicle(vehicle);
    }
  };

  // Filtrer par score minimum côté client (mode local seulement)
  const filteredVehicles = searchMode === 'local' && filters.score_min 
    ? vehicles.filter(v => v.note_finale >= parseFloat(filters.score_min))
    : vehicles;

  // Données à afficher selon le mode
  const displayItems = searchMode === 'live' ? liveListings : filteredVehicles;

  return (
    <div className="app">
      <Navbar searchMode={searchMode} setSearchMode={setSearchMode} />
      
      <main className="main-content">
        {/* Hero section */}
        <section className="hero">
          <h1>Trouvez votre véhicule idéal</h1>
          <p>
            {searchMode === 'live' 
              ? '🔴 Recherche en temps réel sur Aramis Auto, La Centrale...'
              : 'Analyse IA basée sur 627 véhicules, 425 fiches techniques et 210 avis réels'
            }
          </p>
        </section>

        {/* Barre de recherche */}
        <SearchBar 
          filters={filters}
          setFilters={setFilters}
          marques={marques}
          onSearch={handleSearch}
          loading={loading}
          searchMode={searchMode}
        />

        {/* Résultats */}
        <section className="results-section">
          <div className="results-header">
            <h2>
              {searchMode === 'live' 
                ? 'Annonces en temps réel' 
                : (filters.marque || filters.modele ? 'Résultats de recherche' : 'Véhicules populaires')
              }
            </h2>
            <span className="results-count">
              {displayItems.length} {searchMode === 'live' ? 'annonce' : 'véhicule'}{displayItems.length > 1 ? 's' : ''}
              {totalCount > displayItems.length && ` sur ${totalCount}`}
            </span>
          </div>

          {error && (
            <div className="error-banner">
              <span>⚠️</span> {error}
            </div>
          )}

          {loading ? (
            <div className="loading-grid">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="vehicle-card skeleton">
                  <div className="skeleton-image"></div>
                  <div className="skeleton-text"></div>
                  <div className="skeleton-text short"></div>
                </div>
              ))}
            </div>
          ) : displayItems.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">🔍</span>
              <p>
                {searchMode === 'live' 
                  ? 'Sélectionnez une marque et cliquez sur "Rechercher annonces"'
                  : 'Aucun véhicule trouvé avec ces critères'
                }
              </p>
              {searchMode === 'local' && (
                <button 
                  className="btn-reset"
                  onClick={() => {
                    setFilters({ marque: '', modele: '', carburant: '', score_min: '', prix_max: '', km_max: '' });
                    loadVehicles();
                  }}
                >
                  Réinitialiser les filtres
                </button>
              )}
            </div>
          ) : (
            <div className="vehicles-grid">
              {displayItems.map((item, idx) => (
                <VehicleCard 
                  key={item._id || item.external_id || idx}
                  vehicle={item}
                  onClick={() => handleVehicleClick(item)}
                  isLive={searchMode === 'live'}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <p>🛡️ <strong>Car-thésien</strong> - Données vérifiées depuis ADEME, fiches-auto.fr, avis-auto.fr</p>
          <p className="footer-disclaimer">
            100% traçabilité • Zéro hallucination • Scores basés sur données réelles
          </p>
        </div>
      </footer>

      {/* Modal détail */}
      {selectedVehicle && (
        <VehicleModal 
          vehicle={selectedVehicle}
          onClose={() => setSelectedVehicle(null)}
        />
      )}
    </div>
  );
}

export default App;
