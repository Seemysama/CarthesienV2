/**
 * Car-thesien - Application Marketplace
 * Version simplifiée et fonctionnelle
 */

import { useState, useEffect } from 'react';
import './index.css';

// =============================================================================
// HELPERS
// =============================================================================

const formatPrice = (price) => {
  if (!price) return 'Prix N/C';
  return new Intl.NumberFormat('fr-FR', { 
    style: 'currency', 
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(price);
};

const getScoreColor = (score) => {
  if (!score) return '#9CA3AF';
  if (score >= 15) return '#22c55e';
  if (score >= 12) return '#eab308';
  if (score >= 10) return '#f97316';
  return '#ef4444';
};

const getRecommendation = (score) => {
  if (score >= 15) return { text: '🟢 Excellent choix', color: '#22c55e' };
  if (score >= 12) return { text: '🟡 Bon choix', color: '#eab308' };
  if (score >= 10) return { text: '🟠 Acceptable', color: '#f97316' };
  return { text: '🔴 Prudence', color: '#ef4444' };
};

// =============================================================================
// COMPOSANTS
// =============================================================================

const Navbar = () => (
  <nav style={{
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    height: '70px',
    background: 'rgba(15, 23, 42, 0.95)',
    backdropFilter: 'blur(10px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 40px',
    zIndex: 1000,
    borderBottom: '1px solid rgba(255,255,255,0.1)'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <span style={{ fontSize: '1.8rem' }}>🚗</span>
      <span style={{ fontSize: '1.4rem', fontWeight: 700, color: 'white' }}>Car-thésien</span>
    </div>
    <div style={{ color: 'rgba(255,255,255,0.7)' }}>
      Analyse intelligente de véhicules
    </div>
  </nav>
);

const CarCard = ({ car, onClick }) => {
  const score = car.note_finale || car.expert_score || 0;
  const image = car.photo_url || "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400";

  return (
    <div 
      onClick={() => onClick && onClick(car)}
      style={{
        background: 'white',
        borderRadius: '16px',
        overflow: 'hidden',
        boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
        cursor: 'pointer',
        transition: 'transform 0.2s, box-shadow 0.2s'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.boxShadow = '0 8px 30px rgba(0,0,0,0.15)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.1)';
      }}
    >
      {/* Image */}
      <div style={{ position: 'relative', height: '180px' }}>
        <img 
          src={image} 
          alt={car.title}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(e) => {
            e.target.src = "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400";
          }}
        />
        {/* Badge Score */}
        <div style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          background: getScoreColor(score),
          color: 'white',
          padding: '6px 12px',
          borderRadius: '20px',
          fontWeight: 700,
          fontSize: '0.9rem'
        }}>
          {score.toFixed(1)}/20
        </div>
      </div>

      {/* Contenu */}
      <div style={{ padding: '16px' }}>
        <h3 style={{ 
          margin: '0 0 8px 0', 
          fontSize: '1.1rem',
          color: '#1e293b',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }}>
          {car.title || `${car.marque} ${car.modele}`}
        </h3>
        
        <div style={{ 
          fontSize: '1.4rem', 
          fontWeight: 800, 
          color: '#3b82f6',
          marginBottom: '12px'
        }}>
          {formatPrice(car.price)}
        </div>

        <div style={{ 
          display: 'flex', 
          gap: '16px', 
          color: '#64748b',
          fontSize: '0.85rem'
        }}>
          {car.year && <span>📅 {car.year}</span>}
          {car.mileage && <span>📏 {car.mileage.toLocaleString()} km</span>}
          {car.fuel && <span>⛽ {car.fuel}</span>}
        </div>

        {/* Mini jauges */}
        {(car.analysis?.scores?.details || car.scores) && (
          <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
            {(car.analysis?.scores?.details?.fiabilite || car.scores?.fiabilite) && (
              <div style={{ 
                flex: 1, 
                background: '#f1f5f9', 
                borderRadius: '8px', 
                padding: '8px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Fiabilité</div>
                <div style={{ fontWeight: 700, color: getScoreColor((car.analysis?.scores?.details?.fiabilite || car.scores?.fiabilite) * 2) }}>
                  {car.analysis?.scores?.details?.fiabilite || car.scores?.fiabilite}/10
                </div>
              </div>
            )}
            {(car.analysis?.scores?.details?.budget || car.scores?.budget) && (
              <div style={{ 
                flex: 1, 
                background: '#f1f5f9', 
                borderRadius: '8px', 
                padding: '8px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Budget</div>
                <div style={{ fontWeight: 700, color: getScoreColor((car.analysis?.scores?.details?.budget || car.scores?.budget) * 2) }}>
                  {car.analysis?.scores?.details?.budget || car.scores?.budget}/10
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const SearchBar = ({ filters, setFilters, onSearch, loading }) => {
  return (
    <div style={{
      display: 'flex',
      gap: '12px',
      padding: '20px',
      background: 'white',
      borderRadius: '16px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
      marginBottom: '30px',
      flexWrap: 'wrap'
    }}>
      <input
        type="text"
        placeholder="Marque (ex: Peugeot)"
        value={filters.marque}
        onChange={(e) => setFilters({...filters, marque: e.target.value})}
        style={{
          flex: 1,
          minWidth: '150px',
          padding: '12px 16px',
          border: '2px solid #e2e8f0',
          borderRadius: '10px',
          fontSize: '1rem'
        }}
      />
      <input
        type="text"
        placeholder="Modèle (ex: 308)"
        value={filters.modele}
        onChange={(e) => setFilters({...filters, modele: e.target.value})}
        style={{
          flex: 1,
          minWidth: '150px',
          padding: '12px 16px',
          border: '2px solid #e2e8f0',
          borderRadius: '10px',
          fontSize: '1rem'
        }}
      />
      <button
        onClick={onSearch}
        disabled={loading}
        style={{
          padding: '12px 30px',
          background: loading ? '#94a3b8' : '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '10px',
          fontSize: '1rem',
          fontWeight: 600,
          cursor: loading ? 'not-allowed' : 'pointer'
        }}
      >
        {loading ? '⏳ Chargement...' : '🔍 Rechercher'}
      </button>
    </div>
  );
};

// =============================================================================
// MODAL DÉTAIL VÉHICULE
// =============================================================================

const VehicleModal = ({ car, onClose }) => {
  if (!car) return null;
  
  const score = car.note_finale || car.expert_score || 0;
  const recommendation = getRecommendation(score);
  const image = car.photo_url || "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=800";

  return (
    <div 
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        padding: '20px'
      }}
    >
      <div 
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'white',
          borderRadius: '20px',
          maxWidth: '900px',
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto'
        }}
      >
        {/* Header avec image */}
        <div style={{ position: 'relative' }}>
          <img 
            src={image} 
            alt={car.title}
            style={{ 
              width: '100%', 
              height: '300px', 
              objectFit: 'cover',
              borderRadius: '20px 20px 0 0'
            }}
            onError={(e) => {
              e.target.src = "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=800";
            }}
          />
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '15px',
              right: '15px',
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              background: 'rgba(0,0,0,0.5)',
              color: 'white',
              fontSize: '1.5rem',
              cursor: 'pointer'
            }}
          >
            ✕
          </button>
          {/* Badge Score */}
          <div style={{
            position: 'absolute',
            bottom: '-25px',
            left: '30px',
            background: getScoreColor(score),
            color: 'white',
            padding: '15px 25px',
            borderRadius: '15px',
            fontWeight: 700,
            fontSize: '1.3rem',
            boxShadow: '0 4px 15px rgba(0,0,0,0.2)'
          }}>
            {score.toFixed(1)}/20
          </div>
        </div>

        {/* Contenu */}
        <div style={{ padding: '40px 30px 30px' }}>
          {/* Titre et prix */}
          <div style={{ marginBottom: '25px' }}>
            <h2 style={{ margin: '0 0 10px 0', fontSize: '1.8rem', color: '#1e293b' }}>
              {car.title || `${car.marque} ${car.modele}`}
            </h2>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: '#3b82f6' }}>
              {formatPrice(car.price)}
            </div>
          </div>

          {/* Recommendation */}
          <div style={{
            background: recommendation.color + '20',
            border: `2px solid ${recommendation.color}`,
            borderRadius: '12px',
            padding: '15px 20px',
            marginBottom: '25px',
            fontSize: '1.1rem',
            fontWeight: 600,
            color: recommendation.color
          }}>
            {recommendation.text}
          </div>

          {/* Caractéristiques */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '15px',
            marginBottom: '25px'
          }}>
            {car.year && (
              <div style={{ background: '#f1f5f9', padding: '15px', borderRadius: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Année</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b' }}>{car.year}</div>
              </div>
            )}
            {car.mileage && (
              <div style={{ background: '#f1f5f9', padding: '15px', borderRadius: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Kilométrage</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b' }}>{car.mileage.toLocaleString()} km</div>
              </div>
            )}
            {(car.fuel || car.carburant) && (
              <div style={{ background: '#f1f5f9', padding: '15px', borderRadius: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Carburant</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b' }}>{car.fuel || car.carburant}</div>
              </div>
            )}
            {car.city && (
              <div style={{ background: '#f1f5f9', padding: '15px', borderRadius: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Localisation</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b' }}>{car.city}</div>
              </div>
            )}
          </div>

          {/* Scores détaillés */}
          {(car.analysis?.scores?.details || car.scores) && (
            <div style={{ marginBottom: '25px' }}>
              <h3 style={{ margin: '0 0 15px 0', color: '#1e293b' }}>📊 Scores détaillés</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
                {(car.analysis?.scores?.details?.fiabilite ?? car.scores?.fiabilite) !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span>🔧 Fiabilité</span>
                      <span style={{ fontWeight: 700 }}>{car.analysis?.scores?.details?.fiabilite ?? car.scores?.fiabilite}/10</span>
                    </div>
                    <div style={{ background: '#e2e8f0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${(car.analysis?.scores?.details?.fiabilite ?? car.scores?.fiabilite) * 10}%`, 
                        height: '100%', 
                        background: getScoreColor((car.analysis?.scores?.details?.fiabilite ?? car.scores?.fiabilite) * 2),
                        borderRadius: '10px'
                      }} />
                    </div>
                  </div>
                )}
                {(car.analysis?.scores?.details?.confort ?? car.scores?.confort) !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span>🛋️ Confort</span>
                      <span style={{ fontWeight: 700 }}>{car.analysis?.scores?.details?.confort ?? car.scores?.confort}/10</span>
                    </div>
                    <div style={{ background: '#e2e8f0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${(car.analysis?.scores?.details?.confort ?? car.scores?.confort) * 10}%`, 
                        height: '100%', 
                        background: getScoreColor((car.analysis?.scores?.details?.confort ?? car.scores?.confort) * 2),
                        borderRadius: '10px'
                      }} />
                    </div>
                  </div>
                )}
                {(car.analysis?.scores?.details?.budget ?? car.scores?.budget) !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span>💰 Budget</span>
                      <span style={{ fontWeight: 700 }}>{car.analysis?.scores?.details?.budget ?? car.scores?.budget}/10</span>
                    </div>
                    <div style={{ background: '#e2e8f0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${(car.analysis?.scores?.details?.budget ?? car.scores?.budget) * 10}%`, 
                        height: '100%', 
                        background: getScoreColor((car.analysis?.scores?.details?.budget ?? car.scores?.budget) * 2),
                        borderRadius: '10px'
                      }} />
                    </div>
                  </div>
                )}
                {(car.analysis?.scores?.details?.securite) !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span>🛡️ Sécurité</span>
                      <span style={{ fontWeight: 700 }}>{car.analysis?.scores?.details?.securite}/10</span>
                    </div>
                    <div style={{ background: '#e2e8f0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${car.analysis?.scores?.details?.securite * 10}%`, 
                        height: '100%', 
                        background: getScoreColor(car.analysis?.scores?.details?.securite * 2),
                        borderRadius: '10px'
                      }} />
                    </div>
                  </div>
                )}
                {(car.analysis?.scores?.details?.habitabilite) !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span>🚗 Habitabilité</span>
                      <span style={{ fontWeight: 700 }}>{car.analysis?.scores?.details?.habitabilite}/10</span>
                    </div>
                    <div style={{ background: '#e2e8f0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${car.analysis?.scores?.details?.habitabilite * 10}%`, 
                        height: '100%', 
                        background: getScoreColor(car.analysis?.scores?.details?.habitabilite * 2),
                        borderRadius: '10px'
                      }} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Qualités / Défauts */}
          {((car.analysis?.qualites?.length > 0 || car.qualites?.length > 0) || (car.analysis?.defauts?.length > 0 || car.defauts?.length > 0)) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '25px' }}>
              {(car.analysis?.qualites?.length > 0 || car.qualites?.length > 0) && (
                <div>
                  <h4 style={{ color: '#22c55e', margin: '0 0 10px 0' }}>✅ Points forts</h4>
                  <ul style={{ margin: 0, paddingLeft: '20px', color: '#475569' }}>
                    {(car.analysis?.qualites || car.qualites).slice(0, 4).map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </div>
              )}
              {(car.analysis?.defauts?.length > 0 || car.defauts?.length > 0) && (
                <div>
                  <h4 style={{ color: '#ef4444', margin: '0 0 10px 0' }}>⚠️ Points faibles</h4>
                  <ul style={{ margin: 0, paddingLeft: '20px', color: '#475569' }}>
                    {(car.analysis?.defauts || car.defauts).slice(0, 4).map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Lien externe */}
          {car.url && (
            <a
              href={car.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-block',
                padding: '15px 30px',
                background: '#3b82f6',
                color: 'white',
                borderRadius: '12px',
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: '1rem'
              }}
            >
              Voir l&apos;annonce originale ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// APP PRINCIPALE
// =============================================================================

function App() {
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ marque: '', modele: '' });
  const [selectedCar, setSelectedCar] = useState(null);

  // Chargement initial
  useEffect(() => {
    fetchVehicles();
  }, []);

  const fetchVehicles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (filters.marque) params.append('marque', filters.marque);
      if (filters.modele) params.append('modele', filters.modele);
      params.append('limit', '20');

      const response = await fetch(`/api/listings/search?${params}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          marque: filters.marque || undefined,
          modele: filters.modele || undefined,
          limit: 20
        })
      });

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}`);
      }

      const data = await response.json();
      setVehicles(data.listings || []);
    } catch (err) {
      console.error('Erreur fetch:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)'
    }}>
      <Navbar />
      
      {/* Contenu principal */}
      <main style={{ 
        paddingTop: '100px',
        paddingBottom: '40px',
        paddingLeft: '40px',
        paddingRight: '40px',
        maxWidth: '1400px',
        margin: '0 auto'
      }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <h1 style={{ 
            color: 'white', 
            fontSize: '2.5rem', 
            marginBottom: '10px' 
          }}>
            Trouvez votre véhicule idéal
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: '1.1rem' }}>
            Analyse IA basée sur les données réelles du marché
          </p>
        </div>

        {/* Recherche */}
        <SearchBar 
          filters={filters}
          setFilters={setFilters}
          onSearch={fetchVehicles}
          loading={loading}
        />

        {/* Erreur */}
        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#dc2626',
            padding: '16px',
            borderRadius: '12px',
            marginBottom: '20px'
          }}>
            ⚠️ Erreur: {error}
          </div>
        )}

        {/* Résultats */}
        {loading ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '60px',
            color: 'white'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: '20px' }}>⏳</div>
            <p>Chargement des véhicules...</p>
          </div>
        ) : vehicles.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '60px',
            color: 'rgba(255,255,255,0.7)'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: '20px' }}>🚗</div>
            <p>Aucun véhicule trouvé. Essayez une autre recherche.</p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '24px'
          }}>
            {vehicles.map((car, idx) => (
              <CarCard 
                key={car._id || idx} 
                car={car}
                onClick={(c) => setSelectedCar(c)}
              />
            ))}
          </div>
        )}

        {/* Stats */}
        {vehicles.length > 0 && (
          <div style={{ 
            textAlign: 'center', 
            marginTop: '30px',
            color: 'rgba(255,255,255,0.5)'
          }}>
            {vehicles.length} véhicule(s) affiché(s)
          </div>
        )}
      </main>

      {/* Modal détail */}
      {selectedCar && (
        <VehicleModal car={selectedCar} onClose={() => setSelectedCar(null)} />
      )}
    </div>
  );
}

export default App;
