"""
Chunk Statistics Processor
=========================
Utility module to extract and process chunk statistics from search API responses.

This module provides comprehensive analysis of chunk usage patterns in RAG systems,
including Support@K metrics, qualified chunk distribution, and retrieval effectiveness.

Features:
- Extract chunk statistics from SearchAssist and XO Platform API responses
- Calculate Support@K metrics for retrieval quality assessment
- Analyze qualified chunk distribution across rank ranges
- Generate Excel-compatible formatted output
- Provide aggregate summary statistics for batch analysis

Author: RAG Evaluator Team
Version: 2.0.0
"""

import json
import logging
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

class APIType(Enum):
    """Supported API types for chunk statistics extraction."""
    XO_PLATFORM = "XO"
    SEARCH_ASSIST = "SA"

class ChunkQualificationStatus(Enum):
    """Chunk qualification status values."""
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    UNKNOWN = "unknown"

@dataclass
class ChunkData:
    """Data structure for individual chunk information."""
    chunk_id: str
    rank: int
    sent_to_llm: bool
    used_in_answer: bool
    qualification_status: str

@dataclass
class SupportMetrics:
    """Data structure for Support@K metrics."""
    best_support_rank: Optional[int]
    support_at_5: bool
    support_at_10: bool
    support_at_20: bool
    bucketed_distribution: str

@dataclass
class ChunkDistribution:
    """Data structure for chunk distribution analysis."""
    top_5_qualified: int
    top_5_qualified_used: int
    top_5_10_qualified: int
    top_5_10_qualified_used: int
    top_10_20_qualified: int
    top_10_20_qualified_used: int
    total_qualified: int
    total_qualified_used: int

@dataclass
class ChunkStatistics:
    """Complete chunk statistics data structure."""
    retrieved_chunk_ids: List[str] = field(default_factory=list)
    retrieved_chunk_count: int = 0
    sent_to_llm_chunk_ids: List[str] = field(default_factory=list)
    sent_to_llm_chunk_count: int = 0
    used_in_answer_chunk_ids: List[str] = field(default_factory=list)
    used_in_answer_chunk_count: int = 0
    chunk_qualification_stats: Dict[str, int] = field(default_factory=dict)
    support_metrics: SupportMetrics = field(default_factory=lambda: SupportMetrics(
        best_support_rank=None,
        support_at_5=False,
        support_at_10=False,
        support_at_20=False,
        bucketed_distribution='none'
    ))
    chunk_distribution: ChunkDistribution = field(default_factory=lambda: ChunkDistribution(
        top_5_qualified=0,
        top_5_qualified_used=0,
        top_5_10_qualified=0,
        top_5_10_qualified_used=0,
        top_10_20_qualified=0,
        top_10_20_qualified_used=0,
        total_qualified=0,
        total_qualified_used=0
    ))
    error: Optional[str] = None

class ChunkStatisticsProcessor:
    """
    Process chunk statistics from search API responses.
    
    This class provides methods to extract, analyze, and format chunk statistics
    from SearchAssist and XO Platform API responses. It includes comprehensive
    analysis of chunk usage patterns, Support@K metrics, and qualified chunk
    distribution across different rank ranges.
    """
    
    # Constants
    MAX_CHUNKS_FOR_ANALYSIS = 20
    SUPPORT_THRESHOLDS = [5, 10, 20]
    RANK_RANGES = {
        'top_5': (1, 5),
        'top_5_10': (6, 10),
        'top_10_20': (11, 20)
    }
    
    @staticmethod
    def extract_chunk_statistics(answer: Dict, api_type: str = "XO") -> Dict:
        """
        Extract chunk statistics from search API response.
        
        This method processes the generative chunks from the API response and
        extracts comprehensive statistics including chunk IDs, counts, qualification
        status, Support@K metrics, and chunk distribution analysis.
        
        Args:
            answer: The response from the search API containing chunk information
            api_type: Type of API ("XO" for XO Platform, "SA" for SearchAssist)
            
        Returns:
            Dictionary containing comprehensive chunk statistics with the following structure:
            {
                'retrieved_chunk_ids': List[str],
                'retrieved_chunk_count': int,
                'sent_to_llm_chunk_ids': List[str],
                'sent_to_llm_chunk_count': int,
                'used_in_answer_chunk_ids': List[str],
                'used_in_answer_chunk_count': int,
                'chunk_qualification_stats': Dict[str, int],
                'support_metrics': Dict containing Support@K metrics,
                'chunk_distribution': Dict containing qualified chunk distribution,
                'error': Optional[str] if any error occurred
            }
            
        Raises:
            Exception: If there's an error during processing (handled internally)
        """
        try:
            logger.debug(f"Extracting chunk statistics for API type: {api_type}")
            
            # Extract generative chunks based on API type
            generative_chunks = ChunkStatisticsProcessor._extract_generative_chunks(answer, api_type)
            
            if not generative_chunks:
                logger.debug("No generative chunks found, returning empty statistics")
                return ChunkStatisticsProcessor._create_empty_statistics()
            
            # Process chunks and collect statistics
            chunk_data_list = ChunkStatisticsProcessor._process_chunks(generative_chunks)
            
            # Calculate all metrics
            statistics = ChunkStatisticsProcessor._calculate_statistics(chunk_data_list)
            
            logger.debug(f"Successfully extracted statistics for {len(chunk_data_list)} chunks")
            return statistics
            
        except Exception as e:
            logger.error(f"Error extracting chunk statistics: {e}")
            return ChunkStatisticsProcessor._create_empty_statistics(error=str(e))
    
    @staticmethod
    def _extract_generative_chunks(answer: Dict, api_type: str) -> List[Dict]:
        """
        Extract generative chunks from API response based on API type.
        
        Args:
            answer: API response dictionary
            api_type: Type of API ("XO" or "SA")
            
        Returns:
            List of generative chunk dictionaries
        """
        if api_type.upper() == APIType.SEARCH_ASSIST.value:
            # SearchAssist structure
            return answer.get('template', {}).get('chunk_result', {}).get('generative', [])
        else:
            # XO Platform structure (default)
            return answer.get('chunk_result', {}).get('generative', [])
    
    @staticmethod
    def _process_chunks(generative_chunks: List[Dict]) -> List[ChunkData]:
        """
        Process generative chunks and extract structured data.
        
        Args:
            generative_chunks: List of raw chunk dictionaries
            
        Returns:
            List of structured ChunkData objects
        """
        chunk_data_list = []
        
        # Process only top MAX_CHUNKS_FOR_ANALYSIS chunks
        for rank, chunk in enumerate(generative_chunks[:ChunkStatisticsProcessor.MAX_CHUNKS_FOR_ANALYSIS], 1):
            source = chunk.get('_source', {})
            chunk_id = source.get('chunkId', '')
            
            if chunk_id:
                chunk_data = ChunkData(
                    chunk_id=chunk_id,
                    rank=rank,
                    sent_to_llm=source.get('sentToLLM', False),
                    used_in_answer=source.get('usedInAnswer', False),
                    qualification_status=source.get('chunkQualified', ChunkQualificationStatus.UNKNOWN.value)
                )
                chunk_data_list.append(chunk_data)
        
        return chunk_data_list
    
    @staticmethod
    def _calculate_statistics(chunk_data_list: List[ChunkData]) -> Dict:
        """
        Calculate comprehensive statistics from chunk data.
        
        Args:
            chunk_data_list: List of processed chunk data
            
        Returns:
            Dictionary containing all calculated statistics
        """
        # Extract basic statistics
        retrieved_chunk_ids = sorted([chunk.chunk_id for chunk in chunk_data_list])
        sent_to_llm_chunk_ids = sorted([chunk.chunk_id for chunk in chunk_data_list if chunk.sent_to_llm])
        used_in_answer_chunk_ids = sorted([chunk.chunk_id for chunk in chunk_data_list if chunk.used_in_answer])
        
        # Calculate qualification statistics
        qualification_stats = ChunkStatisticsProcessor._calculate_qualification_stats(chunk_data_list)
        
        # Calculate Support@K metrics
        support_metrics = ChunkStatisticsProcessor._calculate_support_metrics(chunk_data_list)
        
        # Calculate chunk distribution
        chunk_distribution = ChunkStatisticsProcessor._calculate_chunk_distribution(chunk_data_list)
        
        return {
            'retrieved_chunk_ids': retrieved_chunk_ids,
            'retrieved_chunk_count': len(retrieved_chunk_ids),
            'sent_to_llm_chunk_ids': sent_to_llm_chunk_ids,
            'sent_to_llm_chunk_count': len(sent_to_llm_chunk_ids),
            'used_in_answer_chunk_ids': used_in_answer_chunk_ids,
            'used_in_answer_chunk_count': len(used_in_answer_chunk_ids),
            'chunk_qualification_stats': qualification_stats,
            'support_metrics': support_metrics,
            'chunk_distribution': chunk_distribution
        }
    
    @staticmethod
    def _calculate_qualification_stats(chunk_data_list: List[ChunkData]) -> Dict[str, int]:
        """
        Calculate chunk qualification statistics.
        
        Args:
            chunk_data_list: List of chunk data
            
        Returns:
            Dictionary with qualification status counts
        """
        qualification_stats = {}
        for chunk in chunk_data_list:
            status = chunk.qualification_status
            qualification_stats[status] = qualification_stats.get(status, 0) + 1
        return qualification_stats
    
    @staticmethod
    def _calculate_support_metrics(chunk_data_list: List[ChunkData]) -> Dict:
        """
        Calculate basic support metrics from chunk data.
        
        Args:
            chunk_data_list: List of chunk data
            
        Returns:
            Dictionary containing basic support metrics
        """
        # Get ranks of chunks used in answer
        used_chunk_ranks = [chunk.rank for chunk in chunk_data_list if chunk.used_in_answer]
        
        if not used_chunk_ranks:
            return ChunkStatisticsProcessor._create_empty_support_metrics()
        
        # Calculate best support rank (minimum rank of any used chunk)
        best_support_rank = min(used_chunk_ranks)
        
        return {
            'best_support_rank': best_support_rank
        }
    
    @staticmethod
    def _calculate_chunk_distribution(chunk_data_list: List[ChunkData]) -> Dict:
        """
        Calculate simple chunk distribution: how many chunks used in answer from each rank range.
        
        Args:
            chunk_data_list: List of chunk data
            
        Returns:
            Dictionary containing simplified chunk distribution metrics
        """
        # Get all chunks used in answer (not just qualified ones)
        used_chunks = [chunk for chunk in chunk_data_list if chunk.used_in_answer]
        
        # Get ranks of chunks used in answer
        used_chunk_ranks = [chunk.rank for chunk in used_chunks]
        
        # Calculate how many chunks used from each rank range
        top_5_used = len([rank for rank in used_chunk_ranks if rank <= 5])
        top_5_10_used = len([rank for rank in used_chunk_ranks if 6 <= rank <= 10])
        top_10_20_used = len([rank for rank in used_chunk_ranks if 11 <= rank <= 20])
        
        return {
            'chunks_used_top_5': top_5_used,
            'chunks_used_5_10': top_5_10_used,
            'chunks_used_10_20': top_10_20_used,
            'used_chunk_ranks': used_chunk_ranks,  # List of actual ranks used
            'total_chunks_used': len(used_chunks)
        }
    

    
    @staticmethod
    def _create_empty_statistics(error: Optional[str] = None) -> Dict:
        """
        Create empty statistics structure.
        
        Args:
            error: Optional error message
            
        Returns:
            Dictionary with empty statistics
        """
        empty_stats = {
            'retrieved_chunk_ids': [],
            'retrieved_chunk_count': 0,
            'sent_to_llm_chunk_ids': [],
            'sent_to_llm_chunk_count': 0,
            'used_in_answer_chunk_ids': [],
            'used_in_answer_chunk_count': 0,
            'chunk_qualification_stats': {},
            'support_metrics': ChunkStatisticsProcessor._create_empty_support_metrics(),
            'chunk_distribution': ChunkStatisticsProcessor._create_empty_chunk_distribution()
        }
        
        if error:
            empty_stats['error'] = error
            
        return empty_stats
    
    @staticmethod
    def _create_empty_support_metrics() -> Dict:
        """Create empty support metrics structure."""
        return {
            'best_support_rank': None
        }
    
    @staticmethod
    def _create_empty_chunk_distribution() -> Dict:
        """Create empty chunk distribution structure."""
        return {
            'chunks_used_top_5': 0,
            'chunks_used_5_10': 0,
            'chunks_used_10_20': 0,
            'used_chunk_ranks': [],
            'total_chunks_used': 0
        }
    
    @staticmethod
    def format_chunk_statistics_for_excel(stats: Dict) -> Dict:
        """
        Format chunk statistics for Excel export.
        
        This method converts the internal statistics format to a format suitable
        for direct inclusion in Excel DataFrames, with proper string formatting
        for lists and dictionaries.
        
        Args:
            stats: Raw chunk statistics dictionary
            
        Returns:
            Dictionary with Excel-compatible formatted values
        """
        try:
            support_metrics = stats.get('support_metrics', {})
            chunk_distribution = stats.get('chunk_distribution', {})
            
            return {
                'Retrieved Chunk IDs': json.dumps(stats.get('retrieved_chunk_ids', []), separators=(',', ':')),
                'Retrieved Chunk Count': stats.get('retrieved_chunk_count', 0),
                'Sent to LLM Chunk IDs': json.dumps(stats.get('sent_to_llm_chunk_ids', []), separators=(',', ':')),
                'Sent to LLM Chunk Count': stats.get('sent_to_llm_chunk_count', 0),
                'Used in Answer Chunk IDs': json.dumps(stats.get('used_in_answer_chunk_ids', []), separators=(',', ':')),
                'Used in Answer Chunk Count': stats.get('used_in_answer_chunk_count', 0),

                'Best Support Rank': support_metrics.get('best_support_rank', 'None'),
                'Chunks Used Top 5': chunk_distribution.get('chunks_used_top_5', 0),
                'Chunks Used 5-10': chunk_distribution.get('chunks_used_5_10', 0),
                'Chunks Used 10-20': chunk_distribution.get('chunks_used_10_20', 0),
                'Used Chunk Ranks': json.dumps(chunk_distribution.get('used_chunk_ranks', []), separators=(',', ':')),
                'Total Chunks Used': chunk_distribution.get('total_chunks_used', 0)
            }
        except Exception as e:
            logger.error(f"Error formatting chunk statistics: {e}")
            return ChunkStatisticsProcessor._create_empty_excel_format()
    
    @staticmethod
    def _create_empty_excel_format() -> Dict:
        """Create empty Excel format structure."""
        return {
            'Retrieved Chunk IDs': '[]',
            'Retrieved Chunk Count': 0,
            'Sent to LLM Chunk IDs': '[]',
            'Sent to LLM Chunk Count': 0,
            'Used in Answer Chunk IDs': '[]',
            'Used in Answer Chunk Count': 0,

            'Best Support Rank': 'None',
            'Chunks Used Top 5': 0,
            'Chunks Used 5-10': 0,
            'Chunks Used 10-20': 0,
            'Used Chunk Ranks': '[]',
            'Total Chunks Used': 0
        }
    
    @staticmethod
    def get_chunk_statistics_summary(stats_list: List[Dict]) -> Dict:
        """
        Generate summary statistics from a list of chunk statistics.
        
        This method calculates aggregate metrics across multiple queries,
        including average chunk counts, Support@K rates, and distribution
        summaries for batch analysis.
        
        Args:
            stats_list: List of chunk statistics dictionaries
            
        Returns:
            Dictionary containing aggregate summary statistics
        """
        if not stats_list:
            return ChunkStatisticsProcessor._create_empty_summary()
        
        total_queries = len(stats_list)
        
        # Calculate basic aggregate metrics
        total_retrieved = sum(stats.get('retrieved_chunk_count', 0) for stats in stats_list)
        total_sent_to_llm = sum(stats.get('sent_to_llm_chunk_count', 0) for stats in stats_list)
        total_used_in_answer = sum(stats.get('used_in_answer_chunk_count', 0) for stats in stats_list)
        

        
        # Calculate chunk distribution summary
        chunk_distribution_summary = ChunkStatisticsProcessor._calculate_chunk_distribution_summary(stats_list, total_queries)
        
        return {
            'total_queries': total_queries,
            'avg_retrieved_chunks': round(total_retrieved / total_queries, 2) if total_queries > 0 else 0,
            'avg_sent_to_llm_chunks': round(total_sent_to_llm / total_queries, 2) if total_queries > 0 else 0,
            'avg_used_in_answer_chunks': round(total_used_in_answer / total_queries, 2) if total_queries > 0 else 0,
            'total_retrieved_chunks': total_retrieved,
            'total_sent_to_llm_chunks': total_sent_to_llm,
            'total_used_in_answer_chunks': total_used_in_answer,

            'chunk_distribution_summary': chunk_distribution_summary
        }
    

    
    @staticmethod
    def _calculate_chunk_distribution_summary(stats_list: List[Dict], total_queries: int) -> Dict:
        """Calculate chunk distribution summary."""
        # Sum all distribution metrics
        total_metrics = {
            'chunks_used_top_5': 0,
            'chunks_used_5_10': 0,
            'chunks_used_10_20': 0,
            'total_chunks_used': 0
        }
        
        for stats in stats_list:
            chunk_dist = stats.get('chunk_distribution', {})
            for key in total_metrics:
                total_metrics[key] += chunk_dist.get(key, 0)
        
        # Calculate averages
        return {
            f'avg_{key}': round(total_metrics[key] / total_queries, 2) if total_queries > 0 else 0
            for key in total_metrics
        }
    
    @staticmethod
    def _create_empty_summary() -> Dict:
        """Create empty summary structure."""
        return {
            'total_queries': 0,
            'avg_retrieved_chunks': 0,
            'avg_sent_to_llm_chunks': 0,
            'avg_used_in_answer_chunks': 0,
            'total_retrieved_chunks': 0,
            'total_sent_to_llm_chunks': 0,
            'total_used_in_answer_chunks': 0,
            'chunk_distribution_summary': {
                'avg_chunks_used_top_5': 0.0,
                'avg_chunks_used_5_10': 0.0,
                'avg_chunks_used_10_20': 0.0,
                'avg_total_chunks_used': 0.0
            }
        }
