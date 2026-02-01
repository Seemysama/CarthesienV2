#!/usr/bin/env python3
"""
Scraper pour fiches-auto.fr - Données techniques et pannes.

SOURCES DE DONNÉES:
- URL: https://www.fiches-auto.fr/essai-{marque}/essai-{id}-test-complet-{marque}-{modele}.php
- Données: Qualités/Défauts, Notes motorisations, Ventes historiques, Pannes récurrentes
- Volume estimé: ~1200 fiches techniques

ANTI-HALLUCINATION:
- Chaque donnée a son source_url traçable
- Données factuelles (ventes = chiffres officiels)

Auteur: Car-thesien Team
Version: 1.0.0
Date: 1 février 2026
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential


# =============================================================================
# DATA CLASSES - STRUCTURES TRAÇABLES
# =============================================================================

@dataclass
class NotesMotorisation:
    """Notes techniques par motorisation."""
    motorisation: str
    note_globale: Optional[float] = None
    note_technique: Optional[float] = None
    comportement_routier: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class VentesHistoriques:
    """Ventes par année."""
    annee: int
    ventes: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PanneRecurrente:
    """Une panne connue avec sa fréquence."""
    description: str
    categorie: str  # moteur, boite, electronique, suspension, autre
    frequence: Optional[str] = None  # "fréquent", "rare", "occasionnel"
    motorisations_concernees: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FicheTechnique:
    """Fiche technique complète d'un véhicule."""
    marque: str
    modele: str
    generation: Optional[str] = None
    annees: Optional[str] = None  # "2019-2025"
    
    # Qualités et défauts
    qualites: List[str] = field(default_factory=list)
    defauts: List[str] = field(default_factory=list)
    
    # Notes par motorisation
    notes_motorisations: List[NotesMotorisation] = field(default_factory=list)
    
    # Ventes historiques
    ventes_historiques: List[VentesHistoriques] = field(default_factory=list)
    total_ventes: int = 0
    
    # Pannes récurrentes
    pannes_recurrentes: List[PanneRecurrente] = field(default_factory=list)
    
    # Scores agrégés (calculés)
    score_fiabilite: Optional[float] = None
    score_global: Optional[float] = None
    
    # Traçabilité
    source_url: str = ""
    scrape_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'marque': self.marque,
            'modele': self.modele,
            'generation': self.generation,
            'annees': self.annees,
            'qualites': self.qualites,
            'defauts': self.defauts,
            'notes_motorisations': [n.to_dict() for n in self.notes_motorisations],
            'ventes_historiques': [v.to_dict() for v in self.ventes_historiques],
            'total_ventes': self.total_ventes,
            'pannes_recurrentes': [p.to_dict() for p in self.pannes_recurrentes],
            'score_fiabilite': self.score_fiabilite,
            'score_global': self.score_global,
            'source_url': self.source_url,
            'scrape_timestamp': self.scrape_timestamp,
            '_source': {
                'id': 'fiches_auto_fr',
                'name': 'Fiches-Auto.fr',
                'url': 'https://www.fiches-auto.fr',
                'confidence': 'verified_scrape',
            }
        }


# =============================================================================
# SCRAPER PRINCIPAL
# =============================================================================

class FichesAutoScraper:
    """
    Scraper pour fiches-auto.fr - données techniques et pannes.
    
    Usage:
        scraper = FichesAutoScraper()
        data = scraper.scrape_fiche("peugeot", "308")
        scraper.save_to_json(data, "peugeot_308.json")
    """
    
    BASE_URL = "https://www.fiches-auto.fr"
    INDEX_URL = "https://www.fiches-auto.fr/tests/index-modeles.php"  # Liste des modèles
    
    def __init__(self, rate_limit: float = 2.0):
        """
        Args:
            rate_limit: Délai minimum entre requêtes (secondes)
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            timeout=30.0,
            follow_redirects=True
        )
    
    def _rate_limit_wait(self):
        """Respecte le rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch(self, url: str) -> httpx.Response:
        """Fetch avec retry et rate limiting."""
        self._rate_limit_wait()
        print(f"  📥 Fetching: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response
    
    def discover_fiches(self, marque: str) -> List[Dict[str, str]]:
        """
        Découvre toutes les fiches disponibles pour une marque.
        
        Returns:
            Liste de {url, marque, modele, titre}
        """
        # URL pattern: /essai-{marque}/
        index_url = f"{self.BASE_URL}/essai-{marque.lower()}/"
        print(f"\n🔍 Découverte des fiches pour {marque.upper()}...")
        
        try:
            response = self._fetch(index_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            fiches = []
            
            # Chercher tous les liens vers les essais
            links = soup.find_all('a', href=re.compile(r'essai-\d+-test-complet'))
            
            for link in links:
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                # Parser l'URL pour extraire le modèle
                match = re.search(r'essai-(\d+)-test-complet-(\w+)-(.+?)\.php', href)
                if match:
                    fiches.append({
                        'url': urljoin(self.BASE_URL, href),
                        'id': match.group(1),
                        'marque': match.group(2),
                        'modele': match.group(3).replace('-', ' '),
                        'titre': title,
                    })
            
            print(f"   ✅ {len(fiches)} fiches trouvées pour {marque}")
            return fiches
            
        except Exception as e:
            print(f"   ❌ Erreur découverte {marque}: {e}")
            return []
    
    def scrape_fiche(self, url: str = None, marque: str = None, modele: str = None) -> FicheTechnique:
        """
        Scrape une fiche technique complète.
        
        Args:
            url: URL directe de la fiche
            marque/modele: Pour construire l'URL si pas fournie
        """
        if not url and marque and modele:
            # Chercher l'URL via découverte
            fiches = self.discover_fiches(marque)
            matching = [f for f in fiches if modele.lower() in f['modele'].lower()]
            if matching:
                url = matching[0]['url']
            else:
                print(f"   ❌ Aucune fiche trouvée pour {marque} {modele}")
                return FicheTechnique(marque=marque, modele=modele)
        
        if not url:
            raise ValueError("URL ou marque/modele requis")
        
        print(f"\n🚗 Scraping fiche: {url}")
        
        try:
            response = self._fetch(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire marque/modele depuis URL ou titre
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else ""
            
            marque_extracted = marque or self._extract_marque(url, title_text)
            modele_extracted = modele or self._extract_modele(url, title_text)
            
            fiche = FicheTechnique(
                marque=marque_extracted.capitalize(),
                modele=modele_extracted.upper(),
                source_url=url,
            )
            
            # Extraire les données
            fiche.qualites, fiche.defauts = self._extract_qualites_defauts(soup)
            fiche.notes_motorisations = self._extract_notes_motorisations(soup)
            fiche.ventes_historiques = self._extract_ventes(soup)
            fiche.total_ventes = sum(v.ventes for v in fiche.ventes_historiques)
            fiche.pannes_recurrentes = self._extract_pannes(soup)
            fiche.annees = self._extract_annees(soup, title_text)
            
            # Calculer scores
            fiche.score_fiabilite = self._calculate_fiabilite_score(fiche)
            fiche.score_global = self._calculate_global_score(fiche)
            
            print(f"   ✅ Fiche extraite: {len(fiche.qualites)} qualités, {len(fiche.defauts)} défauts")
            print(f"      {len(fiche.notes_motorisations)} motorisations, {len(fiche.ventes_historiques)} années de ventes")
            print(f"      {len(fiche.pannes_recurrentes)} pannes identifiées")
            
            return fiche
            
        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP Error {e.response.status_code}")
            return FicheTechnique(marque=marque or "", modele=modele or "", source_url=url)
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            raise
    
    def _extract_marque(self, url: str, title: str) -> str:
        """Extrait la marque depuis l'URL ou le titre."""
        match = re.search(r'essai-(\w+)/', url)
        if match:
            return match.group(1)
        
        # Sinon depuis le titre
        marques_connues = ['peugeot', 'renault', 'citroen', 'dacia', 'volkswagen', 'bmw', 'audi', 'mercedes', 'toyota', 'hyundai', 'kia']
        for marque in marques_connues:
            if marque in title.lower():
                return marque
        
        return "inconnu"
    
    def _extract_modele(self, url: str, title: str) -> str:
        """Extrait le modèle depuis l'URL ou le titre."""
        match = re.search(r'test-complet-\w+-(.+?)\.php', url)
        if match:
            return match.group(1).replace('-', ' ')
        
        return "inconnu"
    
    def _extract_annees(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extrait la période de production."""
        # Pattern: "(2019-2025)" ou "(2019-)"
        match = re.search(r'\((\d{4})\s*-\s*(\d{4}|)\)', title)
        if match:
            debut = match.group(1)
            fin = match.group(2) or "présent"
            return f"{debut}-{fin}"
        
        return None
    
    def _extract_qualites_defauts(self, soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
        """
        Extrait les qualités et défauts depuis la section #plus_et_moins.
        
        Structure HTML fiches-auto.fr:
        - Container: div#plus_et_moins
        - Images: les-plus.gif (qualités) / les-moins.gif (défauts)
        - Textes: éléments sans classe, parsés séquentiellement
        - Séparateur: "L'avis des internautes" entre expert et utilisateurs
        """
        qualites = []
        defauts = []
        
        # Méthode 1: Chercher le container #plus_et_moins (structure fiches-auto.fr)
        container = soup.find(id='plus_et_moins')
        
        if container:
            # Parser le contenu du container
            qualites, defauts = self._parse_plus_moins_container(container)
        
        # Méthode 2: Fallback - chercher des sections avec classes
        if not qualites and not defauts:
            qualites_section = soup.find_all(['div', 'ul', 'section'], class_=re.compile(r'qualit|avantage|plus|green', re.I))
            defauts_section = soup.find_all(['div', 'ul', 'section'], class_=re.compile(r'defaut|inconvenient|moins|red', re.I))
            
            for section in qualites_section:
                items = section.find_all('li')
                if items:
                    qualites.extend([li.get_text(strip=True) for li in items if li.get_text(strip=True)])
            
            for section in defauts_section:
                items = section.find_all('li')
                if items:
                    defauts.extend([li.get_text(strip=True) for li in items if li.get_text(strip=True)])
        
        # Méthode 3: Fallback - parser le texte brut
        if not qualites and not defauts:
            qualites, defauts = self._parse_qualites_defauts_text(soup)
        
        return qualites, defauts
    
    def _parse_plus_moins_container(self, container) -> Tuple[List[str], List[str]]:
        """
        Parse le container #plus_et_moins de fiches-auto.fr.
        
        Structure:
        - Section Qualités (gauche): img les-plus.gif + textes
        - Section Défauts (droite): img les-moins.gif + textes
        - Séparateur: "L'avis des internautes"
        """
        qualites_expert = []
        qualites_user = []
        defauts_expert = []
        defauts_user = []
        
        # Extraire tout le texte avec structure
        all_text = container.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in all_text.split('\n') if l.strip()]
        
        # Trouver l'index du titre "Défauts" pour séparer les sections
        defauts_start_idx = None
        for i, line in enumerate(lines):
            if line.lower() in ['défauts', 'defauts']:
                defauts_start_idx = i
                break
        
        # Si on a trouvé le séparateur "Défauts", diviser les lignes
        if defauts_start_idx:
            qualites_lines = lines[:defauts_start_idx]
            defauts_lines = lines[defauts_start_idx:]
        else:
            qualites_lines = lines
            defauts_lines = []
        
        # Parser les qualités
        current_section = 'expert'
        for line in qualites_lines:
            if len(line) < 15:
                continue
            
            if "l'avis des internautes" in line.lower():
                current_section = 'user'
                continue
            
            if line.lower() in ['qualités', 'qualites']:
                continue
            
            # Ignorer les lignes de navigation
            if 'toutes les autres' in line.lower() or 'signalé' in line.lower():
                continue
            
            # Ignorer les infos moteur seules
            if re.match(r'^\([^)]+\)$', line):
                continue
            
            if current_section == 'expert' and len(line) > 40:
                qualites_expert.append(line)
            elif current_section == 'user' and len(line) > 15:
                if not re.match(r'^\([^)]+\)$', line):
                    qualites_user.append(line)
        
        # Parser les défauts
        current_section = 'expert'
        for line in defauts_lines:
            if len(line) < 15:
                continue
            
            if "l'avis des internautes" in line.lower():
                current_section = 'user'
                continue
            
            if line.lower() in ['défauts', 'defauts']:
                continue
            
            if 'toutes les autres' in line.lower() or 'signalé' in line.lower():
                continue
            
            if re.match(r'^\([^)]+\)$', line):
                continue
            
            if current_section == 'expert' and len(line) > 40:
                defauts_expert.append(line)
            elif current_section == 'user' and len(line) > 15:
                if not re.match(r'^\([^)]+\)$', line):
                    defauts_user.append(line)
        
        # Méthode alternative: parser via les images
        imgs = container.find_all('img')
        
        for img in imgs:
            src = img.get('src', '')
            
            # Trouver le texte suivant l'image
            next_sibling = img.find_next_sibling(text=True)
            if next_sibling:
                text = next_sibling.strip()
            else:
                # Essayer le parent
                parent = img.parent
                if parent:
                    next_elem = parent.find_next_sibling()
                    if next_elem:
                        text = next_elem.get_text(strip=True)
                    else:
                        continue
                else:
                    continue
            
            if text and len(text) > 20 and not re.match(r'^\([^)]+\)$', text):
                if 'les-plus' in src or 'plus.gif' in src:
                    if text not in qualites_user and text not in qualites_expert:
                        qualites_user.append(text)
                elif 'les-moins' in src or 'moins.gif' in src:
                    if text not in defauts_user and text not in defauts_expert:
                        defauts_user.append(text)
        
        # Combiner expert + utilisateurs
        qualites = qualites_expert + qualites_user
        defauts = defauts_expert + defauts_user
        
        # Dédupliquer tout en gardant l'ordre
        seen_qual = set()
        unique_qualites = []
        for q in qualites:
            q_clean = q[:100]  # Comparer sur les 100 premiers chars
            if q_clean not in seen_qual:
                seen_qual.add(q_clean)
                unique_qualites.append(q)
        
        seen_def = set()
        unique_defauts = []
        for d in defauts:
            d_clean = d[:100]
            if d_clean not in seen_def:
                seen_def.add(d_clean)
                unique_defauts.append(d)
        
        # Nettoyer
        unique_qualites = [q for q in unique_qualites if len(q) > 15 and not q.startswith('(')]
        unique_defauts = [d for d in unique_defauts if len(d) > 15 and not d.startswith('(')]
        
        return unique_qualites[:25], unique_defauts[:25]
    
    def _parse_qualites_defauts_text(self, soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
        """Fallback: parse le texte brut pour trouver qualités/défauts."""
        qualites = []
        defauts = []
        
        text = soup.get_text()
        
        # Pattern après "Qualités" ou "Points forts"
        qual_match = re.search(
            r'(?:Qualités?|Points?\s+forts?)\s*:?\s*(.+?)(?=Défauts?|Points?\s+faibles?|L\'avis|$)', 
            text, re.I | re.S
        )
        if qual_match:
            items = re.split(r'[\n•\-✓✔]', qual_match.group(1))
            qualites = [i.strip() for i in items if i.strip() and len(i.strip()) > 20][:15]
        
        # Pattern après "Défauts" ou "Points faibles"
        def_match = re.search(
            r'(?:Défauts?|Points?\s+faibles?)\s*:?\s*(.+?)(?=Qualités?|Points?\s+forts?|L\'avis|$)', 
            text, re.I | re.S
        )
        if def_match:
            items = re.split(r'[\n•\-✗✘]', def_match.group(1))
            defauts = [i.strip() for i in items if i.strip() and len(i.strip()) > 20][:15]
        
        return qualites, defauts
    
    def _extract_notes_motorisations(self, soup: BeautifulSoup) -> List[NotesMotorisation]:
        """Extrait les notes par motorisation."""
        notes = []
        
        # Chercher un tableau de notes
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # Première cellule = motorisation, autres = notes
                    moto_text = cells[0].get_text(strip=True)
                    
                    # Vérifier que ça ressemble à une motorisation
                    if re.search(r'\d+\.?\d*[Ll]|\d+\s*ch|\d+\s*kW|HDi|TDI|TSI|BlueHDi|PureTech|TCe|dCi', moto_text, re.I):
                        note = NotesMotorisation(motorisation=moto_text)
                        
                        # Chercher des notes dans les autres cellules
                        for cell in cells[1:]:
                            cell_text = cell.get_text(strip=True)
                            note_match = re.search(r'(\d+(?:[.,]\d+)?)\s*/?\s*(?:10|20)?', cell_text)
                            if note_match:
                                value = float(note_match.group(1).replace(',', '.'))
                                if value <= 10:
                                    note.note_globale = value
                                elif value <= 20:
                                    note.note_globale = value / 2  # Normaliser sur 10
                        
                        if note.note_globale:
                            notes.append(note)
        
        # Méthode alternative: chercher dans le texte
        if not notes:
            text = soup.get_text()
            
            # Pattern: "1.2 PureTech : 7.5/10"
            pattern = r'(\d+\.?\d*[Ll]?\s*[A-Za-z]+\s*\d*\s*ch?)\s*:?\s*(\d+(?:[.,]\d+)?)\s*/\s*(?:10|20)'
            matches = re.findall(pattern, text, re.I)
            
            for moto, note_val in matches:
                value = float(note_val.replace(',', '.'))
                if value > 10:
                    value = value / 2
                notes.append(NotesMotorisation(motorisation=moto.strip(), note_globale=value))
        
        return notes
    
    def _extract_ventes(self, soup: BeautifulSoup) -> List[VentesHistoriques]:
        """Extrait les ventes historiques par année."""
        ventes = []
        
        # Chercher un tableau avec des années
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            # Chercher une ligne avec des années (2008, 2009, ...)
            annees_row = None
            ventes_row = None
            
            for row in rows:
                cells_text = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                
                # Vérifier si c'est une ligne d'années
                annees_found = [c for c in cells_text if re.match(r'^20\d{2}$', c)]
                if len(annees_found) >= 3:
                    annees_row = cells_text
                    continue
                
                # Vérifier si c'est une ligne de ventes (chiffres avec K ou M)
                if annees_row:
                    ventes_found = [c for c in cells_text if re.search(r'\d+[.,]?\d*\s*[KMk]?', c)]
                    if len(ventes_found) >= 3:
                        ventes_row = cells_text
                        break
            
            if annees_row and ventes_row:
                for i, annee_str in enumerate(annees_row):
                    if re.match(r'^20\d{2}$', annee_str) and i < len(ventes_row):
                        vente_str = ventes_row[i]
                        
                        # Parser le nombre de ventes
                        vente_val = self._parse_ventes_number(vente_str)
                        if vente_val > 0:
                            ventes.append(VentesHistoriques(
                                annee=int(annee_str),
                                ventes=vente_val
                            ))
        
        return sorted(ventes, key=lambda v: v.annee)
    
    def _parse_ventes_number(self, text: str) -> int:
        """Parse un nombre de ventes (82.1K, 1.2M, etc.)."""
        text = text.strip().upper()
        
        # Pattern: 82.1K, 1.2M, 82100
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*([KMkm])?', text)
        if match:
            value = float(match.group(1).replace(',', '.'))
            multiplier = match.group(2)
            
            if multiplier in ['K', 'k']:
                value *= 1000
            elif multiplier in ['M', 'm']:
                value *= 1000000
            
            return int(value)
        
        return 0
    
    def _extract_pannes(self, soup: BeautifulSoup) -> List[PanneRecurrente]:
        """Extrait les pannes récurrentes."""
        pannes = []
        
        # Chercher une section "Pannes" ou "Problèmes"
        pannes_sections = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'panne|probleme|defaut|issue', re.I))
        
        # Mots-clés pour catégoriser les pannes
        categories = {
            'moteur': ['moteur', 'engine', 'turbo', 'injection', 'courroie', 'distribution', 'puretech', 'tce', 'dci'],
            'boite': ['boîte', 'boite', 'bva', 'embrayage', 'clutch', 'transmission', 'eat', 'dct'],
            'electronique': ['électronique', 'electronique', 'capteur', 'sensor', 'écran', 'gps', 'multimedia', 'batterie', 'bsi'],
            'suspension': ['suspension', 'amortisseur', 'silent', 'bloc', 'triangle', 'rotule'],
            'freinage': ['frein', 'brake', 'plaquette', 'disque'],
        }
        
        for section in pannes_sections:
            items = section.find_all('li')
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 10:
                    # Déterminer la catégorie
                    cat = 'autre'
                    text_lower = text.lower()
                    for cat_name, keywords in categories.items():
                        if any(kw in text_lower for kw in keywords):
                            cat = cat_name
                            break
                    
                    pannes.append(PanneRecurrente(
                        description=text,
                        categorie=cat,
                    ))
        
        # Méthode alternative: chercher dans le texte global
        if not pannes:
            text = soup.get_text()
            
            # Pattern: "problème de XXX", "panne de XXX"
            pattern = r'(?:problème|panne|défaut|souci)\s+(?:de\s+)?([^.]+)'
            matches = re.findall(pattern, text, re.I)
            
            for match in matches[:10]:
                # Catégoriser
                cat = 'autre'
                match_lower = match.lower()
                for cat_name, keywords in categories.items():
                    if any(kw in match_lower for kw in keywords):
                        cat = cat_name
                        break
                
                pannes.append(PanneRecurrente(
                    description=match.strip()[:200],
                    categorie=cat,
                ))
        
        return pannes
    
    def _calculate_fiabilite_score(self, fiche: FicheTechnique) -> float:
        """Calcule un score de fiabilité basé sur les pannes et défauts."""
        base_score = 8.0  # Score de base
        
        # Pénalités par nombre de pannes
        nb_pannes = len(fiche.pannes_recurrentes)
        if nb_pannes > 10:
            base_score -= 2.0
        elif nb_pannes > 5:
            base_score -= 1.0
        elif nb_pannes > 2:
            base_score -= 0.5
        
        # Pénalités par catégorie critique
        for panne in fiche.pannes_recurrentes:
            if panne.categorie == 'moteur':
                base_score -= 0.3
            elif panne.categorie == 'boite':
                base_score -= 0.2
        
        # Bonus si peu de défauts
        if len(fiche.defauts) < 3:
            base_score += 0.5
        
        return max(0.0, min(10.0, base_score))
    
    def _calculate_global_score(self, fiche: FicheTechnique) -> float:
        """Calcule un score global."""
        scores = []
        
        # Score fiabilité
        if fiche.score_fiabilite:
            scores.append(fiche.score_fiabilite)
        
        # Moyenne des notes motorisations
        if fiche.notes_motorisations:
            avg_moto = sum(n.note_globale or 0 for n in fiche.notes_motorisations) / len(fiche.notes_motorisations)
            scores.append(avg_moto)
        
        # Ratio qualités/défauts
        if fiche.qualites or fiche.defauts:
            ratio = len(fiche.qualites) / max(1, len(fiche.qualites) + len(fiche.defauts))
            scores.append(ratio * 10)
        
        if scores:
            return round(sum(scores) / len(scores), 1)
        
        return 7.0  # Score par défaut
    
    def save_to_json(self, data: FicheTechnique, filename: str):
        """Sauvegarde en JSON."""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        
        print(f"   💾 Sauvegardé: {filename}")
    
    def save_to_mongodb(self, data: FicheTechnique, collection_name: str = "fiches_auto"):
        """Sauvegarde dans MongoDB."""
        try:
            from pymongo import MongoClient
            
            client = MongoClient("mongodb://localhost:27017")
            db = client["carthesienDB"]
            collection = db[collection_name]
            
            filter_query = {
                'marque': data.marque,
                'modele': data.modele,
            }
            
            result = collection.update_one(
                filter_query,
                {'$set': data.to_dict()},
                upsert=True
            )
            
            action = "inserted" if result.upserted_id else "updated"
            print(f"   🗄️ MongoDB: {action} ({collection_name})")
            
            client.close()
            
        except Exception as e:
            print(f"   ❌ MongoDB error: {e}")
    
    def close(self):
        """Ferme le client HTTP."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# =============================================================================
# LISTE DES MARQUES À SCRAPER
# =============================================================================

MARQUES_FR = [
    "peugeot",
    "renault",
    "citroen",
    "dacia",
]

MARQUES_ALL = [
    "peugeot", "renault", "citroen", "dacia",
    "volkswagen", "audi", "bmw", "mercedes",
    "toyota", "honda", "mazda", "nissan",
    "hyundai", "kia",
    "fiat", "alfa-romeo",
    "volvo", "seat", "skoda",
    "ford", "opel",
]


# =============================================================================
# CLI - POINT D'ENTRÉE
# =============================================================================

def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scraper fiches-auto.fr")
    parser.add_argument("--marque", type=str, help="Marque à scraper")
    parser.add_argument("--modele", type=str, help="Modèle spécifique")
    parser.add_argument("--url", type=str, help="URL directe de la fiche")
    parser.add_argument("--all-fr", action="store_true", help="Scraper toutes les marques françaises")
    parser.add_argument("--all", action="store_true", help="Scraper toutes les marques")
    parser.add_argument("--discover", action="store_true", help="Découvrir les fiches d'une marque")
    parser.add_argument("--output", type=str, default="data/fiches_auto", help="Dossier de sortie")
    parser.add_argument("--mongodb", action="store_true", help="Sauvegarder dans MongoDB")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="Délai entre requêtes (sec)")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with FichesAutoScraper(rate_limit=args.rate_limit) as scraper:
        
        if args.discover and args.marque:
            # Mode découverte
            fiches = scraper.discover_fiches(args.marque)
            print(f"\n📋 Fiches trouvées pour {args.marque.upper()}:")
            for f in fiches:
                print(f"   - {f['titre']}: {f['url']}")
            
        elif args.url:
            # Scraper une URL directe
            data = scraper.scrape_fiche(url=args.url)
            filename = f"{data.marque.lower()}_{data.modele.lower().replace(' ', '_')}.json"
            scraper.save_to_json(data, output_dir / filename)
            
            if args.mongodb:
                scraper.save_to_mongodb(data)
            
        elif args.marque and args.modele:
            # Scraper un modèle spécifique
            data = scraper.scrape_fiche(marque=args.marque, modele=args.modele)
            filename = f"{args.marque.lower()}_{args.modele.lower().replace(' ', '_')}.json"
            scraper.save_to_json(data, output_dir / filename)
            
            if args.mongodb:
                scraper.save_to_mongodb(data)
            
        elif args.marque:
            # Scraper tous les modèles d'une marque
            fiches = scraper.discover_fiches(args.marque)
            
            print(f"\n🚀 Scraping de {len(fiches)} fiches {args.marque.upper()}...\n")
            
            for fiche_info in fiches:
                try:
                    data = scraper.scrape_fiche(url=fiche_info['url'])
                    filename = f"{data.marque.lower()}_{data.modele.lower().replace(' ', '_')}.json"
                    scraper.save_to_json(data, output_dir / filename)
                    
                    if args.mongodb:
                        scraper.save_to_mongodb(data)
                        
                except Exception as e:
                    print(f"   ❌ Erreur {fiche_info['titre']}: {e}")
            
        elif args.all_fr:
            # Scraper marques françaises
            for marque in MARQUES_FR:
                fiches = scraper.discover_fiches(marque)
                
                for fiche_info in fiches:
                    try:
                        data = scraper.scrape_fiche(url=fiche_info['url'])
                        filename = f"{data.marque.lower()}_{data.modele.lower().replace(' ', '_')}.json"
                        scraper.save_to_json(data, output_dir / filename)
                        
                        if args.mongodb:
                            scraper.save_to_mongodb(data)
                            
                    except Exception as e:
                        print(f"   ❌ Erreur {fiche_info['titre']}: {e}")
            
        elif args.all:
            # Scraper toutes les marques
            for marque in MARQUES_ALL:
                fiches = scraper.discover_fiches(marque)
                
                for fiche_info in fiches:
                    try:
                        data = scraper.scrape_fiche(url=fiche_info['url'])
                        filename = f"{data.marque.lower()}_{data.modele.lower().replace(' ', '_')}.json"
                        scraper.save_to_json(data, output_dir / filename)
                        
                        if args.mongodb:
                            scraper.save_to_mongodb(data)
                            
                    except Exception as e:
                        print(f"   ❌ Erreur {fiche_info['titre']}: {e}")
            
        else:
            # Mode test
            print("\n🧪 Mode test: Découverte Peugeot\n")
            fiches = scraper.discover_fiches("peugeot")
            
            if fiches:
                # Scraper la première fiche
                data = scraper.scrape_fiche(url=fiches[0]['url'])
                scraper.save_to_json(data, output_dir / "test_peugeot.json")
                
                print("\n📋 Aperçu des données:")
                print(json.dumps(data.to_dict(), ensure_ascii=False, indent=2)[:2000] + "...")


if __name__ == "__main__":
    main()
