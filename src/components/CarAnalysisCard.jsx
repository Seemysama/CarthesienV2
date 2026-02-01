/**
 * CarAnalysisCard - Carte d'analyse véhicule
 * 
 * Affiche les résultats de l'API /api/enrich/v2 avec:
 * - Badge de confiance (Or/Argent/Bronze)
 * - Score global avec jauge circulaire
 * - 3 jauges de progression (Fiabilité, Confort, Budget)
 * - Points forts / Points faibles
 * - Alertes moteur (si détectées)
 * - Verdict expert
 * 
 * @author Car-thesien Team
 * @version 1.0.0
 */

import React from 'react';
import './CarAnalysisCard.css';

// =============================================================================
// COMPOSANTS INTERNES
// =============================================================================

/**
 * Badge de confiance avec icône et couleur
 */
const ConfidenceBadge = ({ badge }) => {
  if (!badge) return null;
  
  const badgeStyles = {
    'Certifié': { bg: 'linear-gradient(135deg, #FFD700, #FFA500)', icon: '🥇', textColor: '#1a1a1a' },
    'Vérifié': { bg: 'linear-gradient(135deg, #C0C0C0, #A0A0A0)', icon: '🥈', textColor: '#1a1a1a' },
    'Estimé': { bg: 'linear-gradient(135deg, #CD7F32, #8B4513)', icon: '🥉', textColor: '#fff' },
  };
  
  const style = badgeStyles[badge.label] || { bg: '#6B7280', icon: '❓', textColor: '#fff' };
  
  return (
    <div 
      className="confidence-badge"
      style={{ background: style.bg, color: style.textColor }}
    >
      <span className="badge-icon">{style.icon}</span>
      <span className="badge-label">{badge.label}</span>
      <span className="badge-sources">{badge.sources_count} sources</span>
    </div>
  );
};

/**
 * Jauge circulaire pour le score global
 */
const CircularGauge = ({ value, max = 20, label }) => {
  const percentage = (value / max) * 100;
  const circumference = 2 * Math.PI * 45; // rayon = 45
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  // Couleur selon le score
  const getColor = (val) => {
    if (val >= 16) return '#22C55E';      // Vert
    if (val >= 13) return '#84CC16';      // Vert-jaune
    if (val >= 10) return '#EAB308';      // Jaune
    if (val >= 7) return '#F97316';       // Orange
    return '#EF4444';                      // Rouge
  };
  
  return (
    <div className="circular-gauge">
      <svg viewBox="0 0 100 100" className="gauge-svg">
        {/* Cercle de fond */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="#2D3748"
          strokeWidth="8"
        />
        {/* Cercle de progression */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke={getColor(value)}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          transform="rotate(-90 50 50)"
          className="gauge-progress"
        />
      </svg>
      <div className="gauge-value">
        <span className="value">{value.toFixed(1)}</span>
        <span className="max">/{max}</span>
      </div>
      <div className="gauge-label">{label}</div>
    </div>
  );
};

/**
 * Barre de progression horizontale
 */
const ProgressBar = ({ gauge }) => {
  const percentage = (gauge.value / gauge.max) * 100;
  
  return (
    <div className="progress-bar-container">
      <div className="progress-header">
        <span className="progress-icon">{gauge.icon}</span>
        <span className="progress-label">{gauge.label}</span>
        <span className="progress-value">{gauge.value.toFixed(1)}/{gauge.max}</span>
      </div>
      <div className="progress-track">
        <div 
          className="progress-fill"
          style={{ 
            width: `${percentage}%`,
            backgroundColor: gauge.color 
          }}
        />
      </div>
      <div className="progress-description">{gauge.description}</div>
    </div>
  );
};

/**
 * Liste de points (pros ou cons)
 */
const PointsList = ({ title, points, type }) => {
  const icon = type === 'pros' ? '✓' : '✗';
  const colorClass = type === 'pros' ? 'pros' : 'cons';
  
  return (
    <div className={`points-list ${colorClass}`}>
      <h4 className="points-title">
        {type === 'pros' ? '👍' : '👎'} {title}
      </h4>
      <ul>
        {points.map((point, index) => (
          <li key={index}>
            <span className="point-icon">{icon}</span>
            <span className="point-text">{point}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

/**
 * Alertes de fiabilité moteur
 */
const ReliabilityAlerts = ({ alerts }) => {
  if (!alerts) return null;
  
  const severityColors = {
    'critical': '#EF4444',
    'warning': '#F97316',
    'info': '#3B82F6',
  };
  
  return (
    <div 
      className="reliability-alerts"
      style={{ borderColor: severityColors[alerts.severity] || '#F97316' }}
    >
      <div className="alerts-header">
        <span className="alerts-icon">⚠️</span>
        <span className="alerts-title">Alerte: {alerts.engine_detected}</span>
      </div>
      <ul className="alerts-list">
        {alerts.alerts.map((alert, index) => (
          <li key={index}>{alert}</li>
        ))}
      </ul>
    </div>
  );
};

/**
 * Bloc TCO (Total Cost of Ownership)
 */
const TCOBlock = ({ tco }) => {
  if (!tco) return null;
  
  return (
    <div className="tco-block">
      <h4 className="tco-title">💰 Coût d'utilisation mensuel</h4>
      <div className="tco-details">
        <div className="tco-item">
          <span className="tco-label">⛽ Carburant</span>
          <span className="tco-value">{tco.fuel.monthly_cost.toFixed(0)}€</span>
        </div>
        <div className="tco-item">
          <span className="tco-label">🔧 Entretien</span>
          <span className="tco-value">{tco.maintenance.monthly_cost.toFixed(0)}€</span>
        </div>
        <div className="tco-item total">
          <span className="tco-label">Total</span>
          <span className="tco-value">{tco.total_monthly.toFixed(0)}€/mois</span>
        </div>
      </div>
      <div className="tco-annual">
        Soit <strong>{tco.total_annual.toFixed(0)}€/an</strong> pour {tco.monthly_km * 12} km
      </div>
    </div>
  );
};

/**
 * Verdict expert
 */
const VerdictBlock = ({ verdict }) => {
  if (!verdict) return null;
  
  return (
    <div className="verdict-block">
      <h4 className="verdict-title">🎯 Verdict Expert</h4>
      <p className="verdict-text">{verdict.text}</p>
      <div className="verdict-recommendation">{verdict.recommendation}</div>
    </div>
  );
};

// =============================================================================
// COMPOSANT PRINCIPAL
// =============================================================================

/**
 * Carte d'analyse véhicule complète
 * 
 * @param {Object} props
 * @param {Object} props.data - Données de l'API /api/enrich/v2
 * @param {boolean} props.loading - État de chargement
 * @param {string} props.error - Message d'erreur éventuel
 */
const CarAnalysisCard = ({ data, loading, error }) => {
  // État de chargement
  if (loading) {
    return (
      <div className="car-analysis-card loading">
        <div className="loading-spinner"></div>
        <p>Analyse en cours...</p>
      </div>
    );
  }
  
  // Erreur
  if (error) {
    return (
      <div className="car-analysis-card error">
        <div className="error-icon">❌</div>
        <p className="error-message">{error}</p>
      </div>
    );
  }
  
  // Pas de données
  if (!data) {
    return null;
  }
  
  return (
    <div className="car-analysis-card">
      {/* En-tête avec véhicule extrait */}
      <div className="card-header">
        <div className="vehicle-info">
          <h3 className="vehicle-name">
            {data.extracted?.brand?.toUpperCase()} {data.extracted?.model?.toUpperCase()}
          </h3>
          {data.extracted?.power_hp && (
            <span className="vehicle-power">{data.extracted.power_hp} ch</span>
          )}
          {data.extracted?.fuel && (
            <span className="vehicle-fuel">{data.extracted.fuel}</span>
          )}
        </div>
        <ConfidenceBadge badge={data.badge_confiance} />
      </div>
      
      {/* Score global */}
      <div className="score-section">
        <CircularGauge 
          value={data.scores?.global?.value || 0} 
          max={data.scores?.global?.max || 20}
          label={data.scores?.global?.label || 'Score Global'}
        />
      </div>
      
      {/* Jauges de détail */}
      <div className="gauges-section">
        {data.gauges?.map((gauge) => (
          <ProgressBar key={gauge.id} gauge={gauge} />
        ))}
      </div>
      
      {/* Alertes moteur */}
      {data.reliability_alerts && (
        <ReliabilityAlerts alerts={data.reliability_alerts} />
      )}
      
      {/* Points forts / faibles */}
      <div className="pros-cons-section">
        <PointsList 
          title="Points Forts" 
          points={data.pros_cons?.pros || []} 
          type="pros" 
        />
        <PointsList 
          title="Points Faibles" 
          points={data.pros_cons?.cons || []} 
          type="cons" 
        />
      </div>
      
      {/* TCO */}
      {data.tco && <TCOBlock tco={data.tco} />}
      
      {/* Verdict */}
      {data.verdict && <VerdictBlock verdict={data.verdict} />}
      
      {/* Footer avec sources */}
      <div className="card-footer">
        <span className="source-info">
          Sources: {data._source?.data_sources?.join(', ') || 'N/A'}
        </span>
        <span className="confidence-info">
          Confiance: {data._source?.confidence || 'N/A'}
        </span>
      </div>
    </div>
  );
};

export default CarAnalysisCard;
