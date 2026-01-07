from typing import List, Dict
import statistics


def sort_by_priority(recommendations):
    priority_order = {
        "high": 1,
        "medium": 2,
        "low": 3,
        "neutral": 4
    }

    def priority_score(rec: str):
        rec_lower = rec.lower()
        if "**high priority**" in rec_lower:
            return priority_order["high"]
        if "**medium priority**" in rec_lower:
            return priority_order["medium"]
        if "**low priority**" in rec_lower:
            return priority_order["low"]
        return priority_order["neutral"]

    return sorted(recommendations, key=priority_score)



def generate_recommendations(detailed_results: List[Dict]) -> List[str]:
    if not detailed_results:
        return []

    recs = []

    # ---------- Helpers ----------
    def avg(col):
        vals = [float(r[col]) for r in detailed_results if _is_number(r.get(col))]
        return sum(vals) / len(vals) if vals else None

    def _is_number(v):
        try:
            float(v)
            return True
        except:
            return False

    # ---------- Detect metrics ----------
    columns = detailed_results[0].keys()

    llm_metrics = [c for c in columns if c.lower().startswith("llm")]
    chunk_metrics = {
        "retrieved": "Retrieved Chunk Count",
        "sent": "Sent to LLM Chunk Count",
        "used": "Used in Answer Chunk Count",
        "rank": "Best Support Rank",
        "total": "Total Chunks Used"
    }

    # ---------- 1️⃣ LLM metric performance ----------
    for metric in llm_metrics:
        mean = avg(metric)
        if mean is None:
            continue

        pct = round(mean * 100, 1)

        if mean < 0.6:
            recs.append(
                f"High Priority**: {metric} needs improvement ({pct}%) - Review prompt and grounding strategy."
            )
        elif mean < 0.8:
            recs.append(
                f"Medium Priority**: {metric} has room for improvement ({pct}%) - Consider fine-tuning parameters."
            )
        else:
            recs.append(
                f"Low Priority**: {metric} performing well ({pct}%) - Maintain current configuration."
            )

    # ---------- 2️⃣ Chunk efficiency ----------
    retrieved = avg("Retrieved Chunk Count")
    sent = avg("Sent to LLM Chunk Count")
    used = avg("Used in Answer Chunk Count")
    rank = avg("Best Support Rank")

    if retrieved and used:
        utilization = used / retrieved
        if utilization < 0.3:
            recs.append(
                f"High Priority**: Low chunk utilization ({round(utilization*100,1)}%) - optimize retrieval precision or reduce chunk count."
            )

    if retrieved and retrieved > 15:
        recs.append(
            f"Medium Priority: High retrieval count ({round(retrieved,1)} chunks) - Consider optimizing retrieval strategy for efficiency."
        )

    if sent and retrieved:
        processing_rate = sent / retrieved
        if processing_rate < 0.5:
            recs.append(
                f"Medium Priority: Low processing rate ({round(processing_rate*100,1)}%) - consider increasing chunks sent to LLM for better context."
            )

    if rank and rank > 5:
        recs.append(
            f"High Priority: Poor top-rank retrieval (rank {round(rank,1)}) - Improve ranking algorithm."
        )

    # ---------- 3️⃣ Rule-based evaluation ----------
    ctx = avg("LLM Context Relevancy")
    acc = avg("LLM Answer Correctness")
    gt = avg("LLM Ground Truth Validity")
    comp = avg("LLM Answer Completeness")
    

    if all(v and v >= 0.75 for v in [ctx, acc, gt, comp]):
        recs.append("✅ System is working as expected. No changes needed.")
        recs.append("📌 Log this example as a golden reference case.")
        recs.append(
            f" Based on: Context Relevancy: {round(ctx*100,1)}%, "
            f"Answer Correctness: {round(acc*100,1)}%, "
            f"GT Validity: {round(gt*100,1)}%, "
            f"Completeness: {round(comp*100,1)}%"
        )
    unique_recs = list(dict.fromkeys(recs))
    print("unique_recsssssssssssssssss",unique_recs)
    # ---------- Deduplicate ----------
    return sort_by_priority(unique_recs)

