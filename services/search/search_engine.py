from typing import List, Dict, Tuple, Optional
import json
from fuzzywuzzy import fuzz
from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path
import asyncio
import logging

from core.models import DocumentIndex
from core.utils import setup_logger

logger = setup_logger('search_engine')

class IntelligentSearchEngine:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.indices: Dict[str, DocumentIndex] = {}
        self.load_indices()
        
    def load_indices(self):
        """Lade alle Markdown/JSON Indizes"""
        # Placeholder - wird in load_indices_async implementiert
        pass
    
    async def load_indices_async(self):
        """Lade alle Indizes asynchron"""
        json_path = Path(self.index_path) / "json"
        
        if not json_path.exists():
            logger.warning(f"Index-Verzeichnis existiert nicht: {json_path}")
            return
        
        for json_file in json_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    doc = DocumentIndex.from_json(json.dumps(data))
                    self.indices[doc.doc_id] = doc
            except Exception as e:
                logger.error(f"Fehler beim Laden von {json_file}: {str(e)}")
        
        logger.info(f"{len(self.indices)} Indizes geladen")

    def search(self, query: str, filters: Dict = None) -> List[Tuple[DocumentIndex, float]]:
        """Mehrstufige intelligente Suche"""
        # 1. Keyword-basierte Vorfilterung
        keyword_matches = self.keyword_search(query)
        
        # 2. Semantische Suche
        semantic_matches = self.semantic_search(query, keyword_matches)
        
        # 3. Verknüpfungs-basierte Erweiterung
        expanded_results = self.expand_with_links(semantic_matches)
        
        # 4. Ranking mit Learning-Daten
        ranked_results = self.apply_learning_boost(expanded_results, query)
        
        return ranked_results

    async def search_async(self, query: str, filters: Dict = None, limit: int = 20):
        """Asynchrone Suche"""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, self.search, query, filters)
        return results[:limit]

    async def get_document_async(self, doc_id: str) -> Optional[DocumentIndex]:
        """Hole Dokument asynchron"""
        return self.indices.get(doc_id)

    async def update_semantic_link_async(self, doc1_id: str, doc2_id: str, score: float):
        """Aktualisiere semantische Verknüpfung"""
        if doc1_id in self.indices:
            self.indices[doc1_id].semantic_links[doc2_id] = score
            # Speichere aktualisierten Index
            self.indices[doc1_id].save(Path(self.index_path))

    def keyword_search(self, query: str) -> List[str]:
        """Schnelle Keyword-basierte Suche im JSON-Index"""
        query_terms = query.lower().split()
        matches = []
        
        for doc_id, index in self.indices.items():
            score = 0
            
            # Titel-Match (höhere Gewichtung)
            for term in query_terms:
                if term in index.title.lower():
                    score += 3
            
            # Keyword-Match
            for term in query_terms:
                for keyword in index.keywords:
                    if fuzz.partial_ratio(term, keyword) > 80:
                        score += 2
            
            # Content-Match
            content_text = ' '.join([s.get('content', '') for s in index.sections])
            for term in query_terms:
                if term in content_text.lower():
                    score += 1
            
            if score > 0:
                matches.append((doc_id, score))
        
        # Sortiere nach Score
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:50]]

    def semantic_search(self, query: str, candidate_ids: List[str]) -> List[Tuple[str, float]]:
        """Semantische Ähnlichkeitssuche"""
        if not candidate_ids:
            return []
            
        query_embedding = self.encoder.encode(query)
        results = []
        
        for doc_id in candidate_ids:
            if doc_id not in self.indices:
                continue
                
            index = self.indices[doc_id]
            
            # Erstelle Dokument-Repräsentation
            doc_text = f"{index.title} {' '.join(index.keywords)} "
            doc_text += ' '.join([s.get('content', '')[:200] for s in index.sections[:3]])
            
            doc_embedding = self.encoder.encode(doc_text)
            
            # Berechne Ähnlichkeit
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            
            results.append((doc_id, float(similarity)))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def expand_with_links(self, results: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Erweitere Ergebnisse basierend auf Verknüpfungen"""
        expanded = dict(results)
        
        for doc_id, score in results[:10]:  # Nur Top 10 expandieren
            if doc_id not in self.indices:
                continue
                
            index = self.indices[doc_id]
            
            # Füge direkte Referenzen hinzu
            for ref_id in index.references:
                if ref_id in self.indices and ref_id not in expanded:
                    expanded[ref_id] = score * 0.5
            
            # Füge semantische Links hinzu
            for link_id, link_score in index.semantic_links.items():
                if link_id in self.indices:
                    if link_id not in expanded:
                        expanded[link_id] = score * link_score * 0.3
                    else:
                        expanded[link_id] = max(expanded[link_id], score * link_score * 0.3)
        
        return sorted(expanded.items(), key=lambda x: x[1], reverse=True)

    def apply_learning_boost(self, results: List[Tuple[str, float]], query: str) -> List[Tuple[DocumentIndex, float]]:
        """Wende Learning-basiertes Ranking an"""
        # Konvertiere zu DocumentIndex Objekten
        final_results = []
        for doc_id, score in results:
            if doc_id in self.indices:
                final_results.append((self.indices[doc_id], score))
        
        return final_results

