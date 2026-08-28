"""
Unused Chunk Analysis Module
============================
Advanced analysis of questions where chunks were sent to LLM but not used in answers.

This module provides comprehensive categorization and analysis of unused chunks to identify:
1. Context relevance issues from qualified chunks
2. Ground truth validity problems
3. Context overload causing answer generation failures

Author: RAG Evaluator Team
Version: 1.0.0
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Try to import pandas, but handle gracefully if not available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

# Configure logging
logger = logging.getLogger(__name__)

class UnusedChunkCategory(Enum):
    """Categories for questions with unused chunks sent to LLM."""
    CONTEXT_IRRELEVANT = "context_irrelevant"
    GROUND_TRUTH_INVALID = "ground_truth_invalid"
    CONTEXT_OVERLOAD = "context_overload"
    ANSWER_GENERATION_FAILURE = "answer_generation_failure"
    MIXED_ISSUES = "mixed_issues"

@dataclass
class UnusedChunkAnalysis:
    """Data structure for unused chunk analysis."""
    query: str
    answer: str
    ground_truth: str
    sent_to_llm_chunks: List[str]
    used_chunks: List[str]
    unused_chunks: List[str]
    chunk_qualification_stats: Dict[str, int]
    total_sent_to_llm: int
    total_used: int
    unused_count: int
    category: UnusedChunkCategory
    reasoning: str
    context_relevance_score: Optional[float] = None
    ground_truth_validity_score: Optional[float] = None
    context_overload_score: Optional[float] = None

@dataclass
class UnusedChunkSummary:
    """Summary statistics for unused chunk analysis."""
    total_questions_analyzed: int
    questions_with_unused_chunks: int
    category_distribution: Dict[str, int]
    avg_unused_chunks_per_question: float
    avg_context_relevance_score: float
    avg_ground_truth_validity_score: float
    avg_context_overload_score: float
    recommendations: List[str]

class UnusedChunkAnalyzer:
    """
    Analyzes questions where chunks were sent to LLM but not used in answers.
    
    This class provides comprehensive categorization and analysis to identify
    the root causes of chunk underutilization in RAG systems.
    """
    
    # Thresholds for categorization
    CONTEXT_OVERLOAD_THRESHOLD = 15  # More than 15 chunks sent to LLM
    LOW_UTILIZATION_THRESHOLD = 0.3  # Less than 30% of sent chunks used
    HIGH_UNUSED_THRESHOLD = 0.7     # More than 70% of sent chunks unused
    
    @staticmethod
    def analyze_unused_chunks(
        queries: List[str],
        answers: List[str], 
        ground_truths: List[str],
        chunk_statistics_list: List[Dict],
        llm_evaluation_results: Optional[List[Dict]] = None
    ) -> Tuple[List[UnusedChunkAnalysis], UnusedChunkSummary]:
        """
        Analyze questions with unused chunks sent to LLM.
        
        Args:
            queries: List of user queries
            answers: List of generated answers
            ground_truths: List of ground truth answers
            chunk_statistics_list: List of chunk statistics dictionaries
            llm_evaluation_results: Optional LLM evaluation results for additional context
            
        Returns:
            Tuple of (analysis_list, summary_statistics)
        """
        try:
            logger.info(f"🔍 Starting unused chunk analysis for {len(queries)} queries")
            
            analysis_list = []
            questions_with_unused_chunks = 0
            
            for i, (query, answer, ground_truth, chunk_stats) in enumerate(
                zip(queries, answers, ground_truths, chunk_statistics_list)
            ):
                # Check if this question has unused chunks
                sent_to_llm_count = chunk_stats.get('sent_to_llm_chunk_count', 0)
                used_count = chunk_stats.get('used_in_answer_chunk_count', 0)
                
                if sent_to_llm_count > 0 and sent_to_llm_count > used_count:
                    questions_with_unused_chunks += 1
                    
                    # Analyze this question
                    analysis = UnusedChunkAnalyzer._analyze_single_question(
                        query, answer, ground_truth, chunk_stats, 
                        llm_evaluation_results[i] if llm_evaluation_results else None
                    )
                    analysis_list.append(analysis)
            
            # Generate summary statistics
            summary = UnusedChunkAnalyzer._generate_summary(
                analysis_list, len(queries), questions_with_unused_chunks
            )
            
            logger.info(f"✅ Unused chunk analysis completed: {questions_with_unused_chunks} questions analyzed")
            return analysis_list, summary
            
        except Exception as e:
            logger.error(f"❌ Error in unused chunk analysis: {e}")
            return [], UnusedChunkAnalyzer._create_empty_summary()
    
    @staticmethod
    def _analyze_single_question(
        query: str,
        answer: str,
        ground_truth: str,
        chunk_stats: Dict,
        llm_eval: Optional[Dict] = None
    ) -> UnusedChunkAnalysis:
        """
        Analyze a single question for unused chunk issues.
        
        Args:
            query: User query
            answer: Generated answer
            ground_truth: Expected answer
            chunk_stats: Chunk statistics for this question
            llm_eval: Optional LLM evaluation results
            
        Returns:
            UnusedChunkAnalysis object
        """
        sent_to_llm_chunks = chunk_stats.get('sent_to_llm_chunk_ids', [])
        used_chunks = chunk_stats.get('used_in_answer_chunk_ids', [])
        unused_chunks = [chunk for chunk in sent_to_llm_chunks if chunk not in used_chunks]
        
        sent_count = len(sent_to_llm_chunks)
        used_count = len(used_chunks)
        unused_count = len(unused_chunks)
        
        # Determine category and reasoning
        category, reasoning = UnusedChunkAnalyzer._categorize_question(
            query, answer, ground_truth, chunk_stats, llm_eval
        )
        
        # Calculate scores
        context_relevance_score = UnusedChunkAnalyzer._calculate_context_relevance_score(
            chunk_stats, llm_eval
        )
        ground_truth_validity_score = UnusedChunkAnalyzer._calculate_ground_truth_validity_score(
            query, ground_truth, llm_eval
        )
        context_overload_score = UnusedChunkAnalyzer._calculate_context_overload_score(
            sent_count, used_count, unused_count
        )
        
        return UnusedChunkAnalysis(
            query=query,
            answer=answer,
            ground_truth=ground_truth,
            sent_to_llm_chunks=sent_to_llm_chunks,
            used_chunks=used_chunks,
            unused_chunks=unused_chunks,
            chunk_qualification_stats=chunk_stats.get('chunk_qualification_stats', {}),
            total_sent_to_llm=sent_count,
            total_used=used_count,
            unused_count=unused_count,
            category=category,
            reasoning=reasoning,
            context_relevance_score=context_relevance_score,
            ground_truth_validity_score=ground_truth_validity_score,
            context_overload_score=context_overload_score
        )
    
    @staticmethod
    def _categorize_question(
        query: str,
        answer: str,
        ground_truth: str,
        chunk_stats: Dict,
        llm_eval: Optional[Dict] = None
    ) -> Tuple[UnusedChunkCategory, str]:
        """
        Categorize the question based on unused chunk analysis.
        
        Args:
            query: User query
            answer: Generated answer
            ground_truth: Expected answer
            chunk_stats: Chunk statistics
            llm_eval: Optional LLM evaluation results
            
        Returns:
            Tuple of (category, reasoning)
        """
        sent_count = chunk_stats.get('sent_to_llm_chunk_count', 0)
        used_count = chunk_stats.get('used_in_answer_chunk_count', 0)
        unused_count = sent_count - used_count
        
        # Check for context overload
        if sent_count > UnusedChunkAnalyzer.CONTEXT_OVERLOAD_THRESHOLD:
            return UnusedChunkCategory.CONTEXT_OVERLOAD, f"Too many chunks ({sent_count}) sent to LLM, causing information overload"
        
        # Check utilization ratio
        utilization_ratio = used_count / sent_count if sent_count > 0 else 0
        if utilization_ratio < UnusedChunkAnalyzer.LOW_UTILIZATION_THRESHOLD:
            return UnusedChunkCategory.CONTEXT_IRRELEVANT, f"Low chunk utilization ({utilization_ratio:.2%}), suggesting irrelevant context"
        
        # Check for answer generation issues
        if answer.strip().lower() in ['', 'no answer', 'i cannot answer', 'insufficient information']:
            return UnusedChunkCategory.ANSWER_GENERATION_FAILURE, "LLM failed to generate meaningful answer despite having context"
        
        # Check ground truth validity using LLM evaluation if available
        if llm_eval and 'ground_truth_validity_score' in llm_eval:
            validity_score = llm_eval['ground_truth_validity_score']
            if validity_score < 0.6:  # Low validity threshold
                return UnusedChunkCategory.GROUND_TRUTH_INVALID, f"Ground truth validity score ({validity_score:.2f}) suggests invalid reference answer"
        
        # Default to mixed issues if no clear category
        return UnusedChunkCategory.MIXED_ISSUES, "Multiple factors contributing to chunk underutilization"
    
    @staticmethod
    def _calculate_context_relevance_score(chunk_stats: Dict, llm_eval: Optional[Dict] = None) -> Optional[float]:
        """Calculate context relevance score."""
        if llm_eval and 'context_relevancy_score' in llm_eval:
            return llm_eval['context_relevancy_score']
        
        # Fallback: use chunk qualification stats
        qualification_stats = chunk_stats.get('chunk_qualification_stats', {})
        qualified_count = qualification_stats.get('qualified', 0)
        total_sent = chunk_stats.get('sent_to_llm_chunk_count', 0)
        
        if total_sent > 0:
            return qualified_count / total_sent
        return None
    
    @staticmethod
    def _calculate_ground_truth_validity_score(
        query: str, 
        ground_truth: str, 
        llm_eval: Optional[Dict] = None
    ) -> Optional[float]:
        """Calculate ground truth validity score."""
        if llm_eval and 'ground_truth_validity_score' in llm_eval:
            return llm_eval['ground_truth_validity_score']
        
        # Fallback: basic heuristics
        if not ground_truth or ground_truth.strip() == '':
            return 0.0
        if ground_truth.lower() in ['invalid question', 'cannot answer', 'no answer']:
            return 0.3
        return 0.7  # Default moderate validity
    
    @staticmethod
    def _calculate_context_overload_score(sent_count: int, used_count: int, unused_count: int) -> float:
        """Calculate context overload score (0-1, higher = more overload)."""
        if sent_count == 0:
            return 0.0
        
        # Factors: high chunk count, low utilization, high unused ratio
        chunk_count_factor = min(sent_count / 20.0, 1.0)  # Normalize to 0-1
        utilization_factor = 1.0 - (used_count / sent_count)
        unused_ratio_factor = unused_count / sent_count
        
        # Weighted combination
        overload_score = (chunk_count_factor * 0.4 + 
                         utilization_factor * 0.3 + 
                         unused_ratio_factor * 0.3)
        
        return min(overload_score, 1.0)
    
    @staticmethod
    def _generate_summary(
        analysis_list: List[UnusedChunkAnalysis],
        total_questions: int,
        questions_with_unused_chunks: int
    ) -> UnusedChunkSummary:
        """Generate summary statistics for unused chunk analysis."""
        if not analysis_list:
            return UnusedChunkAnalyzer._create_empty_summary()
        
        # Category distribution
        category_distribution = {}
        for analysis in analysis_list:
            category = analysis.category.value
            category_distribution[category] = category_distribution.get(category, 0) + 1
        
        # Calculate averages
        total_unused = sum(analysis.unused_count for analysis in analysis_list)
        avg_unused_chunks = total_unused / len(analysis_list) if analysis_list else 0
        
        # Calculate average scores
        context_scores = [a.context_relevance_score for a in analysis_list if a.context_relevance_score is not None]
        validity_scores = [a.ground_truth_validity_score for a in analysis_list if a.ground_truth_validity_score is not None]
        overload_scores = [a.context_overload_score for a in analysis_list if a.context_overload_score is not None]
        
        avg_context_relevance = sum(context_scores) / len(context_scores) if context_scores else 0.0
        avg_ground_truth_validity = sum(validity_scores) / len(validity_scores) if validity_scores else 0.0
        avg_context_overload = sum(overload_scores) / len(overload_scores) if overload_scores else 0.0
        
        # Generate recommendations
        recommendations = UnusedChunkAnalyzer._generate_recommendations(
            analysis_list, category_distribution
        )
        
        return UnusedChunkSummary(
            total_questions_analyzed=total_questions,
            questions_with_unused_chunks=questions_with_unused_chunks,
            category_distribution=category_distribution,
            avg_unused_chunks_per_question=round(avg_unused_chunks, 2),
            avg_context_relevance_score=round(avg_context_relevance, 3),
            avg_ground_truth_validity_score=round(avg_ground_truth_validity, 3),
            avg_context_overload_score=round(avg_context_overload, 3),
            recommendations=recommendations
        )
    
    @staticmethod
    def _generate_recommendations(
        analysis_list: List[UnusedChunkAnalysis],
        category_distribution: Dict[str, int]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Context overload recommendations
        if category_distribution.get('context_overload', 0) > 0:
            recommendations.append("🔍 Reduce chunks sent to LLM to prevent information overload")
            recommendations.append("⚡ Implement dynamic chunk selection based on query complexity")
        
        # Context irrelevance recommendations
        if category_distribution.get('context_irrelevant', 0) > 0:
            recommendations.append("🎯 Improve retrieval relevance by fine-tuning embedding models")
            recommendations.append("📊 Implement chunk pre-filtering based on semantic similarity")
        
        # Ground truth validity recommendations
        if category_distribution.get('ground_truth_invalid', 0) > 0:
            recommendations.append("✅ Review and validate ground truth answers for accuracy")
            recommendations.append("🔍 Implement ground truth quality assessment pipeline")
        
        # Answer generation failure recommendations
        if category_distribution.get('answer_generation_failure', 0) > 0:
            recommendations.append("🤖 Optimize LLM prompts for better context utilization")
            recommendations.append("📝 Implement answer generation quality checks")
        
        # General recommendations
        if len(analysis_list) > 0:
            avg_unused = sum(a.unused_count for a in analysis_list) / len(analysis_list)
            if avg_unused > 5:
                recommendations.append("⚖️ Balance chunk quantity vs. quality for optimal performance")
            
            recommendations.append("📈 Monitor chunk utilization patterns for continuous improvement")
        
        return recommendations
    
    @staticmethod
    def _create_empty_summary() -> UnusedChunkSummary:
        """Create empty summary structure."""
        return UnusedChunkSummary(
            total_questions_analyzed=0,
            questions_with_unused_chunks=0,
            category_distribution={},
            avg_unused_chunks_per_question=0.0,
            avg_context_relevance_score=0.0,
            avg_ground_truth_validity_score=0.0,
            avg_context_overload_score=0.0,
            recommendations=[]
        )
    
    @staticmethod
    def format_analysis_for_excel(analysis_list: List[UnusedChunkAnalysis]) -> List[Dict]:
        """
        Format unused chunk analysis for Excel export.
        
        Args:
            analysis_list: List of UnusedChunkAnalysis objects
            
        Returns:
            List of dictionaries formatted for Excel
        """
        formatted_data = []
        
        for analysis in analysis_list:
            formatted_row = {
                'Query': analysis.query,
                'Generated Answer': analysis.answer,
                'Ground Truth': analysis.ground_truth,
                'Sent to LLM Chunk Count': analysis.total_sent_to_llm,
                'Used Chunk Count': analysis.total_used,
                'Unused Chunk Count': analysis.unused_count,
                'Unused Chunk IDs': json.dumps(analysis.unused_chunks, separators=(',', ':')),
                'Category': analysis.category.value,
                'Reasoning': analysis.reasoning,
                'Context Relevance Score': analysis.context_relevance_score or 'N/A',
                'Ground Truth Validity Score': analysis.ground_truth_validity_score or 'N/A',
                'Context Overload Score': analysis.context_overload_score or 'N/A',
                'Chunk Qualification Stats': json.dumps(analysis.chunk_qualification_stats, separators=(',', ':'))
            }
            formatted_data.append(formatted_row)
        
        return formatted_data
    
    @staticmethod
    def format_summary_for_excel(summary: UnusedChunkSummary) -> Dict:
        """
        Format summary statistics for Excel export.
        
        Args:
            summary: UnusedChunkSummary object
            
        Returns:
            Dictionary formatted for Excel
        """
        return {
            'Total Questions Analyzed': summary.total_questions_analyzed,
            'Questions with Unused Chunks': summary.questions_with_unused_chunks,
            'Percentage with Unused Chunks': f"{(summary.questions_with_unused_chunks / summary.total_questions_analyzed * 100):.1f}%" if summary.total_questions_analyzed > 0 else "0%",
            'Average Unused Chunks per Question': summary.avg_unused_chunks_per_question,
            'Average Context Relevance Score': summary.avg_context_relevance_score,
            'Average Ground Truth Validity Score': summary.avg_ground_truth_validity_score,
            'Average Context Overload Score': summary.avg_context_overload_score,
            'Category Distribution': json.dumps(summary.category_distribution, separators=(',', ':')),
            'Recommendations': ' | '.join(summary.recommendations)
        }
    
    @staticmethod
    def _create_quality_analysis_tab(summary_list: List[Dict]):
        """
        Create a comprehensive Quality Analysis tab for Excel export.
        
        Args:
            summary_list: List of unused chunk summary dictionaries
            
        Returns:
            DataFrame formatted for Quality Analysis tab
        """
        try:
            if not PANDAS_AVAILABLE:
                logger.error("Pandas is not available. Cannot create quality analysis tab.")
                return None
            
            if not summary_list:
                return pd.DataFrame({
                    'Metric': ['No Data Available'],
                    'Value': ['No unused chunk analysis performed'],
                    'Description': ['Please ensure chunk statistics are available']
                })
            
            # Aggregate data across all sheets
            total_questions = sum(s.get('total_questions_analyzed', 0) for s in summary_list)
            total_with_unused = sum(s.get('questions_with_unused_chunks', 0) for s in summary_list)
            
            # Calculate weighted averages
            total_weight = sum(s.get('total_questions_analyzed', 0) for s in summary_list)
            weighted_avg_unused = 0
            weighted_avg_context_relevance = 0
            weighted_avg_ground_truth_validity = 0
            weighted_avg_context_overload = 0
            
            if total_weight > 0:
                for summary in summary_list:
                    weight = summary.get('total_questions_analyzed', 0) / total_weight
                    weighted_avg_unused += summary.get('avg_unused_chunks_per_question', 0) * weight
                    weighted_avg_context_relevance += summary.get('avg_context_relevance_score', 0) * weight
                    weighted_avg_ground_truth_validity += summary.get('avg_ground_truth_validity_score', 0) * weight
                    weighted_avg_context_overload += summary.get('avg_context_overload_score', 0) * weight
            
            # Aggregate category distribution
            combined_category_dist = {}
            for summary in summary_list:
                category_dist = summary.get('category_distribution', {})
                for category, count in category_dist.items():
                    combined_category_dist[category] = combined_category_dist.get(category, 0) + count
            
            # Collect all recommendations
            all_recommendations = []
            for summary in summary_list:
                recommendations = summary.get('recommendations', [])
                all_recommendations.extend(recommendations)
            
            # Remove duplicates while preserving order
            unique_recommendations = []
            for rec in all_recommendations:
                if rec not in unique_recommendations:
                    unique_recommendations.append(rec)
            
            # Create comprehensive quality analysis DataFrame
            quality_data = [
                # Overall Statistics
                {
                    'Metric': 'Total Questions Analyzed',
                    'Value': str(total_questions),
                    'Description': 'Total number of questions across all sheets'
                },
                {
                    'Metric': 'Questions with Unused Chunks',
                    'Value': str(total_with_unused),
                    'Description': 'Questions where chunks were sent to LLM but not used'
                },
                {
                    'Metric': 'Percentage with Unused Chunks',
                    'Value': f"{(total_with_unused / total_questions * 100):.1f}%" if total_questions > 0 else "0%",
                    'Description': 'Percentage of questions experiencing chunk underutilization'
                },
                
                # Average Metrics
                {
                    'Metric': 'Average Unused Chunks per Question',
                    'Value': f"{weighted_avg_unused:.2f}",
                    'Description': 'Weighted average of unused chunks across all sheets'
                },
                {
                    'Metric': 'Average Context Relevance Score',
                    'Value': f"{weighted_avg_context_relevance:.3f}",
                    'Description': 'Weighted average context relevance (0-1, higher is better)'
                },
                {
                    'Metric': 'Average Ground Truth Validity Score',
                    'Value': f"{weighted_avg_ground_truth_validity:.3f}",
                    'Description': 'Weighted average ground truth validity (0-1, higher is better)'
                },
                {
                    'Metric': 'Average Context Overload Score',
                    'Value': f"{weighted_avg_context_overload:.3f}",
                    'Description': 'Weighted average context overload (0-1, lower is better)'
                },
                
                # Category Distribution
                {
                    'Metric': 'Context Irrelevant Issues',
                    'Value': str(combined_category_dist.get('context_irrelevant', 0)),
                    'Description': 'Questions with low chunk utilization due to irrelevant context'
                },
                {
                    'Metric': 'Ground Truth Invalid Issues',
                    'Value': str(combined_category_dist.get('ground_truth_invalid', 0)),
                    'Description': 'Questions with invalid or incorrect ground truth answers'
                },
                {
                    'Metric': 'Context Overload Issues',
                    'Value': str(combined_category_dist.get('context_overload', 0)),
                    'Description': 'Questions with too many chunks causing information overload'
                },
                {
                    'Metric': 'Answer Generation Failures',
                    'Value': str(combined_category_dist.get('answer_generation_failure', 0)),
                    'Description': 'Questions where LLM failed to generate meaningful answers'
                },
                {
                    'Metric': 'Mixed Issues',
                    'Value': str(combined_category_dist.get('mixed_issues', 0)),
                    'Description': 'Questions with multiple contributing factors'
                },
                
                # Recommendations
                {
                    'Metric': 'Total Recommendations',
                    'Value': str(len(unique_recommendations)),
                    'Description': 'Number of actionable recommendations generated'
                }
            ]
            
            # Add individual recommendations
            for i, recommendation in enumerate(unique_recommendations, 1):
                quality_data.append({
                    'Metric': f'Recommendation {i}',
                    'Value': recommendation,
                    'Description': 'Actionable improvement suggestion'
                })
            
            return pd.DataFrame(quality_data)
            
        except Exception as e:
            logger.error(f"Error creating quality analysis tab: {e}")
            return pd.DataFrame({
                'Metric': ['Error'],
                'Value': [f'Failed to create quality analysis: {str(e)}'],
                'Description': ['Please check logs for details']
            })
    
    @staticmethod
    def _create_detailed_analysis_tab(analysis_list: List[UnusedChunkAnalysis]):
        """
        Create a detailed analysis tab showing individual questions with unused chunks.
        
        Args:
            analysis_list: List of UnusedChunkAnalysis objects
            
        Returns:
            DataFrame formatted for detailed analysis tab
        """
        try:
            if not PANDAS_AVAILABLE:
                logger.error("Pandas is not available. Cannot create detailed analysis tab.")
                return None
            
            if not analysis_list:
                return pd.DataFrame({
                    'Query': ['No Data Available'],
                    'Generated Answer': ['No unused chunk analysis performed'],
                    'Ground Truth': ['Please ensure chunk statistics are available'],
                    'Category': ['N/A'],
                    'Reasoning': ['N/A']
                })
            
            # Convert analysis objects to DataFrame format
            detailed_data = []
            for analysis in analysis_list:
                row_data = {
                    'Query': analysis.query,
                    'Generated Answer': analysis.answer,
                    'Ground Truth': analysis.ground_truth,
                    'Sent to LLM Chunk Count': analysis.total_sent_to_llm,
                    'Used Chunk Count': analysis.total_used,
                    'Unused Chunk Count': analysis.unused_count,
                    'Unused Chunk IDs': json.dumps(analysis.unused_chunks, separators=(',', ':')),
                    'Category': analysis.category.value,
                    'Reasoning': analysis.reasoning,
                    'Context Relevance Score': analysis.context_relevance_score or 'N/A',
                    'Ground Truth Validity Score': analysis.ground_truth_validity_score or 'N/A',
                    'Context Overload Score': analysis.context_overload_score or 'N/A',
                    'Chunk Qualification Stats': json.dumps(analysis.chunk_qualification_stats, separators=(',', ':'))
                }
                detailed_data.append(row_data)
            
            return pd.DataFrame(detailed_data)
            
        except Exception as e:
            logger.error(f"Error creating detailed analysis tab: {e}")
            return pd.DataFrame({
                'Query': ['Error'],
                'Generated Answer': [f'Failed to create detailed analysis: {str(e)}'],
                'Ground Truth': ['Please check logs for details'],
                'Category': ['Error'],
                'Reasoning': ['Error']
            })
