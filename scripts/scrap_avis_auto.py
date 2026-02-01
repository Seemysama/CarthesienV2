#!/usr/bin/env python3
"""
Scraper pour avis-auto.fr - Avis utilisateurs vérifiés.

SOURCES DE DONNÉES:
- URL: https://www.avis-auto.fr/avis-{marque}-{modele}-{generation}
- Données: Scores moyens + avis individuels détaillés
- Volume estimé: 50-100K avis sur ~500 modèles

ANTI-HALLUCINATION:
- Chaque avis a son source_url traçable
- Anonymisation RGPD des pseudos (SHA256)
- Timestamps de scraping

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
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential


# =============================================================================
# DATA CLASSES - STRUCTURES ANTI-HALLUCINATION
# =============================================================================

@dataclass
class ScoresMoyens:
    """Scores moyens du véhicule (sur 5)."""
    confort: Optional[float] = None
    consommation: Optional[float] = None
    securite: Optional[float] = None
    cout_entretien: Optional[float] = None
    habitabilite: Optional[float] = None
    fiabilite: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_scale_10(self) -> Dict[str, float]:
        """Convertit les scores /5 en /10 pour uniformité."""
        return {k: round(v * 2, 1) for k, v in self.to_dict().items()}


@dataclass
class AvisIndividuel:
    """Un avis utilisateur avec traçabilité complète."""
    # Identifiant unique
    avis_id: str
    
    # Note et contenu
    note: float  # /5
    titre: Optional[str] = None
    avantages: Optional[str] = None
    inconvenients: Optional[str] = None
    
    # Métadonnées auteur (anonymisé)
    auteur_hash: Optional[str] = None  # SHA256 du pseudo
    date_avis: Optional[str] = None  # "janvier 2026"
    
    # Contexte véhicule
    annee_vehicule: Optional[str] = None  # "Janvier 2024"
    carburant: Optional[str] = None
    boite: Optional[str] = None
    motorisation: Optional[str] = None
    
    # Traçabilité ANTI-HALLUCINATION
    source_url: Optional[str] = None
    scrape_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VehiculeAvisAuto:
    """Données complètes d'un véhicule scrappé."""
    marque: str
    modele: str
    generation: Optional[str] = None
    
    # Données agrégées
    nb_avis: int = 0
    scores_moyens: Optional[ScoresMoyens] = None
    avis: List[AvisIndividuel] = field(default_factory=list)
    
    # Traçabilité
    source_url: str = ""
    scrape_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            'marque': self.marque,
            'modele': self.modele,
            'generation': self.generation,
            'nb_avis': self.nb_avis,
            'scores_moyens': self.scores_moyens.to_dict() if self.scores_moyens else None,
            'scores_moyens_sur_10': self.scores_moyens.to_scale_10() if self.scores_moyens else None,
            'avis': [a.to_dict() for a in self.avis],
            'source_url': self.source_url,
            'scrape_timestamp': self.scrape_timestamp,
            '_source': {
                'id': 'avis_auto_fr',
                'name': 'Avis-Auto.fr',
                'url': 'https://www.avis-auto.fr',
                'confidence': 'verified_scrape',
            }
        }
        return data


# =============================================================================
# SCRAPER PRINCIPAL
# =============================================================================

class AvisAutoScraper:
    """
    Scraper pour avis-auto.fr avec pagination AJAX.
    
    Usage:
        scraper = AvisAutoScraper()
        data = scraper.scrape_vehicle("peugeot", "208", "2")
        scraper.save_to_json(data, "peugeot_208.json")
    """
    
    BASE_URL = "https://www.avis-auto.fr"
    
    # Labels des scores à extraire
    SCORE_LABELS = [
        "Confort", "Consommation", "Sécurité", 
        "Coût d'entretien", "Habitabilité", "Fiabilité"
    ]
    
    # Mapping labels -> attributs
    SCORE_MAPPING = {
        "confort": "confort",
        "consommation": "consommation",
        "sécurité": "securite",
        "securite": "securite",
        "coût d'entretien": "cout_entretien",
        "cout d'entretien": "cout_entretien",
        "habitabilité": "habitabilite",
        "habitabilite": "habitabilite",
        "fiabilité": "fiabilite",
        "fiabilite": "fiabilite",
    }
    
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
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
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
    
    @staticmethod
    def hash_pseudo(pseudo: str) -> str:
        """Anonymise un pseudo (RGPD compliance)."""
        if not pseudo:
            return "anonymous"
        return hashlib.sha256(pseudo.strip().encode('utf-8')).hexdigest()[:16]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch(self, url: str) -> httpx.Response:
        """Fetch avec retry et rate limiting."""
        self._rate_limit_wait()
        print(f"  📥 Fetching: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response
    
    def scrape_vehicle(self, marque: str, modele: str, generation: str = "") -> VehiculeAvisAuto:
        """
        Scrape toutes les données d'un véhicule.
        
        Args:
            marque: Marque (ex: "peugeot")
            modele: Modèle (ex: "208")
            generation: Génération (ex: "2")
            
        Returns:
            VehiculeAvisAuto avec toutes les données
        """
        # Construire l'URL
        slug = f"{marque.lower()}-{modele.lower()}"
        if generation:
            slug += f"-{generation}"
        
        url = f"{self.BASE_URL}/avis-{slug}"
        print(f"\n🚗 Scraping {marque.upper()} {modele.upper()} (gen {generation or 'all'})")
        print(f"   URL: {url}")
        
        try:
            response = self._fetch(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire les données
            scores = self._extract_scores(soup)
            meta = self._extract_meta(soup)
            avis_list = self._extract_avis(soup, url)
            
            vehicule = VehiculeAvisAuto(
                marque=marque.capitalize(),
                modele=modele.upper(),
                generation=generation or None,
                nb_avis=meta.get('nb_avis', len(avis_list)),
                scores_moyens=scores,
                avis=avis_list,
                source_url=url,
            )
            
            print(f"   ✅ {len(avis_list)} avis extraits")
            if scores:
                print(f"   📊 Scores: {scores.to_dict()}")
            
            return vehicule
            
        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP Error {e.response.status_code}: {url}")
            return VehiculeAvisAuto(
                marque=marque.capitalize(),
                modele=modele.upper(),
                generation=generation,
                source_url=url,
            )
        except Exception as e:
            print(f"   ❌ Error: {e}")
            raise
    
    def _extract_scores(self, soup: BeautifulSoup) -> Optional[ScoresMoyens]:
        """Extrait les scores moyens."""
        scores = ScoresMoyens()
        found_any = False
        
        # Méthode 1: Chercher par pattern de texte "Label" + "X/5"
        text_content = soup.get_text()
        
        for label in self.SCORE_LABELS:
            # Pattern: "Label" suivi de "X/5" ou "X.X/5"
            pattern = rf'{label}\s*[:\s]*(\d+(?:[.,]\d+)?)\s*/\s*5'
            match = re.search(pattern, text_content, re.IGNORECASE)
            
            if match:
                value = float(match.group(1).replace(',', '.'))
                attr_name = self.SCORE_MAPPING.get(label.lower())
                if attr_name:
                    setattr(scores, attr_name, value)
                    found_any = True
        
        # Méthode 2: Chercher dans des éléments structurés
        if not found_any:
            # Chercher tous les éléments qui pourraient contenir des scores
            score_containers = soup.find_all(['div', 'span', 'li'], class_=re.compile(r'score|note|rating', re.I))
            
            for container in score_containers:
                container_text = container.get_text()
                for label in self.SCORE_LABELS:
                    if label.lower() in container_text.lower():
                        match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*5', container_text)
                        if match:
                            value = float(match.group(1).replace(',', '.'))
                            attr_name = self.SCORE_MAPPING.get(label.lower())
                            if attr_name:
                                setattr(scores, attr_name, value)
                                found_any = True
        
        return scores if found_any else None
    
    def _extract_meta(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extrait les métadonnées (nombre d'avis, etc.)."""
        meta = {}
        
        # Chercher "XXX avis" dans le texte
        text = soup.get_text()
        patterns = [
            r'(\d+)\s+avis\s+client',
            r'(\d+)\s+avis',
            r'Total\s*:\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                meta['nb_avis'] = int(match.group(1))
                break
        
        return meta
    
    def _extract_avis(self, soup: BeautifulSoup, source_url: str) -> List[AvisIndividuel]:
        """Extrait tous les avis individuels."""
        avis_list = []
        
        # Méthode 1: Chercher les <li> avec id="Collecte_XXXX"
        collecte_items = soup.find_all('li', id=re.compile(r'^Collecte_\d+'))
        
        if collecte_items:
            for item in collecte_items:
                avis = self._parse_collecte_item(item, source_url)
                if avis:
                    avis_list.append(avis)
        
        # Méthode 2: Chercher une structure alternative
        if not avis_list:
            # Chercher des divs/articles qui ressemblent à des avis
            avis_containers = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'avis|review|opinion', re.I))
            
            for i, container in enumerate(avis_containers):
                avis = self._parse_generic_avis(container, source_url, i)
                if avis:
                    avis_list.append(avis)
        
        # Méthode 3: Parser le HTML brut si structure non standard
        if not avis_list:
            avis_list = self._parse_raw_html(soup, source_url)
        
        return avis_list
    
    def _parse_collecte_item(self, item, source_url: str) -> Optional[AvisIndividuel]:
        """Parse un élément <li id="Collecte_XXXX">."""
        try:
            avis_id = item.get('id', f'avis_{int(time.time() * 1000)}')
            text_content = item.get_text(separator='\n', strip=True)
            lines = [l.strip() for l in text_content.split('\n') if l.strip()]
            
            avis = AvisIndividuel(
                avis_id=avis_id,
                note=0.0,
                source_url=source_url,
            )
            
            # Extraire la note (X / 5)
            note_match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*5', text_content)
            if note_match:
                avis.note = float(note_match.group(1).replace(',', '.'))
            
            # Extraire auteur et date ("Rédigé par XXX, en MMMM YYYY")
            author_match = re.search(r'[Rr]édigé\s+par\s+([^,]+),?\s*(?:en\s+)?(\w+\s+\d{4})?', text_content)
            if author_match:
                avis.auteur_hash = self.hash_pseudo(author_match.group(1))
                if author_match.group(2):
                    avis.date_avis = author_match.group(2)
            
            # Extraire infos véhicule
            # Année véhicule (pattern: "Janvier 2024")
            year_match = re.search(r'((?:Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre)\s+\d{4})', text_content, re.IGNORECASE)
            if year_match:
                avis.annee_vehicule = year_match.group(1)
            
            # Carburant
            fuel_match = re.search(r'(Essence|Diesel|Hybride|Électrique|GPL|E85)', text_content, re.IGNORECASE)
            if fuel_match:
                avis.carburant = fuel_match.group(1).capitalize()
            
            # Boîte
            gearbox_match = re.search(r'(Manuelle|Automatique|Auto|BVA|CVT)', text_content, re.IGNORECASE)
            if gearbox_match:
                avis.boite = gearbox_match.group(1).capitalize()
            
            # Motorisation
            motor_match = re.search(r'(\d+(?:\.\d+)?[Ll]?\s*-?\s*\d+\s*ch)', text_content, re.IGNORECASE)
            if motor_match:
                avis.motorisation = motor_match.group(1)
            
            # Avantages / Inconvénients
            # Chercher après "Avantages" et avant "Inconvénients"
            adv_match = re.search(r'Avantages?\s*:?\s*([^I]+?)(?=Inconvénients?|$)', text_content, re.IGNORECASE | re.DOTALL)
            if adv_match:
                avis.avantages = adv_match.group(1).strip()
            
            disadv_match = re.search(r'Inconvénients?\s*:?\s*(.+?)$', text_content, re.IGNORECASE | re.DOTALL)
            if disadv_match:
                avis.inconvenients = disadv_match.group(1).strip()
            
            # Titre (souvent la première ligne courte après la note)
            for line in lines:
                if len(line) > 5 and len(line) < 100 and not re.search(r'\d/5|Rédigé|Avantage|Inconvénient', line, re.I):
                    avis.titre = line
                    break
            
            return avis
            
        except Exception as e:
            print(f"     ⚠️ Erreur parsing avis: {e}")
            return None
    
    def _parse_generic_avis(self, container, source_url: str, index: int) -> Optional[AvisIndividuel]:
        """Parse un conteneur d'avis générique."""
        try:
            text = container.get_text(separator=' ', strip=True)
            
            # Vérifier que c'est bien un avis (contient une note)
            note_match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*(?:5|10)', text)
            if not note_match:
                return None
            
            note = float(note_match.group(1).replace(',', '.'))
            if '/10' in text:
                note = note / 2  # Normaliser sur 5
            
            return AvisIndividuel(
                avis_id=f"avis_{index}_{int(time.time())}",
                note=note,
                source_url=source_url,
            )
            
        except Exception:
            return None
    
    def _parse_raw_html(self, soup: BeautifulSoup, source_url: str) -> List[AvisIndividuel]:
        """Fallback: parse le HTML brut pour trouver des patterns d'avis."""
        avis_list = []
        
        # Chercher tous les patterns "X/5" dans le texte
        all_text = soup.get_text()
        
        # Diviser par avis (pattern: une note suivie de contenu)
        avis_blocks = re.split(r'(?=\b\d+(?:[.,]\d+)?\s*/\s*5\b)', all_text)
        
        for i, block in enumerate(avis_blocks):
            if not block.strip():
                continue
            
            note_match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*5', block)
            if note_match:
                avis = AvisIndividuel(
                    avis_id=f"raw_{i}_{int(time.time())}",
                    note=float(note_match.group(1).replace(',', '.')),
                    source_url=source_url,
                )
                avis_list.append(avis)
        
        return avis_list[:50]  # Limiter pour éviter les faux positifs
    
    def save_to_json(self, data: VehiculeAvisAuto, filename: str):
        """Sauvegarde les données en JSON."""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        
        print(f"   💾 Sauvegardé: {filename}")
    
    def save_to_mongodb(self, data: VehiculeAvisAuto, collection_name: str = "avis_auto"):
        """Sauvegarde dans MongoDB."""
        try:
            from pymongo import MongoClient
            
            client = MongoClient("mongodb://localhost:27017")
            db = client["carthesienDB"]
            collection = db[collection_name]
            
            # Upsert par marque/modele/generation
            filter_query = {
                'marque': data.marque,
                'modele': data.modele,
                'generation': data.generation,
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
# LISTE DES MODÈLES À SCRAPER
# =============================================================================

MODELS_TO_SCRAPE = [
    # Françaises
    ("peugeot", "208", "2"),
    ("peugeot", "308", "3"),
    ("peugeot", "3008", "2"),
    ("peugeot", "2008", "2"),
    ("peugeot", "5008", "2"),
    ("renault", "clio", "5"),
    ("renault", "captur", "2"),
    ("renault", "megane", "4"),
    ("renault", "arkana", ""),
    ("renault", "austral", ""),
    ("citroen", "c3", "3"),
    ("citroen", "c3-aircross", ""),
    ("citroen", "c4", "3"),
    ("citroen", "c5-aircross", ""),
    ("dacia", "sandero", "3"),
    ("dacia", "duster", "3"),
    ("dacia", "jogger", ""),
    ("dacia", "spring", ""),
    
    # Allemandes
    ("volkswagen", "golf", "8"),
    ("volkswagen", "polo", "6"),
    ("volkswagen", "tiguan", "2"),
    ("volkswagen", "t-roc", ""),
    ("bmw", "serie-1", "3"),
    ("bmw", "serie-3", "7"),
    ("bmw", "x1", "2"),
    ("bmw", "x3", "3"),
    ("audi", "a3", "4"),
    ("audi", "a4", "5"),
    ("audi", "q3", "2"),
    ("audi", "q5", "2"),
    ("mercedes", "classe-a", "4"),
    ("mercedes", "classe-c", "5"),
    ("mercedes", "glc", "2"),
    
    # Japonaises
    ("toyota", "yaris", "4"),
    ("toyota", "corolla", "12"),
    ("toyota", "c-hr", "2"),
    ("toyota", "rav4", "5"),
    ("honda", "civic", "11"),
    ("honda", "hr-v", "2"),
    ("mazda", "3", "4"),
    ("mazda", "cx-30", ""),
    ("mazda", "cx-5", "2"),
    ("nissan", "qashqai", "3"),
    ("nissan", "juke", "2"),
    
    # Coréennes
    ("hyundai", "tucson", "4"),
    ("hyundai", "kona", "2"),
    ("hyundai", "i20", "3"),
    ("kia", "sportage", "5"),
    ("kia", "niro", "2"),
    ("kia", "ceed", "3"),
    
    # Autres
    ("fiat", "500", "3"),
    ("mini", "mini", "3"),
    ("volvo", "xc40", ""),
    ("seat", "leon", "4"),
    ("seat", "arona", ""),
    ("skoda", "octavia", "4"),
    ("skoda", "kodiaq", ""),
    ("tesla", "model-3", ""),
    ("tesla", "model-y", ""),
]


# =============================================================================
# CLI - POINT D'ENTRÉE
# =============================================================================

def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scraper avis-auto.fr")
    parser.add_argument("--marque", type=str, help="Marque à scraper")
    parser.add_argument("--modele", type=str, help="Modèle à scraper")
    parser.add_argument("--generation", type=str, default="", help="Génération")
    parser.add_argument("--all", action="store_true", help="Scraper tous les modèles")
    parser.add_argument("--output", type=str, default="data/avis_auto", help="Dossier de sortie")
    parser.add_argument("--mongodb", action="store_true", help="Sauvegarder dans MongoDB")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="Délai entre requêtes (sec)")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with AvisAutoScraper(rate_limit=args.rate_limit) as scraper:
        
        if args.all:
            # Scraper tous les modèles
            print(f"\n🚀 Scraping de {len(MODELS_TO_SCRAPE)} modèles...\n")
            
            results = []
            for marque, modele, gen in MODELS_TO_SCRAPE:
                try:
                    data = scraper.scrape_vehicle(marque, modele, gen)
                    
                    # Sauvegarder JSON
                    filename = f"{marque}_{modele}"
                    if gen:
                        filename += f"_{gen}"
                    scraper.save_to_json(data, output_dir / f"{filename}.json")
                    
                    # MongoDB si demandé
                    if args.mongodb:
                        scraper.save_to_mongodb(data)
                    
                    results.append(data)
                    
                except Exception as e:
                    print(f"   ❌ Erreur {marque} {modele}: {e}")
                    continue
            
            # Résumé
            total_avis = sum(v.nb_avis for v in results)
            print(f"\n{'='*50}")
            print(f"✅ SCRAPING TERMINÉ")
            print(f"   - Modèles scrapés: {len(results)}/{len(MODELS_TO_SCRAPE)}")
            print(f"   - Total avis: {total_avis}")
            print(f"   - Fichiers: {output_dir}/")
            print(f"{'='*50}\n")
            
        elif args.marque and args.modele:
            # Scraper un modèle spécifique
            data = scraper.scrape_vehicle(args.marque, args.modele, args.generation)
            
            filename = f"{args.marque}_{args.modele}"
            if args.generation:
                filename += f"_{args.generation}"
            scraper.save_to_json(data, output_dir / f"{filename}.json")
            
            if args.mongodb:
                scraper.save_to_mongodb(data)
            
        else:
            # Mode test: scraper Peugeot 208
            print("\n🧪 Mode test: Peugeot 208 génération 2\n")
            data = scraper.scrape_vehicle("peugeot", "208", "2")
            scraper.save_to_json(data, output_dir / "test_peugeot_208.json")
            
            if args.mongodb:
                scraper.save_to_mongodb(data)
            
            print("\n📋 Aperçu des données:")
            print(json.dumps(data.to_dict(), ensure_ascii=False, indent=2)[:2000] + "...")


if __name__ == "__main__":
    main()
