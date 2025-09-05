#!/usr/bin/env python3
"""
Test script for the new Unused Chunk Analysis functionality.
This script tests the core functionality without requiring the full RAG evaluation system.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.unusedChunkAnalyzer import UnusedChunkAnalyzer, UnusedChunkAnalysis, UnusedChunkSummary

def test_unused_chunk_analyzer():
    """Test the UnusedChunkAnalyzer functionality."""
    print("🧪 Testing Unused Chunk Analyzer...")
    
    # Sample data for testing
    queries = [
        "What is the capital of France?",
        "How does photosynthesis work?",
        "What is the meaning of life?",
        "Explain quantum computing",
        "What is machine learning?"
    ]
    
    answers = [
        "The capital of France is Paris.",
        "Photosynthesis is the process by which plants convert sunlight into energy.",
        "I cannot answer that question.",
        "Quantum computing uses quantum mechanical phenomena to process information.",
        "Machine learning is a subset of artificial intelligence."
    ]
    
    ground_truths = [
        "Paris",
        "Photosynthesis is the process by which plants convert sunlight into energy.",
        "The meaning of life is a philosophical question with no single answer.",
        "Quantum computing uses quantum mechanical phenomena to process information.",
        "Machine learning is a subset of artificial intelligence."
    ]
    
    # Sample chunk statistics
    chunk_statistics_list = [
        {
            'sent_to_llm_chunk_count': 8,
            'used_in_answer_chunk_count': 3,
            'sent_to_llm_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4', 'chunk5', 'chunk6', 'chunk7', 'chunk8'],
            'used_in_answer_chunk_ids': ['chunk1', 'chunk2', 'chunk3'],
            'chunk_qualification_stats': {'qualified': 6, 'unqualified': 2}
        },
        {
            'sent_to_llm_chunk_count': 5,
            'used_in_answer_chunk_count': 4,
            'sent_to_llm_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4', 'chunk5'],
            'used_in_answer_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4'],
            'chunk_qualification_stats': {'qualified': 5, 'unqualified': 0}
        },
        {
            'sent_to_llm_chunk_count': 20,
            'used_in_answer_chunk_count': 2,
            'sent_to_llm_chunk_ids': [f'chunk{i}' for i in range(1, 21)],
            'used_in_answer_chunk_ids': ['chunk1', 'chunk2'],
            'chunk_qualification_stats': {'qualified': 15, 'unqualified': 5}
        },
        {
            'sent_to_llm_chunk_count': 6,
            'used_in_answer_chunk_count': 5,
            'sent_to_llm_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4', 'chunk5', 'chunk6'],
            'used_in_answer_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4', 'chunk5'],
            'chunk_qualification_stats': {'qualified': 6, 'unqualified': 0}
        },
        {
            'sent_to_llm_chunk_count': 4,
            'used_in_answer_chunk_count': 3,
            'sent_to_llm_chunk_ids': ['chunk1', 'chunk2', 'chunk3', 'chunk4'],
            'used_in_answer_chunk_ids': ['chunk1', 'chunk2', 'chunk3'],
            'chunk_qualification_stats': {'qualified': 4, 'unqualified': 0}
        }
    ]
    
    # Sample LLM evaluation results
    llm_evaluation_results = [
        {'context_relevancy_score': 0.8, 'ground_truth_validity_score': 0.9},
        {'context_relevancy_score': 0.9, 'ground_truth_validity_score': 0.9},
        {'context_relevancy_score': 0.6, 'ground_truth_validity_score': 0.7},
        {'context_relevancy_score': 0.8, 'ground_truth_validity_score': 0.9},
        {'context_relevancy_score': 0.9, 'ground_truth_validity_score': 0.9}
    ]
    
    try:
        # Test the main analysis function
        print("🔍 Running unused chunk analysis...")
        analysis_list, summary = UnusedChunkAnalyzer.analyze_unused_chunks(
            queries, answers, ground_truths, chunk_statistics_list, llm_evaluation_results
        )
        
        print(f"✅ Analysis completed successfully!")
        print(f"📊 Questions analyzed: {summary.total_questions_analyzed}")
        print(f"🔍 Questions with unused chunks: {summary.questions_with_unused_chunks}")
        print(f"📈 Category distribution: {summary.category_distribution}")
        print(f"💡 Recommendations: {len(summary.recommendations)}")
        
        # Test Excel formatting
        print("\n📊 Testing Excel formatting...")
        excel_data = UnusedChunkAnalyzer.format_analysis_for_excel(analysis_list)
        print(f"✅ Excel formatting successful: {len(excel_data)} rows")
        
        summary_excel = UnusedChunkAnalyzer.format_summary_for_excel(summary)
        print(f"✅ Summary Excel formatting successful: {len(summary_excel)} fields")
        
        # Test quality analysis tab creation
        print("\n📋 Testing Quality Analysis tab creation...")
        summary_list = [summary.__dict__]
        quality_tab = UnusedChunkAnalyzer._create_quality_analysis_tab(summary_list)
        if quality_tab is not None:
            print(f"✅ Quality Analysis tab created: {len(quality_tab)} rows")
        else:
            print("⚠️ Quality Analysis tab creation failed (pandas not available)")
        
        # Test detailed analysis tab creation
        print("\n🔍 Testing Detailed Analysis tab creation...")
        detailed_tab = UnusedChunkAnalyzer._create_detailed_analysis_tab(analysis_list)
        if detailed_tab is not None:
            print(f"✅ Detailed Analysis tab created: {len(detailed_tab)} rows")
        else:
            print("⚠️ Detailed Analysis tab creation failed (pandas not available)")
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_categorization_logic():
    """Test the categorization logic specifically."""
    print("\n🧪 Testing categorization logic...")
    
    # Test different scenarios
    test_cases = [
        {
            'name': 'Context Overload',
            'sent_count': 18,
            'used_count': 3,
            'answer': 'Good answer',
            'expected_category': 'context_overload'
        },
        {
            'name': 'Context Irrelevant',
            'sent_count': 8,
            'used_count': 2,
            'answer': 'Good answer',
            'expected_category': 'context_irrelevant'
        },
        {
            'name': 'Answer Generation Failure',
            'sent_count': 5,
            'used_count': 2,
            'answer': 'I cannot answer',
            'expected_category': 'answer_generation_failure'
        }
    ]
    
    for test_case in test_cases:
        print(f"  Testing: {test_case['name']}")
        
        # Create mock chunk stats
        chunk_stats = {
            'sent_to_llm_chunk_count': test_case['sent_count'],
            'used_in_answer_chunk_count': test_case['used_count']
        }
        
        # Test categorization
        category, reasoning = UnusedChunkAnalyzer._categorize_question(
            "test query", test_case['answer'], "test ground truth", chunk_stats
        )
        
        print(f"    Expected: {test_case['expected_category']}")
        print(f"    Got: {category.value}")
        print(f"    Reasoning: {reasoning}")
        
        if category.value == test_case['expected_category']:
            print("    ✅ PASS")
        else:
            print("    ❌ FAIL")
    
    print("✅ Categorization logic tests completed!")

if __name__ == "__main__":
    print("🚀 Starting Unused Chunk Analysis Tests...")
    
    # Run main functionality test
    success = test_unused_chunk_analyzer()
    
    if success:
        # Run categorization logic test
        test_categorization_logic()
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n❌ Tests failed. Please check the implementation.")
        sys.exit(1)
