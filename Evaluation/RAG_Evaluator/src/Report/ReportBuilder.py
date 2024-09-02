from .GraphBuilder import GraphBuilder, AllQtypeGraph
import numpy as np

def HTMLbuilder(component_score, run_ragas=False, ragas_results=None):
    with open('Template/Template.html', 'r', encoding='utf-8') as file:
        html_content = file.read()

    replacements = {
        '{{GENERATOR_SCORE}}': f"{np.nan_to_num(component_score[1].loc['GENERATOR', 'score'], nan=0) * 100:.2f}%",
        '{{RETRIEVER_SCORE}}': f"{np.nan_to_num(component_score[1].loc['RETRIEVER', 'score'], nan=0) * 100:.2f}%",
        '{{REWRITER_SCORE}}': f"{np.nan_to_num(component_score[1].loc['REWRITER', 'score'], nan=0) * 100:.2f}%",
        '{{ROUTING_SCORE}}': f"{np.nan_to_num(component_score[1].loc['ROUTING', 'score'], nan=0) * 100:.2f}%",
        '{{KNOWLEDGE_BASE}}': f"{np.nan_to_num(component_score[1].loc['KNOWLEDGE_BASE', 'score'], nan=0) * 100:.2f}%",
        '{{OVERALL_SCORE}}': f"{np.nan_to_num(component_score[0], nan=0) * 100:.2f}%"
    }

    for placeholder, new_value in replacements.items():
        html_content = html_content.replace(placeholder, new_value)

    if run_ragas:
        data = {
            "question_type": ragas_results['question_type'].tolist(),
            "answer_relevancy": ragas_results['answer_relevancy'].tolist(),
            "faithfulness": ragas_results['faithfulness'].tolist(),
            "context_recall": ragas_results['context_recall'].tolist(),
            "context_precision": ragas_results['context_precision'].tolist(),
            "answer_correctness": ragas_results['answer_correctness'].tolist(),
            "answer_similarity": ragas_results['answer_similarity'].tolist()
        }

        overall_script, overall_div = GraphBuilder(data)
        script, div = AllQtypeGraph(data)

        new_links = []
        for type_key in div.keys():
            new_links.append(f'<a onclick="showDivs(\'{type_key}\')">{type_key}</a>')
    
        new_links_str = ' '.join(new_links)
    
        q_type_charts = []
        for type_key in div.keys():
            q_type_charts.append(
                f'<div id="{type_key}"><h2 id="blocksubtitle">{type_key}</h2>{div[type_key]}{script[type_key]}</div>'
            )
    
        new_q_type_charts = ' '.join(q_type_charts)
    
        html_content = html_content.replace('<a onclick="showDivs(\' \')">othertypes</a>', new_links_str)
        html_content = html_content.replace('<div id="OverallRagas"></div>', f'<div id="OverallRagas"><h2 id="blocktitle">OVERALL METRICS<h2>{overall_div}</div>{overall_script}')
        html_content = html_content.replace('<div id="QuestiontypeRagas"></div>', f'<div id="QuestiontypeRagas"><h2 id="blocktitle">QUESTION TYPE METRICS</h2>' + new_q_type_charts + '</div>')

    with open('output.html', 'w', encoding='utf-8') as file:
        file.write(html_content)

    print("HTML file has been updated and saved as 'output.html'.")
